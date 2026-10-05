<p align="center"><img src="app/static/icon.svg" width="96" height="96" alt=""></p>

# Copa Pronta

Portal Flask para solicitação de itens de copa por sala, acompanhamento operacional dos pedidos e manutenção do catálogo usado no formulário. Roda offline numa máquina da rede local, sem nenhum serviço externo, e sobe na nuvem pela mesma imagem Docker.

## Funcionalidades

- Pedido por escritório e sala, sem necessidade de login, com botões de − e + nas quantidades e observação livre ("adoçante à parte").
- Link direto de cada sala (`/pedido/sala/<id>`) e página de QR codes para imprimir e colar na porta: quem está na sala aponta a câmera e pede.
- O tablet fixo numa sala já abre com o último escritório e sala escolhidos.
- Envio idempotente: duplo clique, F5 na confirmação ou rede instável não abrem pedido duplicado para a copa.
- Catálogo dinâmico de insumos, com itens de quantidade e itens sim/não.
- Painel da copa em `/copa`, atualizado sozinho, com o tempo de espera de cada pedido, destaque em amarelo e vermelho para os atrasados, aviso sonoro, notificação do sistema e tela sempre acesa (com os alertas ligados).
- Modal próprio para concluir pedidos, sem diálogo nativo do navegador.
- Admin em `/admin` para manter escritórios, salas e insumos.
- Histórico de pedidos concluídos em `/admin/history`, com filtro por período e escritório, tempo médio de atendimento e exportação em CSV pronta para o Excel.
- Ativação/inativação de escritórios, salas e insumos, com cascata do escritório para as salas.
- Filtro de salas por escritório e busca por trecho do nome.
- Reordenação de insumos por arrastar ou pelas setas do teclado.
- Tema claro/escuro, aplicado antes da primeira pintura; a marca é um SVG inline que acompanha o tema.
- Instalável como aplicativo no tablet ou celular (manifesto web).
- Autenticação por perfil, proteção CSRF, cabeçalhos de segurança, limite de requisições e trilha de auditoria.
- Migrations com Alembic, aplicadas pelo próprio servidor ao subir, e suíte automatizada.

## Início rápido

Para experimentar (banco em memória, senhas `admin` e `copa`):

```powershell
pip install -r requirements.txt
python run.py
```

Para uso contínuo na rede local, com banco em arquivo e senhas próprias:

```powershell
pip install -r requirements.txt
python run.py --setup     # uma vez: gera o .env e mostra as senhas
python run.py             # aplica as migrations, semeia na primeira vez e sobe
```

Atualizar o portal passa a ser trocar o código e reiniciar: as migrations novas são aplicadas na subida. Iniciar com o Windows, backup do banco, HTTPS e nuvem estão em [docs/DEPLOY.md](docs/DEPLOY.md).

## Estrutura

```text
app/
  __init__.py              # Application factory, logging, cabeçalhos, erros, CLI e preparo do banco
  extensions.py            # SQLAlchemy, Migrate, CSRF, Limiter e ajustes do SQLite
  models.py                # Office, Space, Product, Order, OrderItem
  routes.py                # Rotas HTTP (finas: só traduzem requisição em serviço)
  services.py              # Regra de negócio e acesso a dados
  security.py              # Perfis, senhas e decorador de acesso
  seed.py                  # Catálogo inicial (semeadura aditiva)
  qrcodes.py               # QR codes dos links de pedido de cada sala
  static/
    dashboard.js           # JS do painel da copa
    script.js              # JS global: tema, transições, quantidades, filtros e ordenação
    styles.css             # Estilos globais
    manifest.webmanifest   # Instalação como aplicativo
    icon.svg               # Favicon e símbolo da marca
    icon.png               # Favicon para navegadores sem SVG e ícone de atalho no iOS
  templates/
    base.html              # Layout base
    login.html             # Acesso aos painéis internos
    index.html             # Pedido: seleção de escritório e sala
    sala_form.html         # Pedido: itens da sala
    confirm_pedido.html    # Confirmação do pedido
    copa_dashboard.html    # Painel da copa
    admin/                 # Telas administrativas, histórico e QR codes
    errors/                # Páginas 400, 401, 404, 429 e 500
migrations/                # Alembic: esquema versionado
tests/                     # Suíte automatizada
docs/
  DEPLOY.md                # Instalação contínua, backup, HTTPS e nuvem
  DECISIONS.md             # Decisões de arquitetura e processo, com o motivo
  RELEASE.md               # Versionamento semântico e publicação
.github/
  workflows/quality.yml    # Gate: lint, tipos, JS, testes, migrations e imagem Docker
  workflows/release.yml    # Versão, changelog, tag e GitHub Release a cada push na main
  dependabot.yml           # Atualização semanal das actions
config.py                  # Configuração por ambiente
run.py                     # Entrada do servidor (local e contêiner) e --setup
Dockerfile                 # Imagem para nuvem ou servidor com Docker
docker-compose.yml         # Contêiner com o SQLite num volume
CLAUDE.md                  # Regras do código para agentes (e para quem mais quiser)
```

