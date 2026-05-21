# Espaço Café EBM

Aplicação Flask para solicitar itens de copa por sala e acompanhar pedidos pendentes em um painel operacional.

## O que existe hoje

- Seleção de escritório e sala.
- Cardápio configurado por seed no banco.
- Admin simples para cadastrar escritórios, salas e insumos.
- Pedido com múltiplos itens.
- Confirmação do pedido.
- Painel da copa em `/copa`, com atualização automática a cada 10 segundos.
- API local para listar e concluir pedidos.
- Testes automatizados com banco SQLite em memória.

## Estrutura

```text
app/
  __init__.py          # Factory, seed e comando init-db
  extensions.py        # SQLAlchemy
  models.py            # Office, Space, Product, Order, OrderItem
  routes.py            # Rotas HTML e APIs
  static/              # CSS, JS e imagens
  templates/           # Templates Jinja
config.py              # Configs default, development, testing e production
run.py                 # Entrada local
tests/                 # Testes e scripts auxiliares
```

## Como rodar localmente

Crie e ative um ambiente virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Instale as dependências:

```powershell
pip install -r requirements.txt
```

Opcionalmente, copie `.env.example` para `.env` e ajuste porta/host:

```powershell
Copy-Item .env.example .env
```

Inicie o servidor:

```powershell
python run.py
```

Acesse:

- Solicitação: http://127.0.0.1:5000/
- Painel da copa: http://127.0.0.1:5000/copa
- Admin: http://127.0.0.1:5000/admin

Por padrão, o app usa SQLite em memória para facilitar testes locais. Os dados são recriados a cada inicialização, mas permanecem disponíveis enquanto o servidor estiver aberto.

Se quiser persistir os dados em arquivo, defina `DATABASE_URL` antes de iniciar:

```powershell
$env:DATABASE_URL="sqlite:///cafe_dev.db"
python run.py
```

Se iniciar em background com `python run.py --background`, o log fica em `cafe_server.log`.

## Como testar

```powershell
python -m unittest discover tests
```

Os testes usam `sqlite:///:memory:`, então não alteram o banco local.

## Próximas evoluções naturais

- Migrations com Flask-Migrate/Alembic antes de produção real.
- Tela admin para editar escritórios, salas e produtos sem alterar código.
- Relatórios por período, sala, escritório e item.
- Deploy com Waitress/Gunicorn e banco PostgreSQL quando deixar de ser experimento.
