# Intelos

Plataforma privada e modular de conhecimento, decisão, produtividade e inteligência assistida por IA.

## Âmbito

O Intelos destina-se única e exclusivamente ao uso pessoal do proprietário do repositório. Não é um produto comercial, um serviço público, uma plataforma multiutilizador nem uma aplicação institucional.

## Estado do projeto

As Fases 0–9 estão implementadas, validadas e integradas na main. As subfases 10.1–10.5 da consolidação da auditoria e prontidão operacional também estão integradas. O sistema já dispõe de ingestão documental, recuperação híbrida, respostas auditáveis, geração condicionada à evidência, grafo persistente, manutenção de versões, Copilot conversacional, deteção de frescura da evidência e superfície de auditoria.

A subfase em curso é a 10.6 — ligação Chat → Auditoria → Revalidação, com ligação automática do `answer_id`, abertura direta da auditoria, revalidação controlada e histórico por conversa. O contrato está definido em [ADR-0012](docs/decisions/ADR-0012-audit-surface-and-operational-readiness.md).

A roadmap canónica está em [docs/ROADMAP.md](docs/ROADMAP.md).

## Princípios

- Privacidade e controlo dos dados
- Utilização exclusivamente pessoal
- Arquitetura modular
- Fontes verificáveis e respostas auditáveis
- Independência face a um único fornecedor de IA
- Reutilização responsável de software open source
- Separação clara entre código próprio e componentes de terceiros
