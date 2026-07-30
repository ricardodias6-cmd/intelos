# ADR-0012 — Superfície de auditoria e prontidão operacional

- **Estado:** Aceite como contrato de planeamento
- **Data:** 2026-07-30
- **Âmbito:** Fase 10 do Intelos
- **Dependências:** Fases 4–9 integradas na main

## Contexto

O Intelos já produz respostas condicionadas à evidência, claims validadas, citações, confiança, relatórios de auditoria e avaliações live de frescura. Os contratos existentes permitem verificar tecnicamente uma resposta, mas ainda não definem a próxima superfície de consulta, apresentação e revalidação como uma unidade coerente.

A Fase 10 deve melhorar a utilização e a operação da auditabilidade sem alterar o caminho factual já validado. Em particular, uma resposta que deixou de ser atual não pode ser apresentada novamente como se estivesse validada no presente.

## Decisão

A Fase 10 será implementada em quatro subfases:

1. contrato de leitura e consulta;
2. apresentação da auditoria;
3. revalidação controlada;
4. prontidão operacional.

O contrato deve reutilizar os modelos e endpoints existentes sempre que possível, incluindo AuditReport, AuditFreshness, GET /api/evidence/answer/{answer_id}/audit e GET /api/evidence/answer/{answer_id}/freshness.

### Modelo de consulta

As consultas devem aceitar um identificador obrigatório de resposta ou filtros limitados por:

- answer_id;
- conversation_id;
- turn_id;
- estado de frescura;
- intervalo temporal, quando suportado.

As respostas devem ser limitadas, determinísticas e ordenáveis. O servidor não deve devolver texto bruto de contexto conversacional como se fosse evidência.

### Conteúdo auditável

A superfície de auditoria deve permitir distinguir:

- resposta final;
- claims e respetivo estado de validação;
- Evidence IDs selecionados, rejeitados e efetivamente citados;
- citações e localização documental;
- conflitos;
- confiança;
- eventos de trace;
- freshness.status, requires_revalidation, change_ids e affected_evidence_ids.

A apresentação pode variar em profundidade, mas não pode remover ou alterar a proveniência factual do relatório.

### Revalidação

A revalidação será uma operação explícita, autenticada no âmbito suportado e idempotente. O pedido deverá:

- referenciar o answer_id e o relatório de origem;
- preservar o relatório original;
- obter uma chave de idempotência estável;
- registar o motivo e os Evidence IDs ou change IDs relevantes;
- produzir um novo resultado auditável, caso seja executado.

Os estados possibly_outdated, outdated e unknown exigem revalidação. O estado unknown é fail-safe: não pode ser tratado como current.

### Invariantes de segurança

- Leituras de auditoria não alteram respostas nem documentos.
- Nenhuma claim sem validação pode ser promovida a facto.
- Nenhum Evidence ID fora do conjunto permitido pode ser apresentado como suporte.
- A frescura é avaliada contra o estado documental atual, não apenas contra um booleano persistido.
- Uma resposta não atual não é substituída silenciosamente.
- O contexto conversacional serve para desambiguação e não constitui prova.
- Logs e métricas não devem incluir conteúdo documental ou segredos desnecessários.
- O produto permanece limitado ao uso pessoal e local até existir uma avaliação específica de exposição.

## Consequências

A Fase 10 acrescentará uma camada de leitura, apresentação e reprocessamento sobre os contratos existentes. Isso aumenta a utilidade do Copilot e torna verificável o ciclo de vida de uma resposta sem duplicar o retrieval, a validação semântica ou a persistência de evidência.

A compatibilidade deve ser aditiva. Relatórios anteriores continuam legíveis com defaults seguros, e qualquer falha de resolução de evidência resulta em revalidação, nunca em confiança implícita.

## Critérios de conclusão

A fase só fica concluída quando:

- os contratos de consulta e revalidação estiverem versionados;
- API, persistência e apresentação tiverem testes de contrato;
- existirem testes de idempotência, autorização, migração e regressão;
- estados de frescura não atuais forem tratados fail-safe;
- o histórico dos relatórios for preservado;
- os workflows aplicáveis terminarem com sucesso;
- os limites de utilização pessoal e local permanecerem documentados.

## Fora do âmbito

Esta decisão não autoriza:

- fontes externas não verificadas;
- operação pública, multiutilizador ou SaaS;
- relaxamento dos gates de validação;
- alteração silenciosa de respostas;
- enriquecimento do grafo com texto não suportado;
- exposição de conteúdo documental em logs.
