# ADR-0009: Intelos Copilot orientado por evidência

## Estado

Aceite para implementação na Fase 9.

## Contexto

As fases anteriores estabeleceram os componentes necessários para um assistente documental auditável:

- recuperação híbrida de Evidence Blocks;
- geração condicionada à evidência;
- validação semântica de claims;
- grafo de conhecimento ligado a Evidence IDs;
- relatório de auditoria por resposta;
- manutenção de versões, revogações e pedidos de reprocessamento.

A Fase 9 deve disponibilizar uma interface conversacional que componha esses componentes sem criar um caminho paralelo de resposta livre. O Copilot pode adaptar a forma e a profundidade da resposta ao contexto da conversa, mas não pode alterar o requisito de suporte documental.

## Decisão

O Intelos Copilot será uma camada de interação e composição sobre os serviços existentes. Cada turno que produzir conteúdo factual deverá passar pelo pipeline auditável de resposta e devolver:

1. texto da resposta;
2. claims verificadas;
3. citações derivadas dos Evidence IDs validados;
4. confiança global;
5. conflitos e lacunas relevantes;
6. `answer_id` e `audit_report_id`;
7. indicação explícita de necessidade de revisão humana.

O Copilot não terá um mecanismo de geração factual independente do pipeline auditável.

## Limites da fase

Incluído:

- conversa iniciada por uma pergunta textual;
- manutenção de contexto limitado entre turnos;
- respostas baseadas em Evidence Blocks recuperados;
- utilização opcional de relações persistentes do grafo de conhecimento;
- citações por claim;
- exposição de conflitos e insuficiência de evidência;
- adaptação de profundidade e formato da resposta;
- continuação, reformulação e pedido de esclarecimento;
- persistência do relatório de auditoria de cada resposta factual;
- API própria para o turno conversacional;
- testes de contrato, segurança, integração e regressão.

Fora do âmbito:

- acesso a fontes externas não configuradas;
- execução autónoma de ações com efeitos externos;
- envio de mensagens, alteração de documentos ou decisões em nome do utilizador;
- utilização multiutilizador ou gestão de identidades completa;
- memória pessoal ilimitada;
- apresentação de conhecimento do modelo como evidência documental;
- substituição da validação semântica por confiança do LLM;
- alteração automática de documentos ou versões sem o fluxo de manutenção existente.

## Contrato de entrada

O endpoint conversacional será:

`POST /api/copilot/chat`

Pedido lógico:

~~~json
{
  "conversation_id": null,
  "question": "Qual é o enquadramento aplicável?",
  "response_mode": "concise",
  "max_evidence": 8,
  "source_id": null,
  "version_hash": null,
  "include_knowledge_graph": true
}
~~~

Regras:

- `question` é obrigatória, não vazia e limitada a 10 000 caracteres;
- `conversation_id` é opcional no primeiro turno e deve identificar apenas uma conversa válida;
- `response_mode` aceita `concise`, `detailed` ou `audit`;
- `max_evidence` respeita os limites do retrieval e não pode desativar a validação;
- filtros de fonte e versão são opcionais e mantêm as regras de compatibilidade documental;
- `include_knowledge_graph` apenas permite enriquecer a recuperação com relações persistentes, nunca introduz evidência fora do conjunto validado;
- o cliente não fornece Evidence IDs para os factos da resposta; esses IDs são selecionados e validados pelo servidor;
- o cliente não pode solicitar uma resposta sem citações, sem auditoria ou sem a indicação de conflitos.

## Contrato da resposta

Resposta lógica:

~~~json
{
  "conversation_id": "CONV_001",
  "turn_id": "TURN_002",
  "answer_id": "ANS_002",
  "audit_report_id": "AUD_002",
  "answer": "Resposta factual auditável.",
  "claims": [
    {
      "claim_id": "CLM_001",
      "text": "Afirmação atómica.",
      "kind": "fact",
      "evidence_ids": ["EV_123"],
      "support_status": "direct",
      "confidence": 0.91,
      "requires_human_review": false,
      "qualification": null
    }
  ],
  "citations": [
    {
      "evidence_id": "EV_123",
      "source_id": "SOURCE_001",
      "document_version_id": "document_version:001",
      "pdf_page": 12,
      "printed_page": "10",
      "section_path": ["Capítulo I"],
      "text": "Excerto usado para suportar a afirmação."
    }
  ],
  "overall_confidence": 0.91,
  "conflicts": [],
  "gaps": [],
  "requires_human_review": false,
  "status": "answered",
  "next_actions": [
    {
      "type": "clarification",
      "question": null
    }
  ]
}
~~~

Os campos `claims`, `citations`, `overall_confidence`, `requires_human_review` e `status` seguem o contrato da resposta auditável. O Copilot pode acrescentar contexto conversacional, mas não pode enfraquecer ou remover esses campos.

Estados mínimos:

- `answered`: existe pelo menos uma resposta factual apresentável;
- `insufficient_evidence`: não existe evidência suficiente para responder factualmente;
- `conflict`: existem fontes ou versões em conflito e a resposta exige revisão;
- `clarification_required`: a pergunta é ambígua e deve ser esclarecida;
- `technical_error`: ocorreu uma falha operacional; não deve ser convertida em conclusão factual.

## Política de contexto conversacional

