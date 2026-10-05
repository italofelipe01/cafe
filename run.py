"""Entrada local do servidor.

``python run.py``               sobe em primeiro plano
``python run.py --background``  sobe destacado e grava a saída em cafe_server.log
``python run.py --setup``       gera um .env pronto para uso contínuo (uma vez)
"""

from __future__ import annotations

import os
import secrets
import socket
import subprocess
import sys
import time
from datetime import datetime

from config import ServerSettings, resolve_config

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependência opcional
    load_dotenv = None

# Importar `config` antes de carregar o .env é seguro: as variáveis de ambiente
# são lidas na criação da aplicação, não no import do módulo.
if load_dotenv:
    load_dotenv()


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(PROJECT_ROOT, "cafe_server.log")
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")
EXPOSED_HOSTS = {"0.0.0.0", "::"}


def read_server_config() -> ServerSettings:
    """Lê host, porta e threads sem instanciar a aplicação.

    O processo pai só precisa desses três valores para imprimir o log de
    inicialização. Criar uma aplicação inteira aqui abriria outra conexão de
    banco e dispararia mais uma semeadura, contra um banco descartado em
    seguida.
    """

    return resolve_config().server_settings()


def display_host(host: str) -> str:
    if host in EXPOSED_HOSTS:
        return "127.0.0.1"
    return host


def get_lan_ip() -> str:
    # Conectar um socket UDP não envia pacote: só pergunta ao sistema qual
    # interface sairia para fora. Funciona sem internet; sem rede, fica vazio.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return ""


def stop_hint(pid: int) -> str:
    if os.name == "nt":
        return f"Stop-Process -Id {pid}"
    return f"kill {pid}"


def config_warnings(config: dict) -> list[str]:
    """Combinações que sobem, mas não vão funcionar como se espera."""

    warnings: list[str] = []
    exposed = config["APP_HOST"] in EXPOSED_HOSTS

    if exposed and config.get("ENV_NAME") == "development":
        warnings.append(
            "Ambiente de desenvolvimento exposto na rede: as senhas 'admin' e 'copa' "
            "sao publicas. Para uso real, rode: python run.py --setup"
        )

    if config["SESSION_COOKIE_SECURE"] and not config["TRUST_PROXY_HOPS"]:
        warnings.append(
            "SESSION_COOKIE_SECURE=true sem proxy HTTPS: fora de localhost o navegador "
            "descarta o cookie e o login nao se mantem. Em HTTP na rede local, use "
            "SESSION_COOKIE_SECURE=false."
        )

    return warnings


def print_startup_log(
    server: ServerSettings,
    pid: int | None = None,
    server_name: str = "Flask",
    warnings: list[str] | None = None,
) -> None:
    url = f"http://{display_host(server.host)}:{server.port}"
    print(f"Copa Pronta iniciado em {url}", flush=True)

    if server.host in EXPOSED_HOSTS:
        lan_ip = get_lan_ip()
        if lan_ip:
            print(f"Acesso na rede local: http://{lan_ip}:{server.port}", flush=True)
        print(
            "Atencao: o portal esta exposto na rede. Confirme que SECRET_KEY, "
            "ADMIN_PASSWORD e COPA_PASSWORD estao definidas.",
            flush=True,
        )

    for warning in warnings or []:
        print(f"Atencao: {warning}", flush=True)

    print(
        f"Servidor: {server_name} host={server.host} "
        f"port={server.port} threads={server.threads}",
        flush=True,
    )
    if pid:
        print(f"Para desligar: {stop_hint(pid)}", flush=True)
    else:
        print("Para desligar: pressione Ctrl+C neste terminal.", flush=True)


def serve_foreground(background_child: bool = False) -> None:
    from app import create_app, prepare_database

    app = create_app()

    if app.config["AUTO_MIGRATE"]:
        # Sem passo manual: cada subida aplica as migrations novas, e a
        # primeira semeia o catálogo. Atualizar o portal vira trocar o código e
        # reiniciar.
        with app.app_context():
            prepare_database()

    server = ServerSettings(
        host=app.config["APP_HOST"],
        port=app.config["APP_PORT"],
        threads=app.config["WAITRESS_THREADS"],
    )
    pid = os.getpid() if background_child else None
    warnings = config_warnings(app.config)

    try:
        from waitress import serve
    except ImportError:
        print_startup_log(server, pid=pid, server_name="Flask dev", warnings=warnings)
        app.run(host=server.host, port=server.port, debug=app.config["DEBUG"])
        return

    print_startup_log(server, pid=pid, server_name="Waitress", warnings=warnings)
    serve(app, host=server.host, port=server.port, threads=server.threads)


