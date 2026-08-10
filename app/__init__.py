"""Application factory do Espaço Café EBM."""

from __future__ import annotations

import logging
import os
import secrets
from logging.handlers import RotatingFileHandler
from typing import Any

import click
from flask import Flask, g, jsonify, render_template, request
from flask_wtf.csrf import CSRFError

from app.extensions import csrf, db, limiter, migrate
from config import resolve_config

LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__)

    config_class = resolve_config(config_name)
    app.config.from_object(config_class)
    config_class.init_app(app)

    configure_logging(app)
    register_extensions(app)
    register_blueprints(app)
    register_security_headers(app)
    register_error_handlers(app)
    register_commands(app)

    if app.config["AUTO_CREATE_DB"]:
        with app.app_context():
            initialize_database()

    app.logger.info(
        "Aplicação criada no ambiente '%s' (debug=%s).",
        app.config.get("ENV_NAME", "default"),
        app.config["DEBUG"],
    )
    return app


def configure_logging(app: Flask) -> None:
    """Log de aplicação com nível configurável e arquivo rotativo opcional."""

    level = getattr(logging, app.config["LOG_LEVEL"], logging.INFO)
    formatter = logging.Formatter(LOG_FORMAT)

    app.logger.handlers.clear()
    app.logger.setLevel(level)
    app.logger.propagate = False

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    app.logger.addHandler(stream_handler)

    log_file = app.config["LOG_FILE"]
    if log_file:
        os.makedirs(os.path.dirname(os.path.abspath(log_file)) or ".", exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file, maxBytes=1_000_000, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        app.logger.addHandler(file_handler)

    # A trilha de auditoria compartilha os handlers da aplicação.
    audit_logger = logging.getLogger("cafe.audit")
    audit_logger.handlers.clear()
    audit_logger.setLevel(level)
    audit_logger.propagate = False
    for handler in app.logger.handlers:
        audit_logger.addHandler(handler)

    logging.getLogger("app.seed").handlers.clear()
    logging.getLogger("app.seed").setLevel(level)
    logging.getLogger("app.seed").propagate = False
    for handler in app.logger.handlers:
        logging.getLogger("app.seed").addHandler(handler)


def register_extensions(app: Flask) -> None:
    db.init_app(app)
    migrate.init_app(app, db, directory=migrations_directory())
    csrf.init_app(app)
    limiter.init_app(app)


def migrations_directory() -> str:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "migrations")


def register_blueprints(app: Flask) -> None:
    from app import (
        models,  # noqa: F401  (registra os modelos no metadata)
        routes,
    )

    app.register_blueprint(routes.bp)


def register_security_headers(app: Flask) -> None:
    """Cabeçalhos aplicados a toda resposta.

    A CSP é restritiva porque o portal não carrega absolutamente nada de
    terceiros: fontes, imagens, CSS e JS são todos servidos por ``/static``.
    O único script inline da aplicação — o que aplica o tema antes da primeira
    pintura — é autorizado por um nonce gerado a cada requisição.
    """

    headers: dict[str, str] = app.config["SECURITY_HEADERS"]
    policy_template: str = app.config["CONTENT_SECURITY_POLICY"]
    hsts: str = app.config["HSTS_HEADER"]

    @app.before_request
    def generate_csp_nonce() -> None:
        g.csp_nonce = secrets.token_urlsafe(16)

    @app.context_processor
    def expose_csp_nonce() -> dict[str, Any]:
        return {"csp_nonce": lambda: getattr(g, "csp_nonce", "")}

    @app.after_request
    def apply_security_headers(response):
        for name, value in headers.items():
            response.headers.setdefault(name, value)

        response.headers.setdefault(
            "Content-Security-Policy",
            policy_template.format(nonce=getattr(g, "csp_nonce", "")),
        )

        if request.is_secure and hsts:
            response.headers.setdefault("Strict-Transport-Security", hsts)

        return response