## Requisitos

- Python 3.11 ou superior.
- Windows, Linux ou macOS.
- Nenhum acesso à internet depois da instalação das dependências.

## Instalação

No PowerShell:

```powershell
cd C:\repositories\cafe
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Para desenvolver, instale também as ferramentas de qualidade:

```powershell
pip install -r requirements-dev.txt
```

Se o PowerShell bloquear a ativação da venv:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\.venv\Scripts\Activate.ps1
```

## Execução

```powershell
python run.py
```

Acesse:

```text
Pedido:      http://127.0.0.1:5000/
Painel copa: http://127.0.0.1:5000/copa
Admin:       http://127.0.0.1:5000/admin
```

Em desenvolvimento, as senhas padrão são `admin` para a administração e `copa` para o painel da copa. Elas valem **apenas** no ambiente de desenvolvimento; qualquer outro ambiente exige senhas definidas por variável de ambiente.

Para rodar destacado do terminal, gravando a saída em `cafe_server.log`:

```powershell
python run.py --background
```

Para permitir acesso pelo celular na mesma rede, use `python run.py --setup` (que já escuta em `0.0.0.0` com senhas próprias) ou defina `APP_HOST=0.0.0.0` junto com `SECRET_KEY`, `ADMIN_PASSWORD` e `COPA_PASSWORD`. Ao subir, o `run.py` avisa quando a combinação não vai funcionar como se espera: ambiente de desenvolvimento exposto na rede, ou cookie seguro sem HTTPS.

## Ambientes

O ambiente é escolhido por `APP_ENV` (ou `FLASK_ENV`), e o padrão é `development`.

| Ambiente | Debug | Esquema no boot | Migrations ao subir | Senhas padrão | Cookie seguro |
| --- | --- | --- | --- | --- | --- |
| `development` | sim | `create_all` | não | sim | não |
| `testing` | não | `create_all` | não | de teste | não |
| `production` | não | não | **sim** (`AUTO_MIGRATE`) | **exigidas** | sim |

Em produção a aplicação **recusa subir** se `SECRET_KEY` estiver no valor padrão (ou no valor de exemplo de algum arquivo do repositório) ou se `ADMIN_PASSWORD` e `COPA_PASSWORD` não estiverem definidas. A régua é o ambiente: ligar `DEBUG` em produção não dispensa a verificação.

Variável definida mas vazia vale o mesmo que ausente. Um `.env` copiado do modelo, com as senhas ainda em branco, sobe em desenvolvimento com as senhas de desenvolvimento.

Para ver a configuração efetiva sem revelar segredos (a senha do banco aparece mascarada):

```powershell
$env:FLASK_APP="app:create_app"
flask check-config
```

## Banco De Dados

O padrão é SQLite em memória, o que recria tudo a cada inicialização e facilita demonstrações. Para persistir em arquivo:

```powershell
$env:DATABASE_URL="sqlite:///copa.db"
```

Caminho relativo de SQLite parte da pasta `instance/` (o exemplo acima grava `instance/copa.db`). As conexões SQLite usam modo WAL, para o painel da copa ler enquanto as salas gravam, e verificam chave estrangeira.

### Migrations

O esquema é versionado com Alembic. Com `AUTO_MIGRATE` (padrão em produção), o `run.py` aplica as migrations pendentes ao subir e semeia o catálogo inicial **só se o banco estiver vazio**. Para fazer o mesmo à mão, ou num passo de release da nuvem:

```powershell
$env:FLASK_APP="app:create_app"
flask prepare-db          # migrations + catálogo inicial se o banco estiver vazio
flask db upgrade          # só as migrations
flask init-db             # semeadura aditiva do catálogo inicial
```

Depois de alterar `app/models.py`:

```powershell
flask db migrate -m "descricao da mudanca"
flask db upgrade
```

A semeadura é **aditiva**: cria o que falta e nunca reescreve nome, tipo, ordem ou status de um registro existente. Rodar `flask init-db` duas vezes na sequência cria zero registros na segunda vez. Na subida automática ela só roda sobre banco vazio, para que um escritório renomeado não volte com o nome antigo ao lado do novo.

## Configuração

