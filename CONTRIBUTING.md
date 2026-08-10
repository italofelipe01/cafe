# Como contribuir

## Ambiente

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
Copy-Item .env.example .env
```

## Antes de abrir um PR

```powershell
ruff check .
python -m unittest discover -s . -p "test_*.py"
```

Os dois precisam passar. O CI roda exatamente isso, em Python 3.11, 3.12 e 3.13.

## Convenções

**Commits** seguem [Conventional Commits](https://www.conventionalcommits.org/pt-br/),
como o histórico existente: `feat(admin): ...`, `fix(copa): ...`, `chore(deps): ...`.

**Código** Python segue o ruff configurado em `pyproject.toml`. Duas regras de
arquitetura que o linter não verifica:

- Rotas em `app/routes.py` só traduzem HTTP. Validação e acesso a dados moram
  em `app/services.py`.
- Erros de negócio são `ServiceError` (ou `NotFoundError`), com a mensagem já
  escrita para quem vai ler na tela.

**CSS** usa as variáveis de tema declaradas no topo de `styles.css`. Não escreva
cor literal em componente: toda cor sai de um `--color-*`, para que os dois temas
continuem funcionando. O padding do painel é publicado em `--panel-padding-x/y`;
elementos full-bleed derivam a margem negativa dele em vez de repetir o número.

**JavaScript** não tem etapa de build nem dependência externa. Cada bloco de
`script.js` começa com uma checagem de existência do elemento âncora, porque o
mesmo arquivo serve a todas as telas.

**Templates** herdam de `base.html`. Todo formulário POST precisa do campo
`csrf_token`; há um teste que falha se algum ficar sem.

## Mudanças no banco

Depois de alterar `app/models.py`:

```powershell
$env:FLASK_APP="app:create_app"
$env:DATABASE_URL="sqlite:///instance/dev.db"
flask db migrate -m "descricao da mudanca"
flask db upgrade
```

Commite a migration junto com a mudança do modelo. O CI roda `flask db check` e
falha se o modelo e as migrations divergirem.

## Mudanças no catálogo inicial

`app/seed.py` é **aditivo** por contrato: pode acrescentar escritórios, salas e
insumos, mas nunca alterar registros existentes. Esse contrato é o que impede
que um reinício desfaça o trabalho de quem administra o portal, e há testes em
`tests/test_seed.py` que falham se ele for quebrado.
