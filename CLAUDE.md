# Copa Pronta — Guia para o Claude

Contexto operacional deste repositório. Leia antes de propor código, investigar bug ou
desenhar feature. O README descreve o produto para quem opera; este arquivo descreve as
regras para quem altera o código. Decisões e seus motivos estão em
[docs/DECISIONS.md](docs/DECISIONS.md); versionamento e release, em
[docs/RELEASE.md](docs/RELEASE.md); instalação contínua, backup e nuvem, em
[docs/DEPLOY.md](docs/DEPLOY.md).

## O que é

Portal Flask interno para pedir itens de copa (café, água, limpeza da sala) por sala de
reunião. Três públicos:

- **Quem está na sala** faz o pedido em `/`, sem login, escolhendo escritório e sala, ou
  direto pelo link/QR code da sala (`/pedido/sala/<id>`).
- **A copa** acompanha os pendentes em `/copa`, que se atualiza sozinho, mostra a espera de
  cada pedido e avisa os novos, e conclui cada pedido.
- **A administração** mantém escritórios, salas e insumos em `/admin`, consulta e exporta o
  histórico e imprime os QR codes das salas.

O alvo principal é rodar **offline** numa máquina da rede local, com o mínimo de passo
manual (`run.py --setup` uma vez; migrations aplicadas na subida). A mesma imagem Docker
leva o portal para a nuvem.

## Stack e runtime

- Python **3.11+** (CI em 3.11, 3.12 e 3.13; desenvolvimento local em 3.13).
- Flask com Application Factory, Flask-SQLAlchemy (estilo tipado `Mapped`), Flask-Migrate
  (Alembic), Flask-WTF (CSRF), Flask-Limiter. Servidor Waitress.
- SQLite. O padrão é **em memória**, que se recria a cada subida. Em arquivo, roda em WAL e
  com chave estrangeira ligada (`app/extensions.py`). PostgreSQL é suportado para nuvem
  (`requirements-postgres.txt`).
- Sem framework de frontend e sem build: Jinja + CSS + JS vanilla, e nada carregado de
  terceiros (a CSP não tem nenhuma origem externa). QR codes são SVG gerados no servidor
  pelo `segno` (Python puro).
- Docker: `Dockerfile` (mesmo `run.py`, lê `PORT`) e `docker-compose.yml` com volume.
- Configuração 100% por variável de ambiente, lida em `create_app()` (e não no import).
  `.env.example` é a lista canônica.
- Plataforma de desenvolvimento: **Windows / PowerShell**. O CI roda em Ubuntu.

## Comandos

```powershell
pip install -r requirements.txt -r requirements-dev.txt
python run.py                                    # sobe em http://127.0.0.1:5000
python run.py --background                       # destacado; saída em cafe_server.log
python run.py --setup                            # gera .env de uso contínuo (não sobrescreve)
python -m unittest discover -s . -p "test_*.py"  # suíte (~150 testes, ~10s)
ruff check .                                     # lint
pyright                                          # tipos
node --check app/static/script.js                # sintaxe JS (idem dashboard.js)

$env:FLASK_APP="app:create_app"
flask db upgrade          # aplica o esquema num banco persistente
flask db migrate -m "..." # gera migration depois de mudar app/models.py
flask init-db             # semeia o catálogo (aditivo)
flask prepare-db          # migrations + catálogo inicial só se o banco estiver vazio
flask backup-db           # cópia consistente do SQLite em instance/backups (rotativa)
flask check-config        # configuração efetiva, sem revelar segredos

docker build -t copa-pronta .                    # imagem; o CI sobe e consulta /health
```

Senhas de desenvolvimento: `admin` e `copa`. Fora de `development` elas não existem.

## Mapa do código