Copie `.env.example` para `.env` e ajuste (ou gere um pronto com `python run.py --setup`):

```powershell
Copy-Item .env.example .env
```

| Variável | Padrão | Para que serve |
| --- | --- | --- |
| `APP_ENV` | `development` | Ambiente: `development`, `testing` ou `production` |
| `SECRET_KEY` | `dev-only-secret-key` | Assina o cookie de sessão. Obrigatória fora de desenvolvimento |
| `ADMIN_PASSWORD` | `admin` em dev, vazio nos demais | Senha do painel administrativo |
| `COPA_PASSWORD` | `copa` em dev, vazio nos demais | Senha do painel da copa |
| `DATABASE_URL` | `sqlite:///:memory:` | Conexão do banco. `postgres://` é aceito e convertido |
| `AUTO_CREATE_DB` | `True` (`False` em produção) | `create_all` e semeadura na criação da aplicação |
| `AUTO_MIGRATE` | `False` (`True` em produção) | Migrations e semeadura do banco vazio ao subir pelo `run.py` |
| `APP_HOST` | `127.0.0.1` | Interface de escuta |
| `APP_PORT` | `5000` (ou `PORT`) | Porta. `PORT`, das plataformas de nuvem, vale quando `APP_PORT` não está definida |
| `WAITRESS_THREADS` | `4` | Threads do servidor |
| `PUBLIC_BASE_URL` | vazio | Endereço público usado nos QR codes das salas |
| `TRUST_PROXY_HOPS` | `0` | Proxies reversos confiáveis à frente da aplicação |
| `DEBUG` | do ambiente | Modo de depuração |
| `SESSION_COOKIE_SAMESITE` | `Lax` | Política SameSite do cookie |
| `SESSION_COOKIE_SECURE` | `false` (`true` em produção) | Exige HTTPS para o cookie. Em HTTP na rede local, `false` |
| `RATELIMIT_ENABLED` | `true` | Liga o limite de requisições |
| `RATELIMIT_STORAGE_URI` | `memory://` | Onde o limite é contado. Com várias instâncias, `redis://...` |
| `ORDER_WARN_MINUTES` | `5` | Espera a partir da qual o painel destaca o pedido em amarelo |
| `ORDER_LATE_MINUTES` | `10` | Espera a partir da qual o pedido fica em vermelho |
| `LOG_LEVEL` | `INFO` | Nível do log da aplicação |
| `LOG_FILE` | vazio | Log rotativo em arquivo (caminho relativo à raiz do projeto) |

Gere uma chave de sessão com:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

## Acesso E Perfis

O formulário de pedido é público de propósito: quem está numa sala de reunião precisa pedir café sem credencial. Os painéis internos exigem senha.

| Perfil | Senha | Acessa |
| --- | --- | --- |
| Copa | `COPA_PASSWORD` | `/copa` e a API de pedidos |
| Administração | `ADMIN_PASSWORD` | tudo, incluindo `/admin`, o histórico e os QR codes |

Não há cadastro de usuários. A trilha de auditoria registra o perfil e o IP de cada ação relevante, não a identidade de uma pessoa. Se um dia for preciso saber *quem* concluiu um pedido, `app/security.py` é a camada a substituir por autenticação real.

## Rotas e API

| Método | Rota | Acesso | Descrição |
| --- | --- | --- | --- |
| `GET` | `/health` | público | Estado da aplicação, do banco e versão. `503` se o banco não responde |
| `GET` | `/pedido/sala/<id>` | público | Formulário de itens da sala (link direto e QR code). `404` se a sala não recebe pedidos |
| `POST` | `/submit_form` | público | Envia o pedido e redireciona para a confirmação. O campo `request_token` evita duplicidade |
| `GET` | `/pedido/<id>` | quem pediu | Confirmação do pedido, visível só para o navegador que o enviou |
| `GET` | `/api/rooms?office=NOME` | público | Salas ativas do escritório (JSON) |
| `POST` | `/get_rooms` | público | Mesma consulta, aceita `{"office": "NOME"}`. Mantida por compatibilidade |
| `GET` | `/api/orders` | copa | Pedidos pendentes, do mais antigo para o mais novo (JSON) |
| `POST` | `/api/complete_order/<id>` | copa | Conclui um pedido. `404` se não existe, `409` se já foi concluído |
| `POST` | `/admin/products/reorder` | admin | Grava a ordem dos insumos a partir de `{"product_ids": [...]}` |
| `GET` | `/admin/history.csv` | admin | Histórico filtrado em CSV (`;` e UTF-8 com BOM, para o Excel) |
| `GET` | `/admin/spaces/qrcodes` | admin | Página de impressão com o QR code de cada sala ativa |

