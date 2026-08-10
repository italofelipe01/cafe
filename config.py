"""Configuração da aplicação, por ambiente.

Os atributos das classes são apenas os padrões declarativos. A leitura das
variáveis de ambiente acontece em ``init_app``, no momento em que a aplicação
é criada — nunca no import do módulo. Isso permite que scripts e testes ajustem
``os.environ`` depois de importar este arquivo e ainda sejam obedecidos.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import timedelta
from typing import Any, NamedTuple

DEFAULT_SECRET_KEY = "dev-only-secret-key"
TRUE_VALUES = {"1", "true", "yes", "on"}


class ServerSettings(NamedTuple):
    """Endereço de escuta do servidor, com os tipos já resolvidos."""

    host: str
    port: int
    threads: int


def env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in TRUE_VALUES


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"A variável {name} precisa ser um número inteiro.") from exc


def env_str(name: str, default: str) -> str:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw


class Config:
    """Padrões compartilhados por todos os ambientes."""

    ENV_NAME = "default"

    SECRET_KEY = DEFAULT_SECRET_KEY
    DEBUG = False
    TESTING = False

    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Cria o esquema e semeia o catálogo na inicialização. Conveniente para o
    # banco em memória; em produção o esquema é responsabilidade das migrations.
    AUTO_CREATE_DB = True

    APP_HOST = "127.0.0.1"
    APP_PORT = 5000
    WAITRESS_THREADS = 4

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)

    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None

    # Senhas de acesso aos painéis. Vazio significa "painel indisponível".
    ADMIN_PASSWORD = ""
    COPA_PASSWORD = ""

    RATELIMIT_ENABLED = True
    RATELIMIT_ORDER = "30 per minute"
    RATELIMIT_LOGIN = "10 per minute"

    # Corpo de requisição máximo aceito (256 KB cobre com folga os formulários).
    MAX_CONTENT_LENGTH = 256 * 1024

    LOG_LEVEL = "INFO"
    LOG_FILE = ""

    # Cabeçalhos de segurança aplicados a toda resposta.
    SECURITY_HEADERS: dict[str, str] = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "same-origin",
        "Cross-Origin-Opener-Policy": "same-origin",
    }

    # O portal não carrega nada de terceiros: fontes, imagens, CSS e JS saem
    # todos de /static. O único script inline é o que aplica o tema antes da
    # primeira pintura, e ele é liberado por nonce — nunca por 'unsafe-inline'.
    CONTENT_SECURITY_POLICY = (
        "default-src 'self'; "
        "img-src 'self' data:; "
        "style-src 'self'; "
        "script-src 'self' 'nonce-{nonce}'; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "form-action 'self'; "
        "base-uri 'none'; "
        "frame-ancestors 'none'; "
        "object-src 'none'"
    )
    HSTS_HEADER = "max-age=31536000; includeSubDomains"

    @classmethod
    def server_settings(cls) -> ServerSettings:
        """Host, porta e threads do servidor, lidos do ambiente.

        Separado de ``init_app`` porque o processo pai de ``run.py --background``
        precisa desses três valores apenas para imprimir o log de inicialização.
        Criar uma aplicação inteira só para isso abriria outra conexão de banco e
        dispararia mais uma semeadura, contra um banco descartado em seguida.
        """

        return ServerSettings(
            host=env_str("APP_HOST", cls.APP_HOST),
            port=env_int("APP_PORT", cls.APP_PORT),
            threads=env_int("WAITRESS_THREADS", cls.WAITRESS_THREADS),
        )

    @classmethod
    def init_app(cls, app: Any) -> None:
        """Aplica as variáveis de ambiente sobre os padrões da classe."""

        overrides: dict[str, Callable[[], Any]] = {
            "SECRET_KEY": lambda: env_str("SECRET_KEY", cls.SECRET_KEY),
            "DEBUG": lambda: env_bool("DEBUG", cls.DEBUG),
            "SQLALCHEMY_DATABASE_URI": lambda: env_str(
                "DATABASE_URL", cls.SQLALCHEMY_DATABASE_URI
            ),
            "AUTO_CREATE_DB": lambda: env_bool("AUTO_CREATE_DB", cls.AUTO_CREATE_DB),
            "SESSION_COOKIE_SAMESITE": lambda: env_str(
                "SESSION_COOKIE_SAMESITE", cls.SESSION_COOKIE_SAMESITE
            ),
            "SESSION_COOKIE_SECURE": lambda: env_bool(
                "SESSION_COOKIE_SECURE", cls.SESSION_COOKIE_SECURE
            ),
            "ADMIN_PASSWORD": lambda: env_str("ADMIN_PASSWORD", cls.ADMIN_PASSWORD),
            "COPA_PASSWORD": lambda: env_str("COPA_PASSWORD", cls.COPA_PASSWORD),
            "RATELIMIT_ENABLED": lambda: env_bool(
                "RATELIMIT_ENABLED", cls.RATELIMIT_ENABLED
            ),
            "LOG_LEVEL": lambda: env_str("LOG_LEVEL", cls.LOG_LEVEL).upper(),
            "LOG_FILE": lambda: env_str("LOG_FILE", cls.LOG_FILE),
        }

        for key, read_value in overrides.items():
            app.config[key] = read_value()

        # Fonte única: a aplicação e o run.py leem os mesmos três valores.
        server = cls.server_settings()
        app.config["APP_HOST"] = server.host
        app.config["APP_PORT"] = server.port
        app.config["WAITRESS_THREADS"] = server.threads

        cls.validate(app)

    @classmethod
    def validate(cls, app: Any) -> None:
        """Impede que a aplicação suba com uma configuração insegura."""

        if app.config["TESTING"] or app.config["DEBUG"]:
            return

        if app.config["SECRET_KEY"] == DEFAULT_SECRET_KEY:
            raise RuntimeError(
                "Defina SECRET_KEY no ambiente antes de subir fora de desenvolvimento. "
                "Gere uma com: python -c \"import secrets; print(secrets.token_hex(32))\""
            )

        if not app.config["ADMIN_PASSWORD"]:
            raise RuntimeError(
                "Defina ADMIN_PASSWORD no ambiente para liberar o painel administrativo."
            )

        if not app.config["COPA_PASSWORD"]:
            raise RuntimeError(
                "Defina COPA_PASSWORD no ambiente para liberar o painel da copa."
            )


class DevelopmentConfig(Config):
    ENV_NAME = "development"
    DEBUG = True
    ADMIN_PASSWORD = "admin"
    COPA_PASSWORD = "copa"


class TestingConfig(Config):
    ENV_NAME = "testing"
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    ADMIN_PASSWORD = "admin-teste"
    COPA_PASSWORD = "copa-teste"
    LOG_LEVEL = "CRITICAL"

    @classmethod
    def init_app(cls, app: Any) -> None:
        """Os testes controlam o próprio ambiente, exceto o banco de dados."""

        app.config["SQLALCHEMY_DATABASE_URI"] = env_str(
            "DATABASE_URL", cls.SQLALCHEMY_DATABASE_URI
        )


class ProductionConfig(Config):
    ENV_NAME = "production"
    DEBUG = False
    # O esquema passa a ser responsabilidade do `flask db upgrade`.
    AUTO_CREATE_DB = False
    SESSION_COOKIE_SECURE = True


CONFIG_BY_NAME: dict[str, type[Config]] = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}


def resolve_config(config_name: str | None = None) -> type[Config]:
    """Descobre a classe de configuração a usar.

    A ordem é: argumento explícito, variável ``APP_ENV``, variável ``FLASK_ENV``
    e, por fim, ``development``.
    """

    name = (
        config_name
        or os.environ.get("APP_ENV")
        or os.environ.get("FLASK_ENV")
        or "default"
    ).strip().lower()

    if name not in CONFIG_BY_NAME:
        valid = ", ".join(sorted(CONFIG_BY_NAME))
        raise ValueError(f"Ambiente '{name}' desconhecido. Use um de: {valid}.")

    return CONFIG_BY_NAME[name]
