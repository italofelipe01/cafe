# Espaço Café EBM

Portal Flask para solicitação de itens de copa por sala, acompanhamento operacional dos pedidos e manutenção do catálogo usado no formulário.

## Funcionalidades

- Pedido por escritório e sala.
- Catálogo dinâmico de insumos, com itens de quantidade e itens sim/não.
- Painel da copa em `/copa`, com atualização automática dos pedidos pendentes.
- Modal próprio para concluir pedidos, sem diálogo nativo do navegador.
- Admin em `/admin` para manter escritórios, salas e insumos.
- Ativação/inativação de escritórios, salas e insumos.
- Ao inativar ou reativar um escritório, todas as salas dele acompanham o status.
- Filtro de salas por escritório e busca por trecho do nome.
- Reordenação de insumos por drag and drop.
- Tema claro/escuro com logo adequada para cada modo.
- Transições leves entre páginas e na troca de tema, respeitando redução de movimento do sistema.
- Testes automatizados com SQLite em memória.

## Estrutura Atual

```text
app/
  __init__.py              # Application factory, criação do banco e carga inicial
  extensions.py            # SQLAlchemy
  models.py                # Office, Space, Product, Order, OrderItem
  routes.py                # Rotas HTML e APIs
  static/
    dashboard.js           # JS do painel da copa
    script.js              # JS global: tema, transições, filtros e drag and drop
    styles.css             # Estilos globais
    icon.png               # Favicon
    images/                # Logos claro/escuro
    font/                  # Fonte local Fedra Sans Pro
  templates/
    base.html              # Layout base
    index.html             # Pedido: seleção de escritório e sala
    sala_form.html         # Pedido: itens disponíveis
    confirm_pedido.html    # Confirmação do pedido
    copa_dashboard.html    # Painel da copa
    admin/                 # Telas administrativas
config.py                  # Configuração por ambiente
run.py                     # Entrada local do servidor
tests/test_routes.py       # Suíte automatizada
```

## Requisitos

- Python 3.11+ recomendado.
- Windows, Linux ou macOS.

## Instalação Local

No PowerShell:

```powershell
cd C:\repositories\cafe
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
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
Pedido:        http://127.0.0.1:5000/
Painel copa:  http://127.0.0.1:5000/copa
Admin:         http://127.0.0.1:5000/admin
```

Para permitir acesso pelo celular na mesma rede:

```powershell
$env:APP_HOST="0.0.0.0"
$env:APP_PORT="5000"
python run.py
```

Depois acesse no celular usando o IP local do computador:

```text
http://SEU_IP:5000/
```

## Banco De Dados

Por padrão, o projeto usa:

```text
sqlite:///:memory:
```

Isso facilita testes e demonstrações locais: os dados são recriados a cada inicialização e permanecem disponíveis enquanto o servidor estiver aberto.

Para persistir em arquivo, defina `DATABASE_URL` antes de iniciar:

```powershell
$env:DATABASE_URL="sqlite:///cafe_dev.db"
python run.py
```

## Configuração Opcional

Você pode copiar `.env.example` para `.env` e ajustar host, porta, segredo e banco:

```powershell
Copy-Item .env.example .env
```

## Testes

```powershell
python -m unittest discover tests
```

A suíte usa banco em memória e não altera dados locais.

## Observações De Escopo

Este projeto está preparado para experimento interno. Ainda não há autenticação, permissões, CSRF ou trilha de auditoria corporativa. Esses pontos devem entrar antes de qualquer uso produtivo com acesso amplo.
