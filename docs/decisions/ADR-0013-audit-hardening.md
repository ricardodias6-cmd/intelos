# ADR-0013 — Correções de integridade do caminho auditável

- **Estado:** Aceite
- **Data:** 2026-08-01
- **Âmbito:** Evidence Core, superfície de auditoria, chat auditável
- **Dependências:** Fases 4–10 integradas na main

## Contexto

Uma auditoria ao código detetou que o caminho factual podia usar evidência que
o próprio sistema já considerava inválida, e que várias garantias declaradas
não estavam ligadas ao pipeline real:

- a recuperação escolhia sempre a versão mais recente de cada fonte sem olhar
  ao estado do ciclo de vida, pelo que evidência de uma versão revogada
  continuava a ser recuperada e citada, com a frescura a assinalar o problema
  apenas depois;
- blocos com `verification_status = rejected` eram recuperáveis e, quando
  citados, faziam a validação semântica levantar `InvalidInputError`,
  transformando uma resposta inteira num erro 400;
- o `EvidenceValidator` — hash do texto e correspondência literal de citações —
  existia mas só era usado em testes;
- a expansão do grafo era inalcançável no caso normal, porque a recuperação já
  esgotava `max_evidence` antes de a expansão ser chamada;
- a tabela `audit_revalidation` não existia em nenhuma migração e a
  idempotência era verificada em duas etapas não atómicas.

## Decisão

### Recuperação

Só versões com estado `current` são recuperáveis. Uma versão `superseded` só é
alcançável quando o pedido fixa explicitamente `version_hash`. Uma versão
`revoked` nunca é recuperável e não há retrocesso para a versão anterior: uma
fonte cuja versão atual foi revogada deixa de produzir evidência, em vez de
responder silenciosamente a partir de um documento antigo.

Blocos rejeitados são excluídos na consulta de candidatos e novamente antes da
ordenação.

### Validação

A validação semântica passa a verificar o `text_hash` de cada bloco citado.
Evidência cujo texto não corresponde à extração não suporta nem contradiz uma
afirmação: é excluída da avaliação e assinalada no relatório.

Uma claim do tipo `quote` só pode ser apresentada como facto se o seu texto
aparecer literalmente no texto da evidência. A semelhança semântica, por si só,
deixa de ser suficiente.

Uma evidência inutilizável deixa de descartar a resposta inteira: a afirmação
afetada é removida da resposta factual e o motivo fica no registo de auditoria.

### Orçamento de evidência

Quando a expansão do grafo está ativa, parte de `max_evidence` é reservada para
ela (`graph_expansion_slots`, por omissão 2), em vez de ser truncada depois.

### Revalidação

A tabela `audit_revalidation` passa a ser criada pela migração 32, com índice
único em `idempotency_key`. O registo inicial é criado com `CREATE`, pelo que
duas revalidações concorrentes com a mesma chave não podem ambas iniciar o
pipeline.

### Chat

Sem qualquer fonte no contexto do notebook, o chat auditável explica que não há
fonte em vez de devolver uma resposta de "evidência insuficiente" que parece
resultar de uma pesquisa real.

## Consequências

- Respostas deixam de poder assentar em evidência revogada, rejeitada ou
  alterada; em contrapartida, uma fonte com versão revogada deixa de responder
  até haver nova versão corrente.
- Citações literais tornam-se verificáveis por construção.
- A migração 32 é reversível e coberta pelo teste de integração de migrações.
- O caminho auditável do chat continua a ser o único caminho do chat de
  notebook: o mecanismo anterior permanece no código mas não é alcançável.
  Reintroduzi-lo como fallback explícito fica por decidir.
