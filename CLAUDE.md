# Copa Pronta — Guia para o Claude

Contexto operacional deste repositório. Leia antes de propor código, investigar bug ou
desenhar feature. O README descreve o produto para quem opera; este arquivo descreve as
regras para quem altera o código. Decisões e seus motivos estão em
[docs/DECISIONS.md](docs/DECISIONS.md); versionamento e release, em
[docs/RELEASE.md](docs/RELEASE.md).

## O que é

Portal Flask interno para pedir itens de copa (café, água, limpeza da sala) por sala de
reunião. Três públicos:

- **Quem está na sala** faz o pedido em `/`, sem login, escolhendo escritório e sala.
- **A copa** acompanha os pendentes em `/copa`, que se atualiza sozinho, e conclui cada pedido.
- **A administração** mantém escritórios, salas e insumos em `/admin` e consulta o histórico.

## Stack e runtime

- Python **3.11+** (CI em 3.11, 3.12 e 3.13; desenvolvimento local em 3.13).
- Flask com Application Factory, Flask-SQLAlchemy (estilo tipado `Mapped`), Flask-Migrate
  (Alembic), Flask-WTF (CSRF), Flask-Limiter. Servidor Waitress.
- SQLite. O padrão é **em memória**, que se recria a cada subida.
- Sem framework de frontend e sem build: Jinja + CSS + JS vanilla, e nada carregado de
  terceiros (a CSP não tem nenhuma origem externa).
- Configuração 100% por variável de ambiente, lida em `create_app()` (e não no import).
  `.env.example` é a lista canônica.
- Plataforma de desenvolvimento: **Windows / PowerShell**. O CI roda em Ubuntu.

## Comandos

```powershell
pip install -r requirements.txt -r requirements-dev.txt
python run.py                                    # sobe em http://127.0.0.1:5000
python run.py --background                       # destacado; saída em cafe_server.log
python -m unittest discover -s . -p "test_*.py"  # suíte (~110 testes, ~10s)
ruff check .                                     # lint
pyright                                          # tipos
node --check app/static/script.js                # sintaxe JS (idem dashboard.js)

$env:FLASK_APP="app:create_app"
flask db upgrade          # aplica o esquema num banco persistente
flask db migrate -m "..." # gera migration depois de mudar app/models.py
flask init-db             # semeia o catálogo (aditivo)
flask check-config        # configuração efetiva, sem revelar segredos
```

Senhas de desenvolvimento: `admin` e `copa`. Fora de `development` elas não existem.

## Mapa do código

```text
app/
├── __init__.py     create_app(): logging, extensões, cabeçalhos de segurança (CSP com
│                   nonce), páginas de erro, comandos CLI e audit()
├── extensions.py   db, migrate, csrf, limiter e ModelBase
├── models.py       Office → Space; Order → OrderItem → Product. local_now() em Brasília
├── routes.py       blueprint "main": rotas finas que só traduzem HTTP
├── services.py     regra de negócio e acesso a dados; ServiceError / NotFoundError
├── security.py     perfis admin/copa, comparação de senha em tempo constante,
│                   login_required, safe_redirect_target
├── seed.py         catálogo inicial (escritórios, salas, insumos), semeadura aditiva
├── static/         script.js (global), dashboard.js (copa), styles.css, icon.svg/.png
└── templates/      base.html, pedido (index, sala_form, confirm_pedido), copa_dashboard,
                    login, admin/*, errors/*
config.py           Config / Development / Testing / Production, resolve_config()
run.py              entrada local: Waitress, --background, aviso de exposição na rede
migrations/         Alembic. versions/ é o histórico do esquema, sempre versionado
tests/              unittest. base.AppTestCase sobe create_app("testing") em memória
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
11. **Horário é o de Brasília**, gravado sem tzinfo por `local_now()`.
12. **Nenhum segredo em arquivo versionado.** `.env` fica fora do git; o modelo é `.env.example`.

## Autenticação e perfis

Não há cadastro de usuários: cada perfil tem uma senha vinda do ambiente.

| Perfil | Senha | Acessa |
| --- | --- | --- |
| `copa` | `COPA_PASSWORD` | `/copa`, `/api/orders`, `/api/complete_order/<id>` |
| `admin` | `ADMIN_PASSWORD` | tudo (o perfil admin também recebe `copa`) |

O formulário de pedido é público de propósito. Rota protegida usa
`@login_required(ROLE_...)`: sem sessão, a API responde 401 JSON e a página redireciona para
`/login?next=`. Ação administrativa relevante chama `audit()`, que registra perfil e IP, não
pessoa.

Em produção (`APP_ENV=production`) a aplicação **recusa subir** com `SECRET_KEY` padrão ou sem
as duas senhas, e não cria esquema no boot (`AUTO_CREATE_DB=False`, use `flask db upgrade`).

## Testes

- `tests/base.py`: `AppTestCase` com `create_app("testing")` (SQLite em memória, CSRF e rate
  limit desligados, senhas `admin-teste`/`copa-teste`) e atalhos `login_as_admin()`,
  `login_as_copa()`, `submit_order()` e `fetch()`.
- Os testes de segurança religam CSRF quando é isso que testam. Os de semeadura usam arquivo
  temporário, porque o cenário é justamente o reinício sobre banco persistente.
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

- O banco padrão é em memória: tudo some ao reiniciar. Para persistir, `DATABASE_URL`.
- `AUTO_CREATE_DB=True` usa `db.create_all()`, que **não** aplica migrations. Com banco
  persistente, deixe `False` e use `flask db upgrade`.
- `semantic-release` no Windows precisa de `$env:PYTHONUTF8="1"`: sem isso ele lê o CHANGELOG
  em cp1252 e falha com `'charmap' codec can't decode`.
- A marca do cabeçalho é SVG inline em `base.html`, não imagem: para mudar a cor dela, mude
  as variáveis, não o arquivo. `icon.svg` (favicon) tem cores fixas e o `icon.png` é gerado dele.
- `POST /get_rooms` existe só por compatibilidade; o caminho atual é `GET /api/rooms`.
