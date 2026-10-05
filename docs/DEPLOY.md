# Implantação

Três caminhos, do mais simples ao mais distribuído. Todos usam o mesmo `run.py`
(Waitress), as mesmas migrations e a mesma configuração por variável de ambiente;
o que muda é onde o banco mora e quem termina o HTTPS.

| Caminho | Banco | Para quê |
| --- | --- | --- |
| [Rede local, sem internet](#rede-local-sem-internet) | SQLite em `instance/` | Uma máquina do escritório atende as salas e a copa |
| [Docker](#docker) | SQLite num volume | Mesmo cenário, num servidor que já roda contêineres |
| [Nuvem](#nuvem) | PostgreSQL gerenciado (ou SQLite em disco persistente) | Acesso de fora da rede, várias unidades |

## Rede local, sem internet

Depois da instalação das dependências, nada aqui depende de internet: não há CDN,
fonte remota nem serviço externo. Os QR codes são gerados no próprio servidor.

### Instalar

```powershell
cd C:\repositories\cafe
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py --setup
```

O `--setup` grava um `.env` com:

- `APP_ENV=production`, `SECRET_KEY` aleatória e senhas novas para admin e copa
  (mostradas uma única vez no terminal);
- banco SQLite em `instance/copa.db` e `AUTO_MIGRATE=true`;
- `APP_HOST=0.0.0.0`, para os celulares e tablets da rede alcançarem o portal;
- `PUBLIC_BASE_URL` com o IP detectado, usado nos QR codes;
- `SESSION_COOKIE_SECURE=false`, porque na rede local o acesso é HTTP;
- log rotativo em `instance/copa.log`.

Ele nunca sobrescreve um `.env` existente. Depois:

```powershell
python run.py
```

Na primeira subida, as migrations criam o esquema e o catálogo inicial é semeado.
Nas seguintes, só migrations novas são aplicadas e o catálogo fica como a
administração deixou.

### Liberar no firewall do Windows

```powershell
New-NetFirewallRule -DisplayName "Copa Pronta" -Direction Inbound -Protocol TCP -LocalPort 5000 -Action Allow -Profile Private
```

### Iniciar junto com o Windows

O Agendador de Tarefas sobe o portal no boot, sem ninguém logado. O `--background`
destaca o servidor e grava a saída em `cafe_server.log`.

```powershell
$pasta = "C:\repositories\cafe"
$acao = New-ScheduledTaskAction -Execute "$pasta\.venv\Scripts\python.exe" `
    -Argument "run.py --background" -WorkingDirectory $pasta
$gatilho = New-ScheduledTaskTrigger -AtStartup
Register-ScheduledTask -TaskName "Copa Pronta" -Action $acao -Trigger $gatilho `
    -User "SYSTEM" -RunLevel Highest
```

Para conferir sem reiniciar a máquina: `Start-ScheduledTask -TaskName "Copa Pronta"`
e abrir `http://127.0.0.1:5000/health`.

No Linux, o equivalente é uma unidade do systemd com
`ExecStart=/caminho/.venv/bin/python run.py` e `WorkingDirectory=/caminho`.

### Backup diário

Com o servidor no ar, copiar só o `copa.db` pode perder os últimos pedidos: no modo
WAL eles ficam no arquivo `-wal` até o próximo checkpoint. O comando abaixo usa a
API de backup do SQLite, que copia um retrato consistente, e mantém as 14 cópias
mais novas em `instance/backups/`:

```powershell
$env:FLASK_APP="app:create_app"
flask backup-db                       # --dir e --keep mudam pasta e quantidade
```

Agendado todo dia às 22h:

```powershell
$pasta = "C:\repositories\cafe"
$acao = New-ScheduledTaskAction -Execute "$pasta\.venv\Scripts\flask.exe" `
    -Argument "--app app:create_app backup-db" -WorkingDirectory $pasta
$gatilho = New-ScheduledTaskTrigger -Daily -At 22:00
Register-ScheduledTask -TaskName "Copa Pronta - backup" -Action $acao -Trigger $gatilho `
    -User "SYSTEM" -RunLevel Highest
```

Para restaurar: pare o servidor, troque `instance/copa.db` pela cópia, apague os
`copa.db-wal` e `copa.db-shm` que sobraram e suba de novo.

### Atualizar

```powershell
git pull                              # ou copie a nova versão por cima
pip install -r requirements.txt
```

Reinicie o servidor (ou a tarefa agendada). As migrations novas são aplicadas na
subida. A versão em uso aparece no rodapé e em `/health`.

### QR codes nas salas

Em **Admin → Salas → QR codes das salas** há uma página de impressão com um código
por sala ativa. Cada um abre o pedido daquela sala direto, sem escolher escritório.
Os códigos usam `PUBLIC_BASE_URL`; se ele estiver vazio, usam o endereço pelo qual
a página foi aberta, e a página avisa quando esse endereço só funciona na própria
máquina (`127.0.0.1`). Se o IP do servidor mudar, ajuste `PUBLIC_BASE_URL` e
reimprima — ou reserve o IP no roteador.

### HTTPS na rede local (opcional)

Para HTTPS, coloque um proxy reverso na frente (Caddy, nginx, IIS com ARR) e
defina `SESSION_COOKIE_SECURE=true` e `TRUST_PROXY_HOPS=1`. Com HTTPS, o painel da
copa também ganha notificação do sistema e tela sempre acesa, que os navegadores
só liberam em contexto seguro (ou em `localhost`).

## Docker

```powershell
python run.py --setup             # só para gerar SECRET_KEY e senhas no .env
docker compose up -d --build
```

O `docker-compose.yml` lê o `.env` apenas para preencher segredos, porta publicada
(`APP_PORT`, padrão 5000) e `PUBLIC_BASE_URL`. Dentro do contêiner o banco é
`/data/copa.db`, num volume nomeado que sobrevive a `docker compose down` e a
reconstruções da imagem.

- Atualizar: `git pull` e `docker compose up -d --build`.
- Backup: `docker compose exec copa flask --app app:create_app backup-db --dir /data/backups`.
- Logs: `docker compose logs -f copa`.

A imagem roda como usuário sem privilégios, tem `HEALTHCHECK` no `/health` e recusa
subir sem `SECRET_KEY`, `ADMIN_PASSWORD` e `COPA_PASSWORD`. O CI constrói a imagem e
testa essa subida em todo PR.

## Nuvem

Qualquer plataforma que construa a partir de um `Dockerfile` serve (Render,
Railway, Fly.io, Cloud Run, Azure Container Apps, uma VM com Docker). A imagem lê
`PORT`, que essas plataformas definem.

### Variáveis

| Variável | Valor |
| --- | --- |
| `SECRET_KEY` | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ADMIN_PASSWORD`, `COPA_PASSWORD` | senhas fortes |
| `DATABASE_URL` | URL do PostgreSQL. `postgres://` é aceito e convertido |
| `TRUST_PROXY_HOPS` | `1` (o balanceador da plataforma termina o HTTPS) |
| `PUBLIC_BASE_URL` | `https://copa.suaempresa.com.br` |
| `SESSION_COOKIE_SECURE` | deixe o padrão de produção (`true`) |

`APP_ENV=production` e `APP_HOST=0.0.0.0` já vêm na imagem.

### Banco

O disco de contêiner na nuvem costuma ser efêmero: sem um volume persistente
montado em `/data`, o SQLite some a cada deploy. Use PostgreSQL gerenciado; o
driver (`psycopg`) já está na imagem. Fora do Docker, instale com
`pip install -r requirements-postgres.txt`. O backup passa a ser o da plataforma
ou `pg_dump`.

### Mais de uma instância

- Migrations: com várias instâncias subindo juntas, defina `AUTO_MIGRATE=false` e
  rode `flask --app app:create_app prepare-db` uma vez por deploy, no passo de
  release da plataforma.
- Limite de requisições: `memory://` conta por processo. Aponte
  `RATELIMIT_STORAGE_URI` para um Redis (`redis://...`) e acrescente `redis` às
  dependências da imagem.

### Subcaminho

Atrás de um proxy que publique o portal em `/copa-pronta/`, envie
`X-Forwarded-Prefix` e defina `TRUST_PROXY_HOPS`: os endereços das páginas e do
painel da copa vêm de `url_for` e acompanham o prefixo.

## Conferir e diagnosticar

```powershell
flask --app app:create_app check-config   # configuração efetiva, sem segredos
curl http://127.0.0.1:5000/health          # {"status": "ok", "database": "ok", "version": ...}
```

| Sintoma | Causa provável |
| --- | --- |
| A senha é aceita, mas o painel volta para o login | `SESSION_COOKIE_SECURE=true` sem HTTPS. O `run.py` avisa na subida |
| "O banco tem tabelas, mas nenhum registro de migration" | O banco foi criado por `db.create_all()`. Se o esquema está atualizado, `flask db stamp head` uma vez |
| QR codes abrem `127.0.0.1` no celular | Defina `PUBLIC_BASE_URL` com o IP ou nome do servidor |
| O contêiner sai logo depois de subir | Falta `SECRET_KEY`, `ADMIN_PASSWORD` ou `COPA_PASSWORD`; a mensagem está no log |
| Pedido some ao reiniciar | Banco em memória (`sqlite:///:memory:`), o padrão de demonstração |
| O painel da copa não toca som | O navegador exige um toque na página: use **Ativar alertas** |
