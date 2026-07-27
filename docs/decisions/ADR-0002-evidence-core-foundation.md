# ADR-0002: Fundação do Evidence Core

- Estado: aceite
- Data: 2026-07-27

## Contexto

O Open Notebook foi importado como componente inicial do motor de conhecimento do Intelos. O seu modelo atual de embeddings preserva o texto e a ordem dos blocos, mas não garante, de forma transversal, a página, as coordenadas, a versão documental, o estado de verificação ou a relação explícita entre cada afirmação e a evidência que a sustenta.

O Intelos pretende produzir respostas rigorosas, auditáveis e reutilizáveis. Para isso, não basta apresentar o documento de origem. Cada afirmação tem de poder ser ligada a uma passagem concreta e a uma versão imutável da fonte.

## Decisão

Será criado um Evidence Core próprio dentro do motor de conhecimento do Intelos.

A primeira implementação ficará em `services/knowledge-engine/open_notebook/evidence/` e terá três responsabilidades separadas:

1. representar versões documentais, blocos de evidência, afirmações e estados epistemológicos;
2. executar validações determinísticas que não dependem da obediência de um modelo de linguagem;
3. expor a Constituição de Resposta do Intelos como política versionada e testável.

A persistência será preparada através das tabelas `document_version`, `evidence_block`, `claim` e `claim_evidence` no SurrealDB.

## Princípios vinculativos

- Nenhuma afirmação factual deve ser apresentada como confirmada sem evidência identificável.
- Nenhuma evidência existe sem documento, versão, texto e proveniência mínima.
- Uma citação direta só é considerada verificada quando o transcrito ocorre na evidência associada.
- A página física do PDF e a página impressa no documento são campos distintos.
- O texto extraído automaticamente e o texto confirmado por uma pessoa são preservados separadamente.
- Uma afirmação fornecida pelo utilizador não é automaticamente convertida em facto verificado.
- As contradições não são ocultadas.
- A ausência de evidência suficiente obriga a uma resposta não definitiva.
- O modelo de linguagem não pode inventar identificadores de evidência.

## Processamento documental

O Docling será o normalizador documental principal. Quando estiver explicitamente selecionado e o runtime opcional estiver disponível, o Intelos executará uma única conversão que produz simultaneamente o Markdown usado pelo Open Notebook e os blocos de evidência com proveniência.

O Chandra será utilizado apenas quando seja necessário OCR ou compreensão visual de um documento complexo, digitalizado ou manuscrito. Não será introduzido um segundo motor OCR nesta fase.

## Constituição de Resposta

As nove regras fornecidas pelo proprietário do Intelos serão preservadas integralmente num documento versionado e representadas no código por identificadores estáveis.

As regras de estilo serão aplicadas na camada de resposta. As regras relativas a fontes, números, atualidade, citações, lógica e independência crítica serão também convertidas em validações técnicas sempre que isso seja objetivamente possível.

## Consequências

- O Evidence Core nasce integrado no Open Notebook, mas com fronteiras próprias para poder ser separado no futuro.
- O fluxo de ingestão Docling fica ligado ao Evidence Core sem executar uma segunda conversão do documento.
- O mecanismo anterior de `source_embedding` permanece temporariamente ativo por compatibilidade.
- A integração do Chandra, o reranking semântico, a validação semântica, a visualização PDF e a inserção em DOCX ficam para fases posteriores.
- O fluxo de chat ainda não está obrigado a devolver afirmações ligadas a Evidence IDs.
- Qualquer estado denominado `verified` deve indicar se a verificação foi automática ou humana.