```text
app/
├── __init__.py     create_app(): logging, ProxyFix, extensões, cabeçalhos de segurança
│                   (CSP com nonce), páginas de erro, comandos CLI, audit() e
│                   prepare_database() (migrations + semeadura do banco vazio)
├── extensions.py   db, migrate, csrf, limiter, ModelBase e pragmas do SQLite
├── models.py       Office → Space; Order → OrderItem → Product. local_now() em Brasília
├── routes.py       blueprint "main": rotas finas que só traduzem HTTP
├── services.py     regra de negócio e acesso a dados; ServiceError / NotFoundError
├── security.py     perfis admin/copa, comparação de senha em tempo constante,
│                   login_required, safe_redirect_target
├── seed.py         catálogo inicial (escritórios, salas, insumos), semeadura aditiva
├── qrcodes.py      SVG do QR code de cada sala (segno)
├── backup.py       backup consistente do SQLite, com rotação
├── static/         script.js (global), dashboard.js (copa), styles.css, icon.svg/.png,
│                   manifest.webmanifest
└── templates/      base.html, pedido (index, sala_form, confirm_pedido), copa_dashboard,
                    login, admin/* (inclui history e qrcodes), errors/*
config.py           Config / Development / Testing / Production, resolve_config()
run.py              entrada do servidor (local e Docker): Waitress, AUTO_MIGRATE,
                    --background, --setup, avisos de configuração na subida
Dockerfile          imagem de produção; docker-compose.yml com SQLite em volume
migrations/         Alembic. versions/ é o histórico do esquema, sempre versionado
tests/              unittest. base.AppTestCase sobe create_app("testing") em memória;
                    test_operation cobre config, preparo do banco, backup e run.py
```

## Regras do código

Quebrar uma destas é regressão, mesmo com os testes verdes:

1. **Rotas orquestram, não decidem.** Validação, consulta e escrita moram em
   `app/services.py`. Erro de negócio é `ServiceError`/`NotFoundError`, com mensagem já
   escrita para quem lê na tela.
2. **A semeadura é aditiva.** `app/seed.py` cria o que falta e nunca altera nome, tipo, ordem
   ou status de registro existente, que pertencem a quem administra o portal.
   `tests/test_seed.py` cobre o reinício sobre banco persistente.
3. **Mudou `app/models.py`, gere a migration no mesmo commit.** O CI roda `flask db check`.
4. **`Product.form_key` nunca muda depois de criado.** Renomear o insumo não pode invalidar
   um formulário aberto no navegador de alguém.
5. **Pedido referencia o produto, não copia o nome.** O histórico mostra o nome atual.
6. **Nada de origem externa no frontend.** Sem CDN, fonte remota, `unsafe-inline` ou script
   inline sem o `nonce` de `csp_nonce()`.
7. **Toda cor sai de uma variável `--color-*`** de `styles.css`, para os dois temas
   funcionarem. Margem full-bleed deriva de `--panel-padding-x/y`.
8. **Cada bloco de `script.js` confere se o elemento âncora existe**, porque o mesmo arquivo
   serve a todas as telas.
9. **Todo formulário POST leva `csrf_token`**; requisição JSON que altera estado envia
   `X-CSRFToken`. Há teste que falha se algum formulário ficar sem.
10. **O pedido funciona sem JavaScript.** O script só melhora (filtra salas, valida inline).
11. **Horário é o de Brasília**, gravado sem tzinfo por `local_now()`. Espera e duração
    são calculadas no servidor (`Order.waiting_seconds`), nunca pelo relógio do navegador.
12. **Nenhum segredo em arquivo versionado.** `.env` fica fora do git; o modelo é `.env.example`.
13. **Envio de pedido é idempotente e termina em redirect.** O formulário leva
    `request_token`; `services.create_order` devolve o pedido existente para o mesmo token, e
    a rota redireciona para `/pedido/<id>` (Post/Redirect/Get). POST público novo que crie
    registro segue o mesmo padrão.
14. **Endereço no JavaScript vem do servidor.** Use `data-*` preenchido por `url_for`, nunca
    caminho fixo como `'/api/orders'`: atrás de proxy com prefixo o caminho muda.
15. **Variável vazia vale o padrão do ambiente** (`config.env_raw`). A validação de produção
    é por ambiente (`REQUIRE_SECURE_CONFIG`), nunca por `DEBUG`.

## Autenticação e perfis

Não há cadastro de usuários: cada perfil tem uma senha vinda do ambiente.

| Perfil | Senha | Acessa |
| --- | --- | --- |
| `copa` | `COPA_PASSWORD` | `/copa`, `/api/orders`, `/api/complete_order/<id>` |
| `admin` | `ADMIN_PASSWORD` | tudo (o perfil admin também recebe `copa`) |

O formulário de pedido é público de propósito. A confirmação `/pedido/<id>` só abre para o
navegador que enviou o pedido (lista `recent_orders` na sessão). Rota protegida usa
`@login_required(ROLE_...)`: sem sessão, a API responde 401 JSON e a página redireciona para
`/login?next=`. Ação administrativa relevante chama `audit()`, que registra perfil e IP, não
pessoa.

Em produção (`APP_ENV=production`) a aplicação **recusa subir** com `SECRET_KEY` padrão ou sem
as duas senhas, e não cria esquema no boot (`AUTO_CREATE_DB=False`, use `flask db upgrade`).

