from __future__ import annotations

from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from api.routers._chat_shared import extract_chat_messages
from open_notebook.graphs import chat


def test_extract_chat_messages_preserves_audit_identifiers() -> None:
    message = AIMessage(
        id="ANSWER_CHAT_001",
        content="Resposta auditável.",
        additional_kwargs={
            "answer_id": "ANSWER_CHAT_001",
            "audit_report_id": "AUDIT_CHAT_001",
            "conversation_id": "chat_session:SESSION_001",
            "turn_id": "TURN_CHAT_001",
            "audit_status": "answered",
        },
    )

    extracted = extract_chat_messages([message])

    assert extracted[0].answer_id == "ANSWER_CHAT_001"
    assert extracted[0].audit_report_id == "AUDIT_CHAT_001"
    assert extracted[0].conversation_id == "chat_session:SESSION_001"
    assert extracted[0].turn_id == "TURN_CHAT_001"
    assert extracted[0].audit_status == "answered"


def test_auditable_chat_graph_emits_answer_and_audit_ids(
    monkeypatch,
) -> None:
    async def fake_build(request, *, model_id=None):
        assert request.question == "Quem decide?"
        assert request.conversation_id == "chat_session:SESSION_001"
        assert request.turn_id == "TURN_CHAT_001"
        assert request.source_ids == ["source:one"]
        return SimpleNamespace(
            answer_id="ANSWER_CHAT_001",
            audit_report_id="AUDIT_CHAT_001",
            answer="A entidade competente decide.",
            status=SimpleNamespace(value="answered"),
        )

    monkeypatch.setattr(chat, "build_auditable_answer", fake_build)

    result = chat.call_model_with_messages(
        {
            "messages": [
                HumanMessage(content="Quem decide?"),
            ],
            "notebook": None,
            "context": {
                "sources": [{"id": "source:one", "title": "Documento"}],
                "notes": [],
            },
            "context_config": None,
            "model_override": None,
            "audit_enabled": True,
            "audit_conversation_id": "chat_session:SESSION_001",
            "audit_turn_id": "TURN_CHAT_001",
            "audit_response_mode": "detailed",
        },
        RunnableConfig(),
    )

    message = result["messages"]
    assert message.id == "ANSWER_CHAT_001"
    assert message.content == "A entidade competente decide."
    assert message.additional_kwargs["audit_report_id"] == "AUDIT_CHAT_001"
    assert message.additional_kwargs["conversation_id"] == "chat_session:SESSION_001"


def test_auditable_chat_scope_is_empty_when_no_source_is_selected(
    monkeypatch,
) -> None:
    async def fake_build(request, *, model_id=None):
        assert request.source_ids == []
        return SimpleNamespace(
            answer_id="ANSWER_CHAT_EMPTY_SCOPE",
            audit_report_id="AUDIT_CHAT_EMPTY_SCOPE",
            answer="Não foi encontrada evidência suficiente.",
            status=SimpleNamespace(value="insufficient_evidence"),
        )

    monkeypatch.setattr(chat, "build_auditable_answer", fake_build)

    result = chat.call_model_with_messages(
        {
            "messages": [HumanMessage(content="Pergunta?")],
            "notebook": None,
            "context": {"sources": [], "notes": []},
            "context_config": None,
            "model_override": None,
            "audit_enabled": True,
            "audit_conversation_id": "chat_session:SESSION_002",
            "audit_turn_id": "TURN_CHAT_002",
            "audit_response_mode": "detailed",
        },
        RunnableConfig(),
    )

    assert result["messages"].id == "ANSWER_CHAT_EMPTY_SCOPE"
