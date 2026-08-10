# Espaço Café EBM

Portal Flask para solicitação de itens de copa por sala, acompanhamento operacional dos pedidos e manutenção do catálogo usado no formulário.

## Funcionalidades

- Pedido por escritório e sala, sem necessidade de login.
- Catálogo dinâmico de insumos, com itens de quantidade e itens sim/não.
- Painel da copa em `/copa`, com atualização automática dos pedidos pendentes.
- Modal próprio para concluir pedidos, sem diálogo nativo do navegador.
- Admin em `/admin` para manter escritórios, salas e insumos.
- Histórico de pedidos concluídos em `/admin/history`, com filtro por período e escritório.
- Ativação/inativação de escritórios, salas e insumos, com cascata do escritório para as salas.
- Filtro de salas por escritório e busca por trecho do nome.
- Reordenação de insumos por arrastar ou pelas setas do teclado.
- Tema claro/escuro com logo adequada para cada modo, aplicado antes da primeira pintura.
- Transições leves entre páginas e na troca de tema, respeitando redução de movimento do sistema.
- Autenticação por perfil, proteção CSRF, cabeçalhos de segurança, limite de requisições e trilha de auditoria.
- Migrations com Alembic e suíte automatizada com SQLite em memória.

## Estrutura

```text
app/
  __init__.py              # Application factory, logging, cabeçalhos, erros e CLI
  extensions.py            # SQLAlchemy, Migrate, CSRF e Limiter
  models.py                # Office, Space, Product, Order, OrderItem
  routes.py                # Rotas HTTP (finas: só traduzem requisição em serviço)
  services.py              # Regra de negócio e acesso a dados
  security.py              # Perfis, senhas e decorador de acesso
  seed.py                  # Catálogo inicial (semeadura aditiva)
  static/
    dashboard.js           # JS do painel da copa
    script.js              # JS global: tema, transições, filtros e ordenação
    styles.css             # Estilos globais
    icon.png               # Favicon
    images/                # Logos claro/escuro
    font/                  # Fonte local Fedra Sans Pro
  templates/
    base.html              # Layout base
    login.html             # Acesso aos painéis internos
    index.html             # Pedido: seleção de escritório e sala
    sala_form.html         # Pedido: itens disponíveis
    confirm_pedido.html    # Confirmação do pedido
    copa_dashboard.html    # Painel da copa
    admin/                 # Telas administrativas, incluindo o histórico
    errors/                # Páginas 400, 401, 404, 429 e 500
migrations/                # Alembic: esquema versionado
tests/                     # Suíte automatizada
config.py                  # Configuração por ambiente
run.py                     # Entrada local do servidor
```

## Requisitos

- Python 3.11 ou superior.
- Windows, Linux ou macOS.

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

Para permitir acesso pelo celular na mesma rede:

```powershell
$env:APP_HOST="0.0.0.0"
python run.py
```

Nesse modo o portal fica exposto a toda a rede local. Defina `SECRET_KEY`, `ADMIN_PASSWORD` e `COPA_PASSWORD` antes.

## Ambientes

O ambiente é escolhido por `APP_ENV` (ou `FLASK_ENV`), e o padrão é `development`.

| Ambiente | Debug | Cria o banco no boot | Senhas padrão | Cookie seguro |
| --- | --- | --- | --- | --- |
| `development` | sim | sim | sim | não |
| `testing` | não | sim | de teste | não |
| `production` | não | **não** (use migrations) | **exigidas** | sim |

Em produção a aplicação **recusa subir** se `SECRET_KEY` continuar no valor padrão ou se `ADMIN_PASSWORD` e `COPA_PASSWORD` não estiverem definidas. Isso é intencional: uma chave de sessão previsível é o que permite forjar sessão.

Para ver a configuração efetiva sem revelar segredos:

```powershell
$env:FLASK_APP="app:create_app"
flask check-config
```

## Banco De Dados

O padrão é SQLite em memória, o que recria tudo a cada inicialização e facilita demonstrações. Para persistir em arquivo:

```powershell
$env:DATABASE_URL="sqlite:///cafe_dev.db"
```

### Migrations

O esquema é versionado com Alembic. Em qualquer ambiente com banco persistente:

```powershell
$env:FLASK_APP="app:create_app"
flask db upgrade          # aplica o esquema
flask init-db             # semeia o catálogo inicial
```

Depois de alterar `app/models.py`:

```powershell
flask db migrate -m "descricao da mudanca"
flask db upgrade
```

A semeadura é **aditiva**: cria o que falta e nunca reescreve nome, tipo, ordem ou status de um registro existente. Rodar `flask init-db` duas vezes na sequência cria zero registros na segunda vez — e é isso que garante que uma reinicialização do servidor não desfaça o trabalho de quem administra o catálogo.

## Configuração

Copie `.env.example` para `.env` e ajuste:

```powershell
Copy-Item .env.example .env
```

