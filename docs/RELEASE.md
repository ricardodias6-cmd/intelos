# Release inicial

## Escopo

A primeira release do Intelos é uma release local, privada e de utilizador único. Não representa aprovação para exposição pública, operação multiutilizador ou serviço SaaS.

## Conteúdo incluído

- Fases 0–9 concluídas;
- Fase 10 concluída, incluindo o ciclo Chat → Auditoria → Revalidação;
- retrieval auditável limitado ao contexto de fontes selecionadas;
- persistência de AuditReport, histórico e revalidação idempotente;
- instalação local por Docker Compose;
- backup, restauro e procedimentos de recuperação documentados.

## Critérios antes da tag

- CI do PR final verde;
- teste end-to-end persistente executado;
- backup e restauro verificados;
- `README.md` e `docs/ROADMAP.md` alinhados;
- nenhuma porta publicada fora de localhost;
- `.env` e dados pessoais fora do controlo de versões.

## Identificação

A tag inicial proposta é `v1.0.0`. Deve apontar para o commit de merge da branch final depois de todos os checks verdes. A criação da tag e da release deve ser feita apenas nesse commit imutável.
