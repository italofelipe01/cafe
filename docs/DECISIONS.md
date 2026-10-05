# Registro de decisões

Decisões de arquitetura e processo que não se deduzem do código. Cada item traz a escolha, o
motivo, o custo aceito e a regra que resulta dela. Decisão superada não é apagada: ganha nota
dizendo o que a substituiu.

As decisões de 2026-08-10 foram registradas depois, a partir dos commits da reforma daquele dia
(`ae1e0cc` a `f9f7d63`) e do texto da 1.0.0 no CHANGELOG.

## 2026-08-10 — O formulário de pedido é público

**Motivo:** quem está numa sala de reunião precisa pedir sem credencial.
**Custo:** qualquer um na rede pode abrir pedidos. Isso é contido por limite de requisições
(`RATELIMIT_ORDER`) e pela validação de escritório, sala e quantidade no serviço.
**Regra:** só `/copa`, `/admin` e as APIs internas exigem login. Um pedido nunca depende de sessão.

## 2026-08-10 — Dois perfis com senha de ambiente, sem cadastro de usuários

**Motivo:** o risco imediato era o portal ficar administrável por qualquer dispositivo da rede
com `APP_HOST=0.0.0.0`. Um cadastro de usuários resolveria mais do que o problema pedia.
**Custo:** a auditoria registra perfil e IP, não pessoa. Senhas não têm hash porque vêm do
ambiente e são comparadas em tempo constante.
**Regra:** `admin` herda `copa`. Identidade individual, se um dia for necessária, substitui
`app/security.py` inteiro, não se remenda nele.

## 2026-08-10 — Produção recusa subir com configuração insegura

**Motivo:** uma chave de sessão previsível permite forjar sessão, e um perfil sem senha deixaria
o painel inacessível ou, pior, aberto.
**Regra:** fora de `development` e `testing`, `Config.validate` levanta erro se `SECRET_KEY` for a
padrão ou se faltar `ADMIN_PASSWORD` ou `COPA_PASSWORD`. *Corrigido em 2026-10-05: o código
decidia por `DEBUG`, e não pelo ambiente (ver "Vazio é padrão; validação por ambiente").*

## 2026-08-10 — A semeadura é aditiva

**Motivo:** o seed rodava a cada boot e reescrevia nome, tipo, ordem e status do catálogo,
desfazendo o trabalho da administração a cada reinício.
**Custo:** corrigir um item já semeado exige a tela de administração ou uma migration de dados.
Editar `seed.py` não basta.
**Regra:** `seed_database()` só cria o que falta. Verificado por `tests/test_seed.py` e pelo CI,
que roda `flask init-db` duas vezes e exige zero criações na segunda.

## 2026-08-10 — Esquema versionado com Alembic

**Motivo:** `db.create_all()` não evolui um banco existente, então cada ambiente divergia.
**Custo:** toda mudança de modelo exige gerar e commitar uma migration.
**Regra:** em produção `AUTO_CREATE_DB=False` e o esquema vem de `flask db upgrade`. O CI roda
`flask db check` e falha se modelo e migrations divergirem. *Ampliado em 2026-10-05: o próprio
servidor aplica as migrations ao subir (ver "Migrations na subida do servidor").*

## 2026-08-10 — Rotas finas, regra em `services.py`

**Motivo:** validação e acesso a dados estavam repetidos em seis telas de administração.
**Regra:** rota traduz HTTP e chama serviço. Erro de negócio é `ServiceError`/`NotFoundError`,
com a mensagem pronta para a tela.

## 2026-08-10 — Nenhum recurso de terceiros no navegador

**Motivo:** permite uma Content-Security-Policy sem origem externa e sem `unsafe-inline`.
**Custo:** a fonte Fedra Sans Pro, comercial, fica versionada em `app/static/font/`. A licença
precisa ser confirmada antes de publicar o repositório (ver `NOTICE.md`). *Superado em
2026-09-18: a fonte saiu junto com a identidade anterior (ver "Identidade própria").*
**Regra:** o único script inline é o de tema, liberado por nonce a cada requisição. Nada de CDN.

## 2026-08-10 — Configuração lida na criação da aplicação

**Motivo:** ler `os.environ` no import de `config` fazia qualquer ajuste posterior ser ignorado,
e `DevelopmentConfig`/`ProductionConfig` nunca eram instanciados.
**Regra:** `resolve_config()` escolhe a classe por argumento, `APP_ENV` ou `FLASK_ENV`, e
`init_app` aplica o ambiente dentro de `create_app()`.

