# Intelos Evidence Core

Esta pasta contém a primeira fundação do sistema de evidência verificável do Intelos.

## Responsabilidades atuais

- representar blocos de evidência ligados a uma versão documental;
- distinguir texto extraído de texto confirmado;
- representar afirmações como factos, citações, estatísticas, informação técnica, pressupostos, opiniões ou declarações do utilizador;
- validar identificadores, hashes, transcrições, atualidade, números e estados de suporte;
- expor a Constituição de Resposta do Intelos através de identificadores estáveis.

## Limites desta fase

A validação atual é estrutural e determinística. Confirma que a evidência existe, que o texto não foi alterado e que uma citação direta ocorre na passagem associada.

Ainda não demonstra, por si só, que uma passagem implica semanticamente uma determinada conclusão. Essa validação exigirá uma camada separada de avaliação semântica e, nos casos críticos, confirmação humana.

## Próximas integrações

1. produzir `document_version` e `evidence_block` durante a ingestão documental;
2. preservar página, página impressa, secção e coordenadas através do Docling;
3. usar o Chandra apenas quando seja necessário OCR ou interpretação visual;
4. recuperar blocos de evidência através de pesquisa híbrida e reranking;
5. obrigar o fluxo de resposta a devolver afirmações atómicas ligadas a Evidence IDs;
6. abrir o PDF na passagem correspondente;
7. gerar transcritos e referências para exportação documental.

## Regra essencial

O modelo de linguagem não cria evidência. Apenas pode referenciar identificadores fornecidos pelo sistema e validados contra o registo fechado do Evidence Core.
