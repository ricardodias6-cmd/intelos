# ADR-0010: Clarificação e apresentação do Intelos Copilot

## Estado

Aceite para implementação na subfase de clarificação da Fase 9.

## Contexto

O contrato do Copilot já suporta contexto limitado, respostas auditáveis e três modos de apresentação. Faltam duas garantias operacionais:

- perguntas de seguimento sem contexto suficiente devem pedir esclarecimento antes do retrieval;
- os modos `concise`, `detailed` e `audit` devem alterar apenas a apresentação, preservando claims, Evidence IDs, citações, confiança e estado.

## Decisão

A clarificação será determinística e executada antes do retrieval e do LLM.

Uma pergunta será marcada como `clarification_required` apenas quando contiver uma referência deíctica ou um seguimento explicitamente ambíguo, como “isso”, “aquilo”, “qual deles” ou “e depois”, e não existir contexto conversacional. A clarificação:

- não executa retrieval, grafo ou geração;
- não apresenta claims factuais nem citações;
- mantém `answer_id` e `audit_report_id` para rastreabilidade;
- devolve uma pergunta única em `next_actions`;
- pode ser persistida como um turno normal, sem ser tratada como evidência.

Com contexto conversacional, a pergunta segue o pipeline auditável normal. O histórico continua a ser apenas contexto de desambiguação.

A apresentação será projetada depois da resposta validada:

- `concise`: mantém a resposta factual essencial;
- `detailed`: acrescenta as claims validadas e respetivas qualificações;
- `audit`: acrescenta estado, Evidence IDs, conflitos, lacunas e percurso técnico, sem inserir texto documental fora das citações.

Nenhum modo pode:

- criar claims;
- alterar o suporte ou a confiança;
- ocultar conflitos ou revisão humana;
- remover Evidence IDs ou citações;
- converter contexto conversacional em evidência.

## Contrato

Uma resposta de clarificação usa:

```json
{
  "status": "clarification_required",
  "answer": "Preciso de um esclarecimento para responder com precisão.",
  "claims": [],
  "citations": [],
  "overall_confidence": 0,
  "next_actions": [
    {
      "type": "clarification",
      "question": "A que documento, entidade ou procedimento se refere?"
    }
  ]
}
```

O relatório de auditoria regista o estado e o motivo determinístico da clarificação.

## Critérios de aceitação

1. Uma pergunta ambígua sem contexto não chama retrieval nem o LLM.
2. A resposta de clarificação não contém claims, citações ou confiança factual.
3. Uma pergunta equivalente com contexto segue o pipeline normal.
4. Os três modos mantêm idênticos claims, citações, confiança e estado.
5. `detailed` e `audit` expõem informação adicional apenas derivada do resultado validado.
6. A resposta `audit` não duplica texto documental nem trata IDs como prova.
7. O comportamento é coberto por testes de contrato e regressão.

## Limites

Esta subfase não implementa streaming, interface gráfica, memória ilimitada, ações externas ou clarificação gerada pelo modelo. A regra determinística pode ser ampliada numa decisão posterior com novos testes e métricas.