| Variável | Padrão | Para que serve |
| --- | --- | --- |
| `APP_ENV` | `development` | Ambiente: `development`, `testing` ou `production` |
| `SECRET_KEY` | `dev-only-secret-key` | Assina o cookie de sessão. Obrigatória fora de desenvolvimento |
| `ADMIN_PASSWORD` | vazio | Senha do painel administrativo |
| `COPA_PASSWORD` | vazio | Senha do painel da copa |
| `DATABASE_URL` | `sqlite:///:memory:` | Conexão do banco |
| `AUTO_CREATE_DB` | `True` (`False` em produção) | Cria o esquema e semeia na inicialização |
| `APP_HOST` | `127.0.0.1` | Interface de escuta |
| `APP_PORT` | `5000` | Porta |
| `WAITRESS_THREADS` | `4` | Threads do servidor de produção |
| `DEBUG` | `false` | Modo de depuração |
| `SESSION_COOKIE_SAMESITE` | `Lax` | Política SameSite do cookie |
| `SESSION_COOKIE_SECURE` | `false` (`true` em produção) | Exige HTTPS para o cookie |
| `RATELIMIT_ENABLED` | `true` | Liga o limite de requisições |
| `LOG_LEVEL` | `INFO` | Nível do log da aplicação |
| `LOG_FILE` | vazio | Caminho de um log rotativo em arquivo |

Gere uma chave de sessão com:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

## Acesso E Perfis

O formulário de pedido é público de propósito: quem está numa sala de reunião precisa pedir café sem credencial. Os painéis internos exigem senha.

| Perfil | Senha | Acessa |
| --- | --- | --- |
| Copa | `COPA_PASSWORD` | `/copa` e a API de pedidos |
| Administração | `ADMIN_PASSWORD` | tudo, incluindo `/admin` e o histórico |

Não há cadastro de usuários. A trilha de auditoria registra o perfil e o IP de cada ação relevante, não a identidade de uma pessoa. Se um dia for preciso saber *quem* concluiu um pedido, `app/security.py` é a camada a substituir por autenticação real.

## API

Todas as respostas são JSON. As rotas internas respondem `401` quando não há sessão.

| Método | Rota | Acesso | Descrição |
| --- | --- | --- | --- |
| `GET` | `/health` | público | Estado da aplicação e do banco. `503` se o banco não responde |
| `GET` | `/api/rooms?office=NOME` | público | Salas ativas do escritório |
| `POST` | `/get_rooms` | público | Mesma consulta, aceita `{"office": "NOME"}`. Mantida por compatibilidade |
| `GET` | `/api/orders` | copa | Pedidos pendentes, do mais antigo para o mais novo |
| `POST` | `/api/complete_order/<id>` | copa | Conclui um pedido. `404` se não existe, `409` se já foi concluído |
| `POST` | `/admin/products/reorder` | admin | Grava a ordem dos insumos a partir de `{"product_ids": [...]}` |

As rotas que alteram estado exigem o token CSRF no cabeçalho `X-CSRFToken`. O token é publicado na página em `<meta name="csrf-token">`.

Exemplo de resposta de `/api/orders`:

```json
[
  {
    "id": 12,
    "office": "EBM Office Goiânia",
    "room": "Sala Aton",
    "status": "pending",
    "date": "10/08/2026",
    "time": "09:14",
    "created_at": "2026-08-10T09:14:22",
    "items": { "Café expresso com açúcar": 3, "Limpeza da sala": "Sim" }
  }
]
```

## Segurança

O que está implementado:

- Autenticação por perfil em todos os painéis internos e nas rotas de API.
- CSRF em todos os formulários e nas requisições JSON que alteram estado.
- Content-Security-Policy sem `unsafe-inline`: o único script inline, o do tema, é liberado por nonce gerado a cada requisição.
- `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Cross-Origin-Opener-Policy` e HSTS sob HTTPS.
- Cookie de sessão `HttpOnly`, `SameSite=Lax` e `Secure` em produção.
- Limite de requisições no envio de pedidos e nas tentativas de login.
- Recusa de subir em produção com chave de sessão padrão ou sem senhas definidas.
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
```

A suíte usa banco em memória e não altera dados locais. Os testes de semeadura usam um arquivo temporário, porque o cenário que eles cobrem é justamente o de reiniciar o servidor sobre um banco persistente.

## Licença

Uso interno da organização, conforme [LICENSE](LICENSE). Se a intenção passar a
ser publicar o código, substitua o arquivo por uma licença aberta (MIT, Apache 2.0)
e resolva antes a questão da fonte descrita em [NOTICE.md](NOTICE.md).

Como contribuir: [CONTRIBUTING.md](CONTRIBUTING.md). Histórico de mudanças:
[CHANGELOG.md](CHANGELOG.md).

## Fonte

O diretório `app/static/font/` traz a Fedra Sans Pro, uma fonte comercial. Confirme com quem detém a licença se ela cobre distribuição em repositório e entrega por servidor antes de publicar este projeto fora da organização.
