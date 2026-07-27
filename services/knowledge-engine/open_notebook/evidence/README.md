# Intelos Evidence Core

Esta pasta contém a primeira fundação do sistema de evidência verificável do Intelos.

## Responsabilidades atuais

- representar blocos de evidência ligados a uma versão documental;
- distinguir texto extraído de texto confirmado;
- representar afirmações como factos, citações, estatísticas, informação técnica, pressupostos, opiniões ou declarações do utilizador;
- validar identificadores, hashes, transcrições, atualidade, números e estados de suporte;
- expor a Constituição de Resposta do Intelos através de identificadores estáveis;
- converter documentos com Docling numa única passagem, produzindo Markdown e blocos estruturados;
- preservar página física, coordenadas, tipo de bloco, secção e hash da versão;
- persistir versões e blocos de forma idempotente no SurrealDB.

## Ativação atual

A ingestão estruturada é utilizada quando o motor documental selecionado nas definições é `docling` e o runtime opcional está disponível. Os restantes caminhos de ingestão mantêm o comportamento original do Open Notebook.

O mecanismo `source_embedding` continua ativo por compatibilidade. Nesta fase, a pesquisa e o chat ainda não consultam diretamente os blocos de evidência.

## Limites desta fase

A validação atual é estrutural e determinística. Confirma que a evidência existe, que o texto não foi alterado e que uma citação direta ocorre na passagem associada.

Ainda não demonstra, por si só, que uma passagem implica semanticamente uma determinada conclusão. Essa validação exigirá uma camada separada de avaliação semântica e, nos casos críticos, confirmação humana.

Também não foi ainda executado um teste de ponta a ponta com Docling, uma instância real de SurrealDB e um documento português representativo.

## Próximas integrações

1. testar a migração e a ingestão com uma instância real de SurrealDB e PDF;
2. usar o Chandra apenas quando seja necessário OCR ou interpretação visual;
3. recuperar blocos de evidência através de pesquisa híbrida e reranking;
4. obrigar o fluxo de resposta a devolver afirmações atómicas ligadas a Evidence IDs;
5. abrir o PDF na passagem correspondente;
6. gerar transcritos e referências para exportação documental.

## Regra essencial

O modelo de linguagem não cria evidência. Apenas pode referenciar identificadores fornecidos pelo sistema e validados contra o registo fechado do Evidence Core.
