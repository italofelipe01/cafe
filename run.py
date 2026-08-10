"""Entrada local do servidor.

``python run.py``               sobe em primeiro plano
``python run.py --background``  sobe destacado e grava a saída em cafe_server.log
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time

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


def read_server_config() -> ServerSettings:
    """Lê host, porta e threads sem instanciar a aplicação.

    O processo pai só precisa desses três valores para imprimir o log de
    inicialização. Criar uma aplicação inteira aqui abriria outra conexão de
    banco e dispararia mais uma semeadura, contra um banco descartado em
    seguida.
    """

    return resolve_config().server_settings()


def display_host(host: str) -> str:
    if host in {"0.0.0.0", "::"}:
        return "127.0.0.1"
    return host


def get_lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return ""


def print_startup_log(
    server: ServerSettings, pid: int | None = None, server_name: str = "Flask"
) -> None:
    url = f"http://{display_host(server.host)}:{server.port}"
    print(f"Espaco Cafe EBM iniciado em {url}", flush=True)

    if server.host in {"0.0.0.0", "::"}:
        lan_ip = get_lan_ip()
        if lan_ip:
            print(f"Acesso na rede local: http://{lan_ip}:{server.port}", flush=True)
        print(
            "Atencao: o portal esta exposto na rede. Confirme que SECRET_KEY, "
            "ADMIN_PASSWORD e COPA_PASSWORD estao definidas.",
            flush=True,
        )

    print(
        f"Servidor: {server_name} host={server.host} "
        f"port={server.port} threads={server.threads}",
        flush=True,
    )
    if pid:
        print(f"Para desligar: Stop-Process -Id {pid}", flush=True)
    else:
        print("Para desligar: pressione Ctrl+C neste terminal.", flush=True)


def serve_foreground(background_child: bool = False) -> None:
    from app import create_app

    app = create_app()
    server = ServerSettings(
        host=app.config["APP_HOST"],
        port=app.config["APP_PORT"],
        threads=app.config["WAITRESS_THREADS"],
    )
    pid = os.getpid() if background_child else None

    try:
        from waitress import serve
    except ImportError:
        print_startup_log(server, pid=pid, server_name="Flask dev")
        app.run(host=server.host, port=server.port, debug=app.config["DEBUG"])
        return

    print_startup_log(server, pid=pid, server_name="Waitress")
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


if __name__ == "__main__":
    if "--background" in sys.argv:
        start_background()
    elif "--background-child" in sys.argv:
        serve_foreground(background_child=True)
    else:
        serve_foreground()
