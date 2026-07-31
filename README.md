# Intelos

Plataforma privada e modular de conhecimento, decisão, produtividade e inteligência assistida por IA.

## Âmbito

O Intelos destina-se única e exclusivamente ao uso pessoal do proprietário do repositório. Não é um produto comercial, um serviço público, uma plataforma multiutilizador nem uma aplicação institucional.

## Estado do projeto

As Fases 0–10 estão implementadas, validadas e integradas na main. O sistema dispõe de ingestão documental, recuperação híbrida limitada ao contexto selecionado, respostas auditáveis, geração condicionada à evidência, grafo persistente, manutenção de versões, Copilot conversacional, deteção de frescura, superfície de auditoria e revalidação controlada.

A release inicial é privada, local e de utilizador único. Os procedimentos de instalação, backup, restauro, retenção, recuperação e release estão documentados em [services/knowledge-engine/README.md](services/knowledge-engine/README.md), [docs/OPERATIONS.md](docs/OPERATIONS.md) e [docs/RELEASE.md](docs/RELEASE.md). O contrato de auditoria está definido em [ADR-0012](docs/decisions/ADR-0012-audit-surface-and-operational-readiness.md).

A roadmap canónica está em [docs/ROADMAP.md](docs/ROADMAP.md).

## Princípios

- Privacidade e controlo dos dados
- Utilização exclusivamente pessoal
- Arquitetura modular
- Fontes verificáveis e respostas auditáveis
- Independência face a um único fornecedor de IA
- Reutilização responsável de software open source
- Separação clara entre código próprio e componentes de terceiros