def start_background() -> None:
    executable = sys.executable

    if os.name == "nt":
        pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if os.path.exists(pythonw):
            executable = pythonw

    command = [executable, os.path.abspath(__file__), "--background-child"]
    creationflags = 0

    if os.name == "nt":
        creationflags = (
            subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.CREATE_NO_WINDOW
            | subprocess.DETACHED_PROCESS
        )

    with open(LOG_PATH, "a", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            command,
            cwd=PROJECT_ROOT,
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=log_file,
            creationflags=creationflags,
            # Fora do Windows, uma sessão própria impede que fechar o terminal
            # derrube o servidor junto.
            start_new_session=os.name != "nt",
        )

    time.sleep(1)

    if process.poll() is not None:
        raise RuntimeError(
            f"O servidor encerrou durante a inicializacao. Consulte o log em {LOG_PATH}."
        )

    print_startup_log(
        read_server_config(), pid=process.pid, server_name="background"
    )
    print(f"Log do servidor: {LOG_PATH}", flush=True)


def build_env_file(lan_ip: str = "") -> tuple[str, dict[str, str]]:
    """Conteúdo de um .env para uso contínuo, com segredos novos.

    Devolve o texto e as senhas geradas, que só aparecem uma vez no terminal.
    """

    passwords = {
        "ADMIN_PASSWORD": secrets.token_urlsafe(9),
        "COPA_PASSWORD": secrets.token_urlsafe(9),
    }
    public_url = f"http://{lan_ip}:5000" if lan_ip else "http://IP-DA-MAQUINA:5000"
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    content = f"""# Gerado por `python run.py --setup` em {generated_at}.
# Configuracao para uso continuo na rede local. Referencia completa: .env.example

APP_ENV=production

# Segredos gerados agora. Guarde as senhas: elas nao aparecem em outro lugar.
SECRET_KEY={secrets.token_hex(32)}
ADMIN_PASSWORD={passwords["ADMIN_PASSWORD"]}
COPA_PASSWORD={passwords["COPA_PASSWORD"]}

# SQLite em arquivo, dentro de instance/ (caminho relativo a essa pasta).
DATABASE_URL=sqlite:///copa.db

# Cada subida aplica as migrations pendentes; a primeira semeia o catalogo.
AUTO_MIGRATE=true

# 0.0.0.0 atende os celulares e tablets da rede. Para uso so nesta maquina,
# troque por 127.0.0.1.
APP_HOST=0.0.0.0
APP_PORT=5000

# Endereco que os QR codes das salas vao abrir. Ajuste se o IP mudar.
PUBLIC_BASE_URL={public_url}

# HTTP na rede local: o cookie seguro exigiria HTTPS e o login nao se manteria.
# Passe para true quando houver um proxy com TLS na frente.
SESSION_COOKIE_SECURE=false

LOG_LEVEL=INFO
LOG_FILE=instance/copa.log
"""
    return content, passwords


def run_setup() -> None:
    if os.path.exists(ENV_PATH):
        print(f"{ENV_PATH} ja existe: nada foi alterado.", flush=True)
        print("Para conferir a configuracao: flask --app app:create_app check-config")
        return

    content, passwords = build_env_file(get_lan_ip())
    with open(ENV_PATH, "x", encoding="utf-8") as env_file:
        env_file.write(content)

    print(f"Configuracao gravada em {ENV_PATH}", flush=True)
    print("")
    print(f"  Senha da administracao: {passwords['ADMIN_PASSWORD']}")
    print(f"  Senha da copa:          {passwords['COPA_PASSWORD']}")
    print("")
    print("Guarde as senhas. Para subir o portal: python run.py")


if __name__ == "__main__":
    if "--setup" in sys.argv:
        run_setup()
    elif "--background" in sys.argv:
        start_background()
    elif "--background-child" in sys.argv:
        serve_foreground(background_child=True)
    else:
        serve_foreground()
