import os
import socket
import subprocess
import sys
import time

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv:
    load_dotenv()


def get_server_config(app):
    host = app.config["APP_HOST"]
    port = app.config["APP_PORT"]
    threads = app.config["WAITRESS_THREADS"]
    return host, port, threads


def display_host(host):
    if host in {"0.0.0.0", "::"}:
        return "127.0.0.1"
    return host


def get_lan_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return ""


def print_startup_log(host, port, threads, pid=None, server_name="Flask"):
    url = f"http://{display_host(host)}:{port}"
    print(f"Espaco Cafe EBM iniciado em {url}", flush=True)

    if host in {"0.0.0.0", "::"}:
        lan_ip = get_lan_ip()
        if lan_ip:
            print(f"Acesso na rede local: http://{lan_ip}:{port}", flush=True)

    print(f"Servidor: {server_name} host={host} port={port} threads={threads}", flush=True)
    if pid:
        print(f"Para desligar: Stop-Process -Id {pid}", flush=True)
    else:
        print("Para desligar: pressione Ctrl+C neste terminal.", flush=True)


def serve_foreground(background_child=False):
    from app import create_app

    app = create_app()
    host, port, threads = get_server_config(app)
    pid = os.getpid() if background_child else None

    try:
        from waitress import serve
    except ImportError:
        print_startup_log(host, port, threads, pid=pid, server_name="Flask dev")
        app.run(host=host, port=port, debug=app.config["DEBUG"])
        return

    print_startup_log(host, port, threads, pid=pid, server_name="Waitress")
    serve(app, host=host, port=port, threads=threads)


def start_background():
    project_root = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(project_root, "cafe_server.log")
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

    log_file = open(log_path, "a", encoding="utf-8")
    process = subprocess.Popen(
        command,
        cwd=project_root,
        stdin=subprocess.DEVNULL,
        stdout=log_file,
        stderr=log_file,
        creationflags=creationflags,
    )
    log_file.close()
    time.sleep(1)

    if process.poll() is not None:
        raise RuntimeError(
            f"O servidor encerrou durante a inicializacao. Consulte o log em {log_path}."
        )

    from app import create_app

    app = create_app()
    host, port, threads = get_server_config(app)
    print_startup_log(host, port, threads, pid=process.pid, server_name="background")
    print(f"Log do servidor: {log_path}", flush=True)


if __name__ == "__main__":
    if "--background" in sys.argv:
        start_background()
    elif "--background-child" in sys.argv:
        serve_foreground(background_child=True)
    else:
        serve_foreground()