## Testes

- `tests/base.py`: `AppTestCase` com `create_app("testing")` (SQLite em memória, CSRF e rate
  limit desligados, senhas `admin-teste`/`copa-teste`) e atalhos `login_as_admin()`,
  `login_as_copa()`, `submit_order()` e `fetch()`.
- `submit_order()` não segue o redirect: o envio bem-sucedido responde `302` para
  `/pedido/<id>`.
- Os testes de segurança religam CSRF quando é isso que testam. Os de semeadura e de preparo
  do banco usam arquivo temporário, porque o cenário é justamente o reinício sobre banco
  persistente. Quem chama `prepare_database()` em teste faz patch de
  `logging.config.fileConfig`, que o `env.py` do Alembic executa a cada migration.
- Toda regra nova precisa de teste que falhe contra o atalho correspondente: permissão testa
  o perfil na rota, não a visibilidade do botão.

## Gates antes de fechar qualquer tarefa de código

São os mesmos do `.github/workflows/quality.yml`, que roda em PR para `main` e, a cada push
para `main`, dentro do `release.yml`, antes de versionar:

1. `ruff check .`
2. `pyright`
3. `node --check` em `app/static/*.js` (se mexeu em JS)
4. `python -m unittest discover -s . -p "test_*.py"`
5. Se mexeu em modelo: `flask db check` contra um banco com `flask db upgrade` aplicado
6. Se mexeu em `Dockerfile`, dependências ou `run.py`: `docker build` e subir a imagem (o CI
   faz isso no job "Imagem Docker")

Se um gate não puder rodar, a resposta final diz qual, por quê e o risco que fica.

## Commits, versão e release

- Conventional Commits em português, **sem acentos no assunto**: `feat(admin): ...`,
  `fix(ui): ...`, `refactor(services): ...`, `docs: ...`, `test: ...`, `ci: ...`.
  Escopos usados: `admin`, `copa`, `ui`, `security`, `services`, `seed`, `db`, `config`,
  `server`, `deps`, `repo`.
- `fix`/`perf` → patch, `feat` → minor, `BREAKING CHANGE:` no rodapé (ou `!`) → major.
  O resto não muda a versão.
- **Não edite `project.version` nem o `CHANGELOG.md` à mão**: o workflow de release escreve
  os dois (a entrada 1.0.0, escrita à mão, é a exceção histórica).
- **Nunca reescreva o histórico da `main`** (rebase, amend ou push forçado de algo já
  publicado). A tag precisa continuar alcançável, senão o release para. Ver
  [docs/RELEASE.md](docs/RELEASE.md).
- Nunca adicionar trailer de coautoria de IA nos commits.
- Commit e push só quando o usuário pedir.

## Armadilhas conhecidas

- O banco padrão é em memória: tudo some ao reiniciar. Para persistir, `DATABASE_URL` (ou
  `python run.py --setup`).
- Caminho relativo de SQLite parte de `instance/`: `sqlite:///copa.db` é `instance/copa.db`.
- `AUTO_CREATE_DB=True` usa `db.create_all()`, que **não** aplica migrations. Com banco
  persistente, deixe `False` e use `AUTO_MIGRATE` (ou `flask db upgrade`). Um banco criado
  por `create_all` precisa de `flask db stamp head` uma vez antes das migrations.
- `AUTO_MIGRATE` roda no `run.py`, não em `create_app()`: os comandos `flask db ...` não podem
  migrar sozinhos antes de fazer o que se pediu a eles.
- A semeadura da subida automática só roda sobre banco vazio; `flask init-db` continua
  aditivo e recriaria um escritório renomeado.
- `SESSION_COOKIE_SECURE=true` (padrão de produção) sem HTTPS: o login é aceito e não se
  mantém. Em HTTP na rede local, `false`.
- O `env.py` do Alembic chama `fileConfig` com `disable_existing_loggers=False`; sem isso,
  migrar dentro do servidor desligava o log da aplicação e a auditoria.
- `semantic-release` no Windows precisa de `$env:PYTHONUTF8="1"`: sem isso ele lê o CHANGELOG
  em cp1252 e falha com `'charmap' codec can't decode`.
- A marca do cabeçalho é SVG inline em `base.html`, não imagem: para mudar a cor dela, mude
  as variáveis, não o arquivo. `icon.svg` (favicon) tem cores fixas e o `icon.png` é gerado dele.
- `POST /get_rooms` existe só por compatibilidade; o caminho atual é `GET /api/rooms`.
