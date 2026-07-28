# Knowledge Engine: validação e riscos residuais

Data da validação: 28 de julho de 2026

## Estado validado

O workflow `Knowledge engine smoke test` constrói a imagem local do Knowledge Engine e executa o conjunto definido em `services/knowledge-engine/docker-compose.yml` num runner Linux descartável.

A execução bem-sucedida validou:

- construção completa da imagem `intelos-knowledge-engine:local`;
- arranque do SurrealDB, API, worker e frontend;
- execução das migrações da base de dados até à versão atual;
- resposta saudável do endpoint `/health`;
- disponibilidade do frontend na porta 8502;
- autenticação ativada quando `OPEN_NOTEBOOK_PASSWORD` está definido;
- rejeição de pedidos sem autenticação e com palavra-passe errada;
- acesso autorizado com bearer password válida;
- criação de um notebook descartável através da API;
- encerramento e novo arranque integral do conjunto Docker Compose;
- preservação do notebook criado após o reinício;
- remoção dos contentores e dados descartáveis no final.

Execução de referência: GitHub Actions `Knowledge engine smoke test`, run `30335512849`, concluída com sucesso.

## Riscos residuais

### R1. Contentores executados como root

**Gravidade:** alta para utilização em produção.

O contentor `open_notebook` não define um utilizador não privilegiado e o SurrealDB é configurado com `user: root`. O smoke test confirmou que ambos são executados como root. Uma vulnerabilidade com execução de código teria, por isso, um impacto potencialmente superior dentro do contentor e sobre os volumes montados.

**Tratamento necessário:** redesenhar o entrypoint para não instalar dependências em tempo de execução, criar utilizadores dedicados sem privilégios, corrigir permissões dos volumes e executar API, worker, frontend e SurrealDB com os privilégios mínimos indispensáveis.

**Decisão atual:** aceitável apenas como bootstrap local e isolado. Não está aprovado para produção.

### R2. Dependências de imagem não fixadas por digest

**Gravidade:** média a alta.

São usados identificadores mutáveis, incluindo `surrealdb/surrealdb:v2`, `node:22-slim`, `python:3.12-slim-trixie` e `ghcr.io/astral-sh/uv:latest`. Uma reconstrução futura pode incorporar conteúdo diferente sem alteração no repositório.

**Tratamento necessário:** fixar imagens por digest, manter um processo controlado de atualização e registar a proveniência das imagens utilizadas em cada release.

### R3. Instalações e atualizações não totalmente reprodutíveis

**Gravidade:** média.

O Dockerfile executa `apt-get upgrade` durante a construção. Os pacotes de sistema obtidos dependem do estado dos repositórios no momento do build. Os runtimes opcionais de extração também podem instalar componentes e descarregar modelos em tempo de execução.

**Tratamento necessário:** usar bases fixadas por digest, reduzir atualizações implícitas, gerar inventário ou SBOM e transferir os runtimes opcionais para imagens ou etapas de construção próprias e versionadas.

### R4. Ausência de análise de vulnerabilidades da imagem e do sistema operativo

**Gravidade:** média.

As auditorias atuais cobrem dependências Python e npm. Não cobrem integralmente pacotes Debian, binários copiados de outras imagens, Node.js, ffmpeg, supervisor, SurrealDB nem o conteúdo final da imagem Docker.

**Tratamento necessário:** adicionar análise da imagem final com uma ferramenta de container scanning e bloquear vulnerabilidades críticas ou altas segundo uma política explícita de exceções.

### R5. Autenticação adequada apenas para ambiente local controlado

**Gravidade:** média quando existe exposição em rede.

A API usa uma palavra-passe estática como bearer token. O Docker Compose limita as portas a `127.0.0.1`, o que reduz a exposição no modelo local testado. Não existe TLS nativo neste conjunto e os segredos são fornecidos por variáveis de ambiente.

**Tratamento necessário:** manter as portas limitadas ao host local ou usar um reverse proxy com TLS, gestão segura de segredos, rotação de credenciais e controlo adicional de acesso antes de qualquer exposição remota.

### R6. Rotação das credenciais do SurrealDB não validada

**Gravidade:** média operacional.

No segundo arranque, o SurrealDB detetou um utilizador root já existente e não voltou a criar o utilizador indicado pelas variáveis de ambiente. Isto é esperado para preservar a base existente, mas significa que alterar apenas `SURREAL_USER` ou `SURREAL_PASSWORD` depois da inicialização não constitui, por si só, um procedimento de rotação válido.

**Tratamento necessário:** documentar e testar um procedimento explícito de rotação e recuperação das credenciais do SurrealDB.

### R7. Ausência de healthchecks declarativos no Docker Compose

**Gravidade:** média operacional.

O arranque funciona porque a API repete a ligação à base de dados e o frontend espera pela API. Contudo, o Docker Compose não define `healthcheck` para os serviços e `depends_on` não expressa prontidão funcional.

**Tratamento necessário:** adicionar healthchecks para SurrealDB, API e frontend, bem como dependências condicionadas à saúde quando suportadas.

### R8. Persistência validada apenas no cenário básico

**Gravidade:** média.

O smoke test confirma uma escrita e leitura após um reinício limpo. Não valida interrupção abrupta, corrupção, falta de espaço, concorrência elevada, migração para trás, cópia de segurança ou restauro.

**Tratamento necessário:** criar testes específicos de backup e restauro, recuperação após interrupção, migrações e concorrência antes de considerar a persistência pronta para produção.

### R9. Cobertura funcional limitada

**Gravidade:** média.

O smoke test não utiliza fornecedores externos de IA, credenciais reais, Docling, Crawl4AI, processamento de documentos extensos, geração de podcasts, execução completa dos comandos assíncronos nem fluxos browser end-to-end.

**Tratamento necessário:** manter estes cenários fora do critério de sucesso atual e adicionar suites próprias quando cada capacidade for integrada no Intelos.

### R10. Cobertura de plataforma limitada

**Gravidade:** baixa a média.

A execução validada ocorreu num runner Ubuntu x86_64. Não confirma comportamento do Docker Desktop em macOS ou Windows, sistemas ARM64, limites de memória reduzidos nem permissões de volumes nesses ambientes.

**Tratamento necessário:** acrescentar uma matriz de compatibilidade e testes nas plataformas oficialmente suportadas antes da distribuição.

## Critério de utilização

O resultado atual demonstra que o bootstrap importado constrói, arranca, autentica, escreve e preserva dados no cenário local testado. Não demonstra que o runtime está endurecido ou pronto para produção.

Qualquer integração deve preservar estes riscos como itens explícitos e não os interpretar como resolvidos pelo CI verde ou pelo smoke test bem-sucedido.