As rotas que alteram estado exigem o token CSRF no cabeçalho `X-CSRFToken`. O token é publicado na página em `<meta name="csrf-token">`.

Exemplo de resposta de `/api/orders`:

```json
[
  {
    "id": 12,
    "office": "Sede Centro",
    "room": "Sala Bourbon",
    "status": "pending",
    "date": "10/08/2026",
    "time": "09:14",
    "created_at": "2026-08-10T09:14:22",
    "waiting_seconds": 312,
    "note": "Adoçante à parte",
    "items": { "Café expresso com açúcar": 3, "Limpeza da sala": "Sim" }
  }
]
```

`waiting_seconds` é calculado no servidor, no horário de Brasília, para que o relógio de um tablet em outro fuso não distorça a espera.

## Segurança

O que está implementado:

- Autenticação por perfil em todos os painéis internos e nas rotas de API.
- CSRF em todos os formulários e nas requisições JSON que alteram estado.
- Content-Security-Policy sem `unsafe-inline`: o único script inline, o do tema, é liberado por nonce gerado a cada requisição.
- `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Cross-Origin-Opener-Policy` e HSTS sob HTTPS.
- Cookie de sessão `HttpOnly`, `SameSite=Lax` e `Secure` em produção.
- Limite de requisições no envio de pedidos e nas tentativas de login, com armazenamento configurável.
- Recusa de subir em produção com chave de sessão padrão ou de exemplo, ou sem senhas definidas.
- Confirmação de pedido visível só para o navegador que o enviou.
- `X-Forwarded-*` aceito apenas com `TRUST_PROXY_HOPS` definido.
- Trilha de auditoria com perfil, IP e ação, no log da aplicação.
- Limite de 256 KB no corpo da requisição.

O que continua fora do escopo:

- Cadastro de usuários e identidade individual.
- Autorização granular além dos dois perfis.
- Armazenamento das senhas com hash — elas vêm do ambiente e são comparadas em tempo constante.
- Retenção e expurgo do histórico de pedidos.

## Qualidade

```powershell
python -m unittest discover -s . -p "test_*.py"   # suíte completa
ruff check .                                      # lint
ruff check --fix .                                # lint com correção automática
pyright                                           # verificação de tipos
node --check app/static/script.js                 # sintaxe JS (idem dashboard.js)
docker build -t copa-pronta .                     # imagem (opcional localmente)
```

A suíte usa banco em memória e não altera dados locais. Os testes de semeadura e de preparo do banco usam arquivo temporário, porque o cenário que eles cobrem é justamente o de reiniciar o servidor sobre um banco persistente.

O workflow `Quality Gate` roda tudo isso em cada PR para `main` (os testes em Python 3.11, 3.12 e 3.13), aplica as migrations num banco limpo, confere que a semeadura é idempotente e constrói a imagem Docker, sobe o contêiner e consulta o `/health`.

## Versionamento

A versão segue [SemVer](https://semver.org/lang/pt-BR/) e é calculada a partir dos commits, que seguem [Conventional Commits](https://www.conventionalcommits.org/pt-br/): `fix` gera patch, `feat` gera minor e `BREAKING CHANGE` gera major. A cada push para `main`, o workflow `Release` roda o mesmo gate e, se ele passar, atualiza `pyproject.toml` e `CHANGELOG.md`, cria a tag `vX.Y.Z` e publica a GitHub Release. A versão em uso aparece no rodapé das páginas e no `/health`.

Versão e changelog não se editam à mão. Detalhes e diagnóstico em [docs/RELEASE.md](docs/RELEASE.md).

## Licença

[MIT](LICENSE).

Como contribuir: [CONTRIBUTING.md](CONTRIBUTING.md). Histórico de mudanças:
[CHANGELOG.md](CHANGELOG.md). Decisões de arquitetura: [docs/DECISIONS.md](docs/DECISIONS.md).
Implantação: [docs/DEPLOY.md](docs/DEPLOY.md).

## Identidade visual

O símbolo é uma xícara cujo vapor forma um ✓: o pedido que chega pronto à sala. No cabeçalho ele é um SVG inline em `base.html`, pintado pelas variáveis `--color-*`, por isso a mesma marcação serve aos dois temas. `app/static/icon.svg` é a versão com fundo, usada como favicon.

A paleta usa tons de café, definidos no topo de `styles.css`. O verde de sucesso foi escurecido para que o texto branco sobre ele passe no contraste mínimo do WCAG. O texto usa a fonte do sistema, então não há arquivo de fonte para licenciar nem origem externa na CSP.
