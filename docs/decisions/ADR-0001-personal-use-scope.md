# ADR-0001: Âmbito exclusivamente pessoal

- Estado: aceite
- Data: 2026-07-27

## Contexto

O Intelos será desenvolvido como uma plataforma privada de conhecimento, decisão e produtividade assistida por IA. O proprietário determinou que o projeto se destina única e exclusivamente ao seu uso pessoal.

## Decisão

O Intelos será concebido como aplicação de utilizador único.

Não serão incluídos, salvo decisão futura expressa:

- registo público de utilizadores;
- gestão de organizações ou equipas;
- faturação ou subscrições;
- isolamento entre múltiplos utilizadores;
- funcionalidades SaaS;
- distribuição pública automática;
- pressupostos de utilização institucional.

A arquitetura deve privilegiar privacidade, execução local ou privada, simplicidade operacional e controlo direto dos dados pelo proprietário.

## Consequências

- A autenticação, quando necessária, protegerá um único proprietário.
- Os cofres e áreas da aplicação poderão separar contextos, mas não representarão contas de utilizadores diferentes.
- A incorporação de componentes open source será documentada e licenciada corretamente.
- Qualquer utilização de informação profissional, sensível ou sujeita a restrições dependerá das autorizações aplicáveis e não é legitimada por esta decisão de arquitetura.
