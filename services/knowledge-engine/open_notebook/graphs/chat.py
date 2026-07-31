import asyncio
import sqlite3
from typing import Annotated, Optional

from ai_prompter import Prompter
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from open_notebook.ai.provision import provision_langchain_model
from open_notebook.config import LANGGRAPH_CHECKPOINT_FILE
from open_notebook.domain.notebook import Notebook
from open_notebook.evidence.auditable_answer import (
    AuditableAnswerRequest,
    build_auditable_answer,
)
from open_notebook.exceptions import OpenNotebookError
from open_notebook.utils import clean_thinking_content
from open_notebook.utils.error_classifier import classify_error
from open_notebook.utils.text_utils import extract_text_content


class ThreadState(TypedDict):
    messages: Annotated[list, add_messages]
    notebook: Optional[Notebook]
    context: Optional[str]
    context_config: Optional[dict]
    model_override: Optional[str]
    audit_enabled: Optional[bool]
    audit_conversation_id: Optional[str]
    audit_turn_id: Optional[str]
    audit_response_mode: Optional[str]


def call_model_with_messages(state: ThreadState, config: RunnableConfig) -> dict:
    try:
        if state.get("audit_enabled"):
            return _call_auditable_model(state)

        system_prompt = Prompter(prompt_template="chat/system").render(data=state)  # type: ignore[arg-type]
        payload = [SystemMessage(content=system_prompt)] + state.get("messages", [])
        model_id = config.get("configurable", {}).get("model_id") or state.get(
            "model_override"
        )

        # Handle async model provisioning from sync context
        def run_in_new_loop():
            """Run the async function in a new event loop"""
            new_loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(new_loop)
                return new_loop.run_until_complete(
                    provision_langchain_model(
                        str(payload), model_id, "chat", max_tokens=8192
                    )
                )
            finally:
                new_loop.close()
                asyncio.set_event_loop(None)

        try:
            # Try to get the current event loop
            asyncio.get_running_loop()
            # If we're in an event loop, run in a thread with a new loop
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_in_new_loop)
                model = future.result()
        except RuntimeError:
            # No event loop running, safe to use asyncio.run()
            model = asyncio.run(
                provision_langchain_model(
                    str(payload),
                    model_id,
                    "chat",
                    max_tokens=8192,
                )
            )

        ai_message = model.invoke(payload)

        # Clean thinking content from AI response (e.g., <think>...</think> tags)
        content = extract_text_content(ai_message.content)
        cleaned_content = clean_thinking_content(content)
        cleaned_message = ai_message.model_copy(update={"content": cleaned_content})

        return {"messages": cleaned_message}
    except OpenNotebookError:
        raise
    except Exception as e:
        error_class, user_message = classify_error(e)
        raise error_class(user_message) from e


def _call_auditable_model(state: ThreadState) -> dict:
    human_messages = [
        message
        for message in state.get("messages", [])
        if getattr(message, "type", None) == "human"
    ]
    if not human_messages:
        raise OpenNotebookError("Auditable chat requires a human question")

    question = str(human_messages[-1].content).strip()
    conversation_id = state.get("audit_conversation_id")
    turn_id = state.get("audit_turn_id")
    response_mode = state.get("audit_response_mode") or "detailed"
    if not conversation_id or not turn_id:
        raise OpenNotebookError(
            "Auditable chat requires conversation and turn identifiers"
        )

    conversation_context = [
        str(message.content)
        for message in state.get("messages", [])[-7:-1]
        if getattr(message, "content", None)
    ]
    request = AuditableAnswerRequest(
        question=question,
        conversation_id=conversation_id,
        turn_id=turn_id,
        response_mode=response_mode,
        conversation_context=conversation_context,
    )

    def run_answer():
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(build_auditable_answer(request))
        finally:
            loop.close()
            asyncio.set_event_loop(None)

    try:
        asyncio.get_running_loop()
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as executor:
            answer = executor.submit(run_answer).result()
    except RuntimeError:
        answer = asyncio.run(build_auditable_answer(request))

    if not answer.answer_id or not answer.audit_report_id:
        raise OpenNotebookError(
            "Auditable chat did not produce stable audit identifiers"
        )

    return {
        "messages": AIMessage(
            id=answer.answer_id,
            content=answer.answer,
            additional_kwargs={
                "answer_id": answer.answer_id,
                "audit_report_id": answer.audit_report_id,
                "conversation_id": conversation_id,
                "turn_id": turn_id,
                "audit_status": answer.status.value,
            },
        )
    }


conn = sqlite3.connect(
    LANGGRAPH_CHECKPOINT_FILE,
    check_same_thread=False,
)
memory = SqliteSaver(conn)

agent_state = StateGraph(ThreadState)
agent_state.add_node("agent", call_model_with_messages)
agent_state.add_edge(START, "agent")
agent_state.add_edge("agent", END)
graph = agent_state.compile(checkpointer=memory)
