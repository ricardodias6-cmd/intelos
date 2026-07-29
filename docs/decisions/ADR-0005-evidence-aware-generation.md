# ADR-0005: Evidence-Aware Generation

## Estado

Aceite para implementação na Fase 5.

## Contexto

A Fase 4 já condiciona a geração aos Evidence Blocks recuperados, mas uma resposta candidata pode conter claims sem suporte, com Evidence IDs inválidos ou em conflito. A validação posterior impede que essas claims sejam apresentadas, mas o utilizador ainda pode receber uma resposta incompleta quando uma reformulação segura seria possível.

## Decisão

A geração passa a ter uma política de regeneração limitada:

1. o modelo recebe apenas os Evidence Blocks selecionados;
2. cada claim candidata é validada individualmente;
3. claims sem suporte, contraditórias, sem Evidence IDs ou com IDs fora do conjunto recuperado são rejeitadas;
4. o modelo recebe feedback estruturado sobre as rejeições;
5. o modelo pode substituir as claims rejeitadas, mantendo as válidas;
6. o número de tentativas é limitado e configurável;
7. depois do limite, claims rejeitadas permanecem auditadas mas nunca são apresentadas como factos.

A regeneração não pode introduzir novos Evidence IDs, desativar a validação ou fazer fallback para texto livre.

## Contrato

O pedido aceita o campo regeneration_attempts, limitado a duas tentativas adicionais. O valor por defeito é uma tentativa adicional.

O feedback de regeneração inclui apenas o texto da claim rejeitada, os Evidence IDs usados e o motivo técnico da rejeição. O conteúdo documental continua a ser tratado como dados, nunca como instruções.

## Consequências

Claims válidas podem ser preservadas enquanto frases rejeitadas são reformuladas. A latência pode aumentar em até duas chamadas ao modelo, mas o limite explícito impede ciclos infinitos e mantém o comportamento fail-closed.
