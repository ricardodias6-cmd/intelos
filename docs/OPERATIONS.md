# Operação local do Intelos

Este documento define o procedimento mínimo de operação do Intelos como aplicação privada, local e de utilizador único.

## Instalação e atualização

A instalação canónica está em [services/knowledge-engine/README.md](../services/knowledge-engine/README.md).

A partir de `services/knowledge-engine`:

```bash
cp .env.example .env
# preencher todos os segredos obrigatórios
docker compose config --quiet
docker compose build open_notebook
docker compose up -d
curl --fail http://127.0.0.1:5055/health
```

Para atualizar a partir de uma revisão validada:

```bash
git pull --ff-only
docker compose build open_notebook
docker compose up -d
```

Não executar `docker compose down -v` durante uma atualização: isso remove volumes nomeados e pode destruir dados.

## Credenciais e segredos

- manter `.env` apenas na máquina local e nunca no Git;
- usar valores aleatórios longos para `OPEN_NOTEBOOK_ENCRYPTION_KEY`, `OPEN_NOTEBOOK_PASSWORD` e `SURREAL_PASSWORD`;
- proteger o ficheiro: `chmod 600 .env`;
- preservar a chave de encriptação: mudar essa chave torna as credenciais de fornecedores já guardadas ilegíveis;
- manter as portas bindadas a `127.0.0.1`; não expor a aplicação ou SurrealDB na rede sem revisão de segurança;
- não incluir tokens, respostas, prompts ou texto documental em logs, issues ou backups não protegidos.

## Backup

Parar a aplicação antes do backup para obter um snapshot consistente:

```bash
docker compose stop open_notebook surrealdb
tar --xattrs --acls -czf intelos-backup-$(date +%Y%m%d-%H%M%S).tar.gz \
  .env surreal_data notebook_data
docker compose start surrealdb open_notebook
```

Guardar o arquivo de backup cifrado, com controlo de acesso separado. O backup deve incluir:

- `surreal_data/`, que contém a base de dados;
- `notebook_data/`, que contém documentos e artefactos locais;
- uma cópia protegida de `.env`, incluindo a chave de encriptação.

Nunca publicar estes arquivos num repositório ou partilha sem encriptação.

## Restauro

1. parar os dois serviços;
2. preservar os diretórios atuais como cópia de segurança;
3. extrair o arquivo no diretório `services/knowledge-engine`;
4. confirmar que `.env` contém a mesma chave de encriptação;
5. iniciar os serviços e verificar saúde e autenticação;
6. abrir um notebook, confirmar fontes, notas e histórico de auditorias;
7. executar uma pergunta de teste e confirmar que surge um novo `answer_id`.

Exemplo:

```bash
docker compose stop open_notebook surrealdb
mv surreal_data surreal_data.before-restore
mv notebook_data notebook_data.before-restore
tar -xzf intelos-backup-YYYYMMDD-HHMMSS.tar.gz
docker compose up -d
curl --fail http://127.0.0.1:5055/health
```

Se o restauro falhar, parar novamente os serviços, repor os diretórios `.before-restore` e recolher os logs sem os publicar.

## Retenção e privacidade

O Intelos é local e pessoal, mas os relatórios de auditoria podem conter respostas, claims e excertos de evidência. A política mínima recomendada é:

- conservar apenas documentos, notas e relatórios necessários;
- rever e eliminar fontes duplicadas ou obsoletas;
- incluir os diretórios de dados na mesma política de retenção;
- destruir backups fora do período definido;
- não enviar conteúdo documental para serviços externos sem decisão explícita e configuração do fornecedor;
- tratar `answer_id`, `audit_id`, nomes de ficheiros e logs como informação potencialmente sensível.

A remoção de uma fonte deve ser acompanhada de verificação de frescura e, quando aplicável, revalidação dos relatórios afetados.

## Recuperação após falhas

```bash
docker compose ps
docker compose logs --tail=200 open_notebook surrealdb
curl --fail http://127.0.0.1:5055/health
curl --fail http://127.0.0.1:5055/health/ready
docker compose restart open_notebook
```

Se a base de dados não estiver pronta, não apagar os dados: confirmar espaço em disco, credenciais, permissões dos diretórios e logs do SurrealDB. Usar o procedimento de restauro quando a recuperação normal não for suficiente.

## Checklist de aceitação operacional

- [ ] `.env` existe, está protegido e os segredos não estão versionados;
- [ ] portas acessíveis apenas em localhost;
- [ ] backup recente restaurado com sucesso numa cópia de teste;
- [ ] upload/importação concluído;
- [ ] Chat limitado às fontes selecionadas;
- [ ] auditoria abre pelo `answer_id`;
- [ ] revalidação produz novo `answer_id` e `audit_id`;
- [ ] histórico mantém o relatório original e o novo;
- [ ] health/readiness e logs não expõem conteúdo sensível.
