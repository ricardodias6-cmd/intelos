# Roadmap do Intelos

Este documento é a referência de estado do projeto. O Intelos é um sistema privado, de utilização pessoal, e a conclusão de uma fase não autoriza exposição pública, uso multiutilizador ou operação em produção sem uma avaliação específica.

## Estado atual

A main contém as Fases 0–9 concluídas e integradas e já inclui as subfases 10.1–10.5 da Fase 10. A subfase 10.6 fecha a integração diária Chat → Auditoria → Revalidação.

| Fase | Tema | Estado |
| --- | --- | --- |
| 0 | Fundação | Concluída |
| 1 | Importação inteligente | Concluída |
| 2 | Hybrid Evidence Retrieval | Concluída |
| 3 | Claim Evidence Semantic Validation | Concluída |
| 4 | Pipeline auditável de ponta a ponta | Concluída |
| 5 | Evidence-Aware Generation | Concluída |
| 6 | Persistent Knowledge Graph | Concluída |
| 7 | Explainable AI | Concluída |
| 8 | Autonomous Knowledge Maintenance | Concluída |
| 9 | Intelos Copilot | Concluída |
| 10 | Superfície de auditoria e prontidão operacional | Em conclusão |

## Fase 10 — Superfície de auditoria e prontidão operacional

### Objetivo

Tornar a auditabilidade utilizável no ciclo diário do Copilot, preservando o caminho factual já validado. A fase deve permitir inspecionar uma resposta, compreender as suas decisões, verificar a frescura da evidência e iniciar uma revalidação controlada quando necessário.

### Subfases

1. **Contrato de leitura e consulta**
   - expor um modelo estável para AuditReport, claims, citações, conflitos, trace e freshness;
   - suportar consulta por answer_id, conversation_id e turn_id;
   - aplicar limites, paginação e autorização compatíveis com o âmbito pessoal;
   - manter leituras sem efeitos secundários.

2. **Apresentação da auditoria**
   - mostrar evidência selecionada e rejeitada;
   - distinguir factos, inferências, conflitos e incerteza;
   - apresentar confiança e estado de frescura;
   - impedir que o contexto conversacional seja apresentado como evidência.

3. **Revalidação controlada**
   - iniciar pedidos idempotentes de revalidação para respostas não atuais;
   - preservar o relatório original e o histórico da nova execução;
   - exigir revalidação para possibly_outdated, outdated e unknown;
   - nunca substituir silenciosamente uma resposta previamente auditada.

4. **Prontidão operacional**
   - acrescentar métricas e logs sem conteúdo documental desnecessário;
   - documentar falhas, recuperação e retenção;
   - validar migrações, contratos, segurança e regressões em CI;
   - manter o sistema limitado ao uso pessoal local até existir avaliação própria de exposição.

5. **Integração frontend da auditoria** — concluída na main
   - painel de apresentação com os modos summary, detailed e audit;
   - indicadores de confiança, frescura, conflitos e decisões de evidência;
   - consulta por answer_id com tratamento seguro de erros.

6. **Fecho do ciclo Chat → Auditoria → Revalidação** — em implementação
   - transportar answer_id, audit_report_id, conversation_id e turn_id nas mensagens AI;
   - abrir a auditoria diretamente a partir da resposta do Chat;
   - iniciar revalidação controlada e mostrar os novos identificadores;
   - consultar visualmente o histórico por conversa, turno e frescura;
   - validar o fluxo completo com testes end-to-end.

### Critérios de aceitação

- Uma resposta pode ser consultada pelo seu answer_id e ligada ao turno que a produziu.
- O utilizador consegue identificar claims, Evidence IDs, conflitos, confiança e frescura.
- Qualquer estado não atual exige revalidação explícita.
- Um Evidence ID ou uma versão desconhecida produz comportamento fail-safe.
- O pedido de revalidação é idempotente e não apaga o relatório anterior.
- Nenhuma informação de conversa é promovida a evidência documental.
- O CI cobre contrato, API, persistência, migração, autorização e regressão.
- O âmbito pessoal e os limites de segurança continuam explícitos na documentação.

### Fora do âmbito

- fontes externas não verificadas;
- operação pública, multiutilizador ou SaaS;
- alteração do algoritmo de recuperação híbrida;
- relaxamento da validação semântica;
- geração de afirmações sem Evidence IDs;
- substituição silenciosa de respostas auditadas.

## Referências

- [ADR-0012 — Superfície de auditoria e prontidão operacional](decisions/ADR-0012-audit-surface-and-operational-readiness.md)
- [ADR-0011 — Ligação da auditoria do Copilot e frescura da evidência](decisions/ADR-0011-copilot-audit-freshness.md)