def register_error_handlers(app: Flask) -> None:
    def wants_json() -> bool:
        return request.path.startswith("/api/") or request.is_json

    def respond(message: str, status_code: int, template: str):
        if wants_json():
            return jsonify({"success": False, "message": message}), status_code
        return render_template(template, message=message), status_code

    # As mensagens complementam o título da página em vez de repeti-lo: o
    # template já diz o que aconteceu, aqui vai o detalhe daquela requisição.
    @app.errorhandler(400)
    def handle_bad_request(error):
        return respond("O servidor não entendeu os dados enviados.", 400, "errors/400.html")

    @app.errorhandler(401)
    def handle_unauthorized(error):
        return respond(
            "Entre com a senha do perfil correspondente para continuar.",
            401,
            "errors/401.html",
        )

    @app.errorhandler(404)
    def handle_not_found(error):
        return respond(
            f"O caminho {request.path} não corresponde a nenhuma página do portal.",
            404,
            "errors/404.html",
        )

    @app.errorhandler(413)
    def handle_payload_too_large(error):
        return respond(
            "O envio excedeu o tamanho máximo aceito pelo servidor.", 413, "errors/400.html"
        )

    @app.errorhandler(429)
    def handle_rate_limited(error):
        app.logger.warning("Limite de requisições atingido em %s.", request.path)
        return respond(
            "O limite de envios desta origem foi atingido temporariamente.",
            429,
            "errors/429.html",
        )

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        app.logger.warning("Requisição recusada por falha de CSRF em %s.", request.path)
        return respond(
            "A sessão desta página expirou. Recarregue antes de enviar de novo.",
            400,
            "errors/400.html",
        )

    @app.errorhandler(500)
    def handle_server_error(error):
        app.logger.exception("Erro não tratado em %s.", request.path)
        db.session.rollback()
        return respond(
            "A operação foi interrompida e nada foi gravado pela metade.",
            500,
            "errors/500.html",
        )


def register_commands(app: Flask) -> None:
    @app.cli.command("init-db")
    @click.option(
        "--create-tables/--no-create-tables",
        default=False,
        help="Cria o esquema direto, sem migrations. Use apenas em desenvolvimento.",
    )
    def init_db_command(create_tables: bool) -> None:
        """Semeia o catálogo inicial sem sobrescrever o que já existe."""

        from app.seed import seed_database

        if create_tables:
            db.create_all()

        created = seed_database()
        click.echo(
            "Catálogo verificado. Criados: "
            f"{created['offices']} escritórios, "
            f"{created['spaces']} salas, "
            f"{created['products']} insumos."
        )

    @app.cli.command("check-config")
    def check_config_command() -> None:
        """Mostra a configuração efetiva, sem revelar segredos."""

        from config import DEFAULT_SECRET_KEY

        secret_ok = app.config["SECRET_KEY"] != DEFAULT_SECRET_KEY
        click.echo(f"Ambiente:        {app.config.get('ENV_NAME')}")
        click.echo(f"Debug:           {app.config['DEBUG']}")
        click.echo(f"Banco:           {app.config['SQLALCHEMY_DATABASE_URI']}")
        click.echo(f"Auto create DB:  {app.config['AUTO_CREATE_DB']}")
        click.echo(f"SECRET_KEY:      {'definida' if secret_ok else 'PADRÃO INSEGURO'}")
        click.echo(f"Senha admin:     {'definida' if app.config['ADMIN_PASSWORD'] else 'ausente'}")
        click.echo(f"Senha copa:      {'definida' if app.config['COPA_PASSWORD'] else 'ausente'}")
        click.echo(f"CSRF:            {app.config['WTF_CSRF_ENABLED']}")
        click.echo(f"Rate limit:      {app.config['RATELIMIT_ENABLED']}")
        click.echo(f"Cookie seguro:   {app.config['SESSION_COOKIE_SECURE']}")


def initialize_database() -> None:
    """Atalho de desenvolvimento: cria o esquema e semeia o catálogo."""

    from app.seed import seed_database

    db.create_all()
    seed_database()


def audit(action: str, **details: Any) -> None:
    """Registra uma ação relevante na trilha de auditoria."""

    from app.security import current_roles

    logger = logging.getLogger("cafe.audit")
    parts = " ".join(f"{key}={value!r}" for key, value in details.items())
    roles = ",".join(sorted(current_roles())) or "anonimo"
    logger.info("%s perfil=%s ip=%s %s", action, roles, request.remote_addr, parts)