## 2026-08-10 — Versão derivada dos commits

**Motivo:** o histórico já seguia Conventional Commits. Escolher o número à mão era uma decisão
a mais, e sujeita a erro.
**Regra:** python-semantic-release a cada push para `main`. Versão e CHANGELOG não se editam à
mão. Processo em [RELEASE.md](RELEASE.md).

## 2026-08-10 — Históricos unificados por merge, não por reescrita

**Motivo:** a `main` do GitHub (PRs #1 a #7) e a branch local da reforma não tinham commit em
comum. Um merge (`7be83a5`) liga as duas sem reescrever nada no remoto.
**Custo:** o push do merge sobrescreveu o commit de release `6144b51`, e a tag `v1.0.0` ficou
fora da `main`. Ver a decisão de 2026-09-18.

## 2026-09-18 — Um único gate, chamado pelo release

**Motivo:** o release era disparado por `workflow_run` ao fim do CI. Isso tinha três problemas:
ele fazia checkout da ponta da `main`, e não do commit verificado; o filtro `branches: [main]`
olha a branch de origem, então um PR vindo da `main` de um fork também disparava o release; e a
relação entre os dois workflows só aparecia na aba Actions.
**Custo:** checks de PR mudam de nome (`test (3.11)` vira `Testes (Python 3.11)`). Proteção de
branch que exija os nomes antigos precisa ser atualizada.
**Regra:** `quality.yml` roda em PR para `main` e por `workflow_call`. `release.yml` roda em push
para `main`, chama o gate e só versiona com `needs: quality`, sobre o SHA do push. O gate ganhou
`pyright` e `node --check`. Actions pinadas por SHA e atualizadas pelo Dependabot. Adaptado do
repositório portal-contabilidade.

## 2026-09-18 — A tag `v1.0.0` volta para a `main`

**Motivo:** com a tag órfã, o PSR recalcula a partir do zero, chega à 1.0.0 já publicada e não
lança mais nenhuma versão. Os três `fix` posteriores (`202f150`, `c77bbcd`, `3977633`) nunca
seriam publicados.
**Regra:** a tag vai para `7be83a5`, cuja árvore é idêntica à base do release. Simulado
localmente: a próxima versão passa a ser 1.0.1. Nunca reescrever a `main` depois de uma release.

## 2026-09-18 — Identidade própria: Copa Pronta

**Motivo:** o projeto vai virar público e não pode carregar nome, logo, paleta, fonte ou dados
da empresa onde nasceu.
**Custo:** a fonte do sistema no lugar da Fedra Sans Pro muda um pouco o desenho do texto. Os
escritórios e salas do catálogo inicial agora são fictícios; um banco persistente já semeado não
perde nada, mas ganharia os fictícios se `flask init-db` rodasse de novo sobre ele.
**Regra:** marca em SVG inline pintada por `--color-*`; `--color-accent` é fundo com texto branco
e `--color-accent-text` é o acento como texto, que clareia no tema escuro. Nenhum arquivo de
fonte, logo ou dado de terceiro versionado.

## 2026-10-05 — Vazio é padrão; validação por ambiente

**Motivo:** o README mandava copiar `.env.example` para `.env`, e o portal deixava de subir: o
modelo trazia `DEBUG=false` e senhas em branco, e uma variável vazia substituía a senha de
desenvolvimento por nada. Além disso, `validate` era pulado sempre que `DEBUG` estava ligado,
então `APP_ENV=production` com `DEBUG=true` subia com a chave de sessão conhecida.
**Regra:** variável definida mas vazia vale o padrão do ambiente (`config.env_raw`). A validação
segue `REQUIRE_SECURE_CONFIG` da classe do ambiente, nunca `DEBUG`. Chaves que já apareceram em
arquivo versionado (`INSECURE_SECRET_KEYS`) são recusadas como a padrão.

## 2026-10-05 — Migrations na subida do servidor

**Motivo:** o uso real é uma máquina do escritório, sem equipe de operação. Exigir
`flask db upgrade` e `flask init-db` a cada atualização era o passo manual que mais falhava.
**Custo:** com várias instâncias subindo juntas, duas podem tentar migrar ao mesmo tempo; nesse
cenário `AUTO_MIGRATE=false` e `flask prepare-db` no passo de release.
**Regra:** `AUTO_MIGRATE` (padrão em produção) é executado pelo `run.py`, e não por
`create_app()`, para que `flask db ...` faça só o que se pede. A semeadura automática só roda
sobre banco vazio: num banco em uso, a aditiva recriaria um escritório renomeado ao lado do novo.
Banco com tabelas e sem `alembic_version` (criado por `create_all`) para a subida com a instrução
de `flask db stamp head`, em vez de adivinhar.

## 2026-10-05 — `run.py --setup` gera a configuração de uso contínuo

**Motivo:** cada instalação precisava inventar `SECRET_KEY` e senhas, escolher banco e lembrar
de `SESSION_COOKIE_SECURE=false` em HTTP — sem isso o login é aceito e não se mantém.
**Regra:** `--setup` grava um `.env` de produção com segredos aleatórios, SQLite em `instance/`,
`AUTO_MIGRATE`, escuta em `0.0.0.0` e cookie não seguro, e nunca sobrescreve um `.env` existente.
O `run.py` avisa na subida quando a configuração sobe mas não vai funcionar como se espera.

## 2026-10-05 — Pedido idempotente e Post/Redirect/Get

**Motivo:** a confirmação era renderizada na resposta do POST. F5 nela, um duplo clique (a
interceptação de envio deixava o segundo clique passar) ou um reenvio por rede instável abriam
outro pedido, e a copa atendia duas vezes.
**Custo:** coluna `order.request_token` com índice único, e a confirmação passou a ser uma página
(`/pedido/<id>`) que só abre para o navegador que fez o pedido.
**Regra:** o formulário leva `request_token`; o mesmo token devolve o pedido original. Token
malformado não recusa o pedido, só desliga a proteção naquele envio. O JavaScript bloqueia o
segundo envio e troca o token quando a página volta do histórico, porque ali sai outro pedido.

## 2026-10-05 — Link direto e QR code por sala, com `segno`

**Motivo:** escolher escritório e sala a cada pedido é o passo mais lento para quem está numa
reunião, e o tablet fixo da sala repetia a escolha todo dia.
**Custo:** uma dependência nova. O `segno` é Python puro, sem dependência nativa e sem serviço
externo, então funciona offline e não muda a CSP.
**Regra:** `/pedido/sala/<id>` usa o id, que não muda quando a sala é renomeada. O endereço dos
QR codes vem de `PUBLIC_BASE_URL` ou da requisição, e a página avisa quando ele só abre na
própria máquina. As cores do QR são fixas (`--color-qr-*`): a câmera precisa de escuro sobre
claro nos dois temas.

## 2026-10-05 — Uma imagem Docker como caminho para a nuvem

**Motivo:** levar o portal para fora da rede local não pode virar um segundo projeto.
**Regra:** o `Dockerfile` roda o mesmo `run.py`. A porta vem de `PORT` (a variável das
plataformas; `APP_PORT`, quando definida, vence), `postgres://` é convertido para o driver
instalado, `TRUST_PROXY_HOPS` liga o `ProxyFix` e `RATELIMIT_STORAGE_URI` tira o limite da
memória do processo. O CI constrói a imagem, confere que ela recusa subir sem segredos e que
responde `/health` depois de migrar.

## 2026-10-05 — SQLite em WAL e com chave estrangeira

**Motivo:** no modo padrão do SQLite, cada gravação de pedido travava as leituras do painel da
copa, que consulta a cada 10 segundos; e chave estrangeira não era verificada.
**Custo:** os arquivos `-wal` e `-shm` ao lado do banco, e copiar só o `.db` com o servidor no ar
deixou de ser backup confiável.
**Regra:** os pragmas são aplicados a cada conexão SQLite (`app/extensions.py`). Backup é
`flask backup-db`, que usa a API de backup do SQLite e mantém as cópias mais novas.

## 2026-10-05 — Cor de sucesso acessível

**Motivo:** o verde `#27ae60` com texto branco ficava em 2,9:1, abaixo do mínimo do WCAG até
para texto grande — e era a cor do botão "Concluir", o mais usado pela copa.
**Regra:** `--color-success` é `#1E7A46` (5,3:1 com branco); `--color-success-text` clareia no
tema escuro. As cores literais que restavam fora do `:root` viraram variáveis.
