# ADR-0003: Validação semântica afirmação-evidência

## Estado

Aceite para implementação na Fase 3.

## Contexto

A Fase 0 estabeleceu o Evidence Core, a Fase 1 validou a ingestão documental real e a Fase 2 introduziu recuperação híbrida diretamente sobre `evidence_block`. Falta avaliar, de forma explícita e auditável, se as evidências selecionadas sustentam semanticamente uma afirmação concreta.

A validação determinística existente confirma integridade, resolução de identificadores, transcrições literais, atualidade e regras de apresentação. Não resolve entailment semântico e declara expressamente esse limite.

## Decisão

A Fase 3 introduz um serviço autónomo de validação semântica afirmação-evidência com as seguintes propriedades:

1. recebe uma afirmação atómica e uma lista fechada de Evidence IDs;
2. resolve os blocos diretamente na base de dados e rejeita identificadores inexistentes, evidência rejeitada e mistura de versões da mesma fonte;
3. utiliza o texto verificado quando disponível e, caso contrário, o texto extraído;
4. calcula compatibilidade semântica por embeddings e sinais determinísticos complementares;
5. verifica conservação de números relevantes e possível inversão de polaridade por negação;
6. produz uma recomendação de suporte `direct`, `partial`, `contradicted` ou `unsupported`;
7. devolve pontuações e razões auditáveis por Evidence ID;
8. exige revisão humana nos casos contraditórios, limítrofes, sem modelo de embeddings ou com sinais inconsistentes;
9. nunca altera automaticamente uma afirmação persistida nem promove uma recomendação a verdade definitiva;
10. disponibiliza a capacidade através de `POST /api/evidence/validate-claim`.

## Critérios de classificação

- `direct`: compatibilidade elevada e ausência de conflito numérico ou de polaridade;
- `partial`: compatibilidade moderada ou suporte distribuído por vários blocos;
- `contradicted`: conflito numérico relevante ou inversão de polaridade acompanhada de sobreposição lexical suficiente;
- `unsupported`: compatibilidade insuficiente e ausência de contradição demonstrável.

Os limiares são explícitos no pedido, dentro de intervalos seguros, e são devolvidos na resposta.

## Fora do âmbito

Esta fase não inclui:

- geração automática de afirmações a partir de respostas de chat;
- obrigação de o chat emitir Evidence IDs;
- alteração do grafo de resposta;
- persistência automática da decisão semântica;
- validação jurídica ou factual externa;
- substituição de revisão humana em decisões de elevado impacto;
- visualizador PDF, OCR avançado, Chandra ou exportação DOCX/PDF.

## Consequências

A aplicação passa a distinguir validação estrutural de validação semântica. O resultado é reproduzível dentro do mesmo modelo de embeddings e parâmetros, mas continua a ser uma recomendação técnica. O nome do modelo, os limiares e os sinais usados ficam expostos para auditoria.