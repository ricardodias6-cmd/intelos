# ADR-0004: Pipeline auditável de resposta

## Estado

Aceite para implementação na Fase 4.

## Contexto

As Fases 0 a 3 estabeleceram o Evidence Core, a ingestão documental, a recuperação híbrida e a validação semântica de uma afirmação contra Evidence IDs. Falta ligar estas capacidades num percurso único iniciado por uma pergunta do utilizador.

A Fase 4 deve produzir respostas úteis sem transformar geração livre em factos não verificáveis. O pipeline tem de preservar a separação entre evidência recuperada, texto gerado, afirmações extraídas, validações e resposta efetivamente apresentada.

## Decisão

A Fase 4 introduz um orquestrador de resposta auditável que executa, nesta ordem:

1. valida a pergunta e os limites da consulta;
2. executa a recuperação híbrida diretamente através de retrieve_evidence;
3. seleciona Evidence IDs e conserva a versão documental escolhida pelo retrieval;
4. envia apenas os Evidence Blocks selecionados para geração;
5. exige uma resposta candidata estruturada;
6. decompõe a resposta candidata em afirmações atómicas;
7. valida cada afirmação através de validate_claim_semantics;
8. remove, qualifica ou reformula afirmações que não possam ser apresentadas como factos;
9. reconstrói a resposta final com citações derivadas dos Evidence IDs validados;
10. devolve confiança, revisão humana e metadados suficientes para auditoria.

O orquestrador chama os serviços Python existentes diretamente. Não faz chamadas HTTP internas ao endpoint de pesquisa ou ao endpoint de validação.

## Limites da Fase 4

Incluído:

- pergunta textual em português ou noutra língua suportada pelo modelo configurado;
- recuperação híbrida sobre Evidence Blocks;
- geração condicionada aos blocos recuperados;
- extração de afirmações atómicas;
- validação semântica individual;
- citações por Evidence ID;
- confiança por afirmação e global;
- política de falha segura;
- endpoint POST /api/evidence/answer;
- testes unitários, de contrato e de integração.

Fora do âmbito:

- persistência durável da resposta final como conhecimento;
- grafo de conhecimento;
- atualização autónoma da base documental;
- visualizador PDF ou interface conversacional completa;
- validação jurídica, factual externa ou revisão humana automática;
- geração de inferências apresentadas como factos documentados;
- chamadas a fontes externas para completar lacunas.

## Contrato de entrada

O endpoint recebe:

~~~json
{
  "question": "Qual é o enquadramento aplicável?",
  "max_evidence": 8,
  "candidate_limit": 250,
  "minimum_score": 0.05,
  "source_id": null,
  "version_hash": null
}
~~~

Regras:

- question é obrigatória, não vazia e limitada a 10 000 caracteres;
- max_evidence assume 8 e não pode ultrapassar 20;
- candidate_limit não pode ser inferior a max_evidence;
- source_id e version_hash são filtros opcionais;
- o cliente não fornece Evidence IDs para iniciar o fluxo;
- filtros explícitos de versão continuam a ser respeitados pelo retrieval;
- nenhum parâmetro do cliente pode desativar a validação semântica ou a política de falha segura.

## Contrato da resposta final

A resposta segue esta forma lógica:

~~~json
{
  "answer": "Texto final auditável.",
  "claims": [
    {
      "claim_id": "CLM_001",
      "text": "Afirmação atómica.",
      "kind": "fact",
      "evidence_ids": ["EV_123", "EV_456"],
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
      "document_version_hash": "sha256",
      "pdf_page": 12,
      "printed_page": "10",
      "section_path": ["Capítulo I"],
      "text": "Excerto usado para suportar a afirmação."
    }
  ],
  "overall_confidence": 0.87,
  "requires_human_review": false,
  "status": "answered",
  "audit": {
    "selected_evidence_ids": ["EV_123", "EV_456"],
    "retrieval_scores": {},
    "embedding_model": "configured-model",
    "direct_threshold": 0.82,
    "partial_threshold": 0.58,
    "pipeline_version": "phase-4"
  }
}
~~~

O campo evidence_ids é a ligação canónica entre uma afirmação e a evidência. O campo citations é uma projeção enriquecida com os metadados dos Evidence Blocks; não deve criar uma segunda relação independente.

Os identificadores devolvidos na resposta têm de pertencer ao conjunto recuperado e validado. Qualquer identificador produzido pelo modelo que não pertença a esse conjunto invalida a afirmação candidata.

## Geração estruturada

O fornecedor LLM deve receber:

- a pergunta original;
- os Evidence Blocks selecionados;
- os respetivos Evidence IDs;
- instruções para não usar conhecimento externo;
- um esquema de saída estruturada.

A saída candidata deve conter texto e afirmações atómicas. Texto livre que não possa ser convertido numa estrutura válida é rejeitado. A resposta candidata nunca é apresentada diretamente ao utilizador.

Na Fase 4, as afirmações geradas devem ser classificadas como fact, quote, statistic ou technical. Inference e interpretation podem existir no modelo de domínio, mas não podem ser apresentadas como factos documentados sem uma política específica de fase posterior.

## Política de validação e apresentação

- direct: a afirmação pode ser apresentada como facto, com as citações validadas;
- partial: a afirmação só pode ser apresentada com qualificação e revisão humana;
- contradicted: a afirmação não pode ser apresentada como facto; deve ser reformulada para expor o conflito ou removida;
- unsupported: a afirmação é removida ou substituída por uma declaração explícita de insuficiência de evidência;
- inference e interpretation: não são emitidas como factos nesta fase.

A resposta final nunca deve conter uma afirmação factual sem pelo menos um Evidence ID validado.

Quando existirem evidências de suporte e de contradição para a mesma afirmação, a resposta deve expor a existência do conflito e marcar requires_human_review como true. Não se deve escolher silenciosamente uma das versões.

## Confiança

A confiança de uma afirmação é derivada do resultado da validação semântica e não da confiança declarada pelo LLM.

Regra inicial:

- direct: confidence igual à confiança validada;
- partial: confidence igual à confiança validada, mas requires_human_review é true;
- contradicted e unsupported: confidence não autoriza apresentação factual e o valor efetivo para a resposta é zero;
- overall_confidence: mínimo das confianças das afirmações factuais apresentadas;
- sem afirmações factuais apresentáveis, overall_confidence é zero.

A fórmula pode ser refinada numa ADR posterior, mas qualquer alteração deve continuar a ser determinística, explícita e testável.

## Política de falha segura

- sem resultados de retrieval: não gerar uma resposta factual; devolver status insufficient_evidence;
- falha do modelo de embeddings: devolver erro controlado ou insufficient_evidence, nunca uma resposta não validada;
- falha do LLM: devolver erro controlado, sem expor resposta parcial;
- saída estruturada inválida: rejeitar a resposta candidata e não fazer fallback para texto livre;
- Evidence ID desaparecido entre retrieval e validação: abortar a resposta e registar o identificador;
- evidências de versões incompatíveis: respeitar a rejeição da Fase 3;
- resposta vazia depois da reparação: devolver insufficient_evidence;
- exceções inesperadas: não apresentar a resposta candidata ao utilizador.

Os erros técnicos devem ser distinguíveis de insufficient_evidence para permitir diagnóstico sem transformar uma falha operacional em falsa conclusão epistemológica.

## Auditoria e observabilidade

Cada execução deve conservar, pelo menos em memória durante a resposta e em logs estruturados sem segredos:

- pergunta ou identificador seguro da pergunta;
- Evidence IDs selecionados;
- scores do retrieval;
- modelo de embeddings;
- limiares usados;
- afirmações candidatas;
- resultado da validação por afirmação;
- decisões de remoção, qualificação ou reformulação;
- estado final e necessidade de revisão humana;
- duração de cada etapa;
- versão do pipeline.

O logging não deve incluir credenciais, prompts que contenham segredos ou conteúdo documental além do necessário para diagnóstico local.

## Critérios de aceitação

A implementação só pode ser considerada concluída quando:

1. uma pergunta com evidência suficiente produz uma resposta citada;
2. uma pergunta sem evidência produz insufficient_evidence;
3. uma resposta com uma afirmação válida e outra inválida não apresenta a inválida como facto;
4. evidência contraditória é preservada como conflito e exige revisão;
5. Evidence IDs inexistentes não são aceites;
6. versões incompatíveis não são misturadas;
7. falhas do LLM e dos embeddings não geram respostas parciais;
8. todas as citações correspondem a Evidence Blocks recuperados;
9. a confiança global é compatível com as classificações individuais;
10. a resposta final pode ser reconstruída a partir dos metadados de auditoria.

## Consequências

O Intelos passa a ter um percurso verificável entre pergunta, evidência, geração, afirmações e resposta final. A resposta deixa de ser apenas texto produzido por um modelo e passa a ser um artefacto com relações explícitas e estados epistemológicos.

O custo é maior latência, maior complexidade de testes e possibilidade de respostas incompletas quando a evidência é insuficiente. Esse comportamento é intencional e está alinhado com a regra de não apresentar como facto uma afirmação que não tenha sido validada.