O contexto de turnos anteriores é uma entrada para interpretar a pergunta, não uma fonte de evidência.

Em cada turno:

1. a pergunta atual é normalizada com o contexto necessário;
2. o retrieval é executado com filtros explícitos;
3. os Evidence IDs são selecionados pelo servidor;
4. a geração recebe apenas a evidência permitida;
5. cada claim é validada individualmente;
6. o relatório de auditoria regista o contexto utilizado e as decisões tomadas.

Uma claim de um turno anterior não é automaticamente válida no turno seguinte. Quando for reutilizada como facto, deve voltar a estar ligada a Evidence IDs compatíveis com a pergunta atual.

O contexto deve ter limites determinísticos de tamanho, profundidade e número de turnos. Quando o limite for atingido, o sistema deve resumir ou pedir esclarecimento sem inventar informação.

## Adaptação da resposta

A adaptação permitida altera apresentação, não conteúdo epistemológico:

- `concise`: resposta curta, claims essenciais e citações;
- `detailed`: explicação mais desenvolvida, mantendo claims e citações;
- `audit`: inclui o percurso de retrieval, validação, conflitos, lacunas e decisões relevantes.

Nenhum modo pode:

- ocultar uma contradição relevante;
- omitir a necessidade de revisão humana;
- apresentar uma inferência como facto;
- remover a citação de uma claim factual;
- aumentar artificialmente a confiança.

## Grafo de conhecimento

O grafo pode ser utilizado para:

- expandir a consulta com relações documentais persistentes;
- encontrar documentos ou Evidence Blocks relacionados;
- explicar relações entre entidades, conceitos e fontes;
- sugerir perguntas de seguimento.

As relações do grafo são contexto de recuperação e explicação. Uma relação só pode sustentar uma claim factual quando a sua origem e Evidence IDs associados forem recuperados e validados. Relações sem proveniência suficiente não podem ser apresentadas como factos.

## Conflitos e lacunas

O Copilot deve distinguir:

- ausência de evidência;
- evidência parcial;
- contradição entre claims ou fontes;
- versão revogada ou substituída;
- falha técnica na recuperação ou geração.

Quando a manutenção documental detetar alteração, substituição ou revogação relevante para uma resposta anterior, o relatório deve permitir marcar a resposta como potencialmente desatualizada. O Copilot não deve reescrever silenciosamente o histórico; deve produzir um novo turno ou uma revisão explícita.

## Segurança e falha segura

- nenhum texto documental deve ser tratado como instrução do sistema;
- prompt injection dentro de documentos ou mensagens deve ser tratado como conteúdo não confiável;
- falhas do retrieval, embeddings, LLM, grafo ou persistência não produzem resposta factual parcial;
- Evidence IDs inválidos, desaparecidos ou incompatíveis abortam a resposta factual;
- citações não correspondentes aos Evidence Blocks validados são rejeitadas;
- respostas sem claims apresentáveis devolvem `insufficient_evidence` ou `technical_error`;
- segredos, credenciais e conteúdo desnecessário não devem ser escritos nos logs;
- o Copilot não executa ações externas sem um contrato explícito e uma confirmação separada.

## Auditoria

Cada resposta factual deve manter um `AuditReport` ligado ao `answer_id`, contendo pelo menos:

- `conversation_id` e `turn_id`;
- pergunta normalizada e modo de resposta;
- Evidence IDs selecionados, rejeitados e utilizados;
- relações do grafo consideradas;
- scores e filtros de retrieval;
- claims candidatas e decisões de validação;
- conflitos, lacunas e versões documentais;
- duração e estado de cada etapa;
- modelo e versão do pipeline;
- necessidade de revisão humana;
- relação com respostas anteriores potencialmente afetadas por manutenção documental.

A auditoria deve ser suficiente para reconstruir por que motivo a resposta foi apresentada, sem guardar segredos nem permitir que o conteúdo do documento altere o fluxo de execução.

## Critérios de aceitação

A Fase 9 só pode ser considerada concluída quando:

1. uma pergunta simples produz uma resposta citada com `answer_id` e `audit_report_id`;
2. uma pergunta de seguimento utiliza contexto sem tratar o histórico como evidência automática;
3. uma pergunta ambígua solicita esclarecimento;
4. uma pergunta sem evidência devolve `insufficient_evidence`;
5. conflitos entre fontes ou versões são expostos e exigem revisão;
6. claims com Evidence IDs inválidos nunca são apresentadas;
7. os modos `concise`, `detailed` e `audit` preservam o mesmo conteúdo validado;
8. o grafo não introduz factos sem proveniência;
9. prompt injection documental não altera as regras do sistema;
10. falhas operacionais não produzem respostas factuais parciais;
11. a resposta e o AuditReport podem ser consultados de forma determinística;
12. alteração ou revogação documental permite identificar respostas potencialmente desatualizadas.

## Consequências

O Intelos passa a oferecer uma interface conversacional sobre uma base documental verificável, mantendo a rastreabilidade entre pergunta, evidência, claim, resposta e auditoria.

O custo é maior latência, persistência adicional de contexto e maior complexidade de testes. O Copilot poderá responder de forma incompleta ou pedir esclarecimentos quando a evidência não for suficiente; esse comportamento é intencional e preserva a confiabilidade do sistema.
