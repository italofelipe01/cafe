"""Configuração da aplicação, por ambiente.

Os atributos das classes são apenas os padrões declarativos. A leitura das
variáveis de ambiente acontece em ``init_app``, no momento em que a aplicação
é criada — nunca no import do módulo. Isso permite que scripts e testes ajustem
``os.environ`` depois de importar este arquivo e ainda sejam obedecidos.

Variável definida mas vazia vale o mesmo que variável ausente: o padrão do
ambiente. É o que faz um ``.env`` copiado do modelo, com ``ADMIN_PASSWORD=``
ainda em branco, continuar subindo em desenvolvimento com as senhas de
desenvolvimento, e continuar recusando subir em produção.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import timedelta
from typing import Any, NamedTuple

DEFAULT_SECRET_KEY = "dev-only-secret-key"

# Chaves que já apareceram em arquivo versionado. Quem leu o repositório
# conhece todas, então nenhuma protege sessão de verdade.
INSECURE_SECRET_KEYS = frozenset({DEFAULT_SECRET_KEY, "troque-esta-chave-em-producao"})

TRUE_VALUES = {"1", "true", "yes", "on"}


class ServerSettings(NamedTuple):
    """Endereço de escuta do servidor, com os tipos já resolvidos."""

    host: str
    port: int
    threads: int


def env_raw(name: str) -> str | None:
    """Valor da variável, ou ``None`` se ela estiver ausente ou em branco."""

    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return None
    return raw


def env_bool(name: str, default: bool) -> bool:
    raw = env_raw(name)
    if raw is None:
        return default
    return raw.strip().lower() in TRUE_VALUES


def env_int(name: str, default: int) -> int:
    raw = env_raw(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"A variável {name} precisa ser um número inteiro.") from exc


def env_str(name: str, default: str) -> str:
    raw = env_raw(name)
    return default if raw is None else raw


def normalize_database_url(url: str) -> str:
    """Ajusta a URL de banco que os provedores de nuvem entregam.

    Heroku, Render, Railway e afins publicam ``postgres://...``, esquema que o
    SQLAlchemy 2 recusa. Sem driver explícito, o SQLAlchemy ainda escolheria o
    psycopg2, e o driver instalado pelo projeto é o psycopg 3. Uma URL com
    driver explícito (``postgresql+psycopg2://``) é respeitada como veio.
    """

    scheme, separator, rest = url.partition("://")
    if separator and scheme in {"postgres", "postgresql"}:
        return f"postgresql+psycopg://{rest}"
    return url


def is_memory_database(url: str) -> bool:
    return url in {"sqlite://", "sqlite:///:memory:"} or "mode=memory" in url


class Config:
    """Padrões compartilhados por todos os ambientes."""

    ENV_NAME = "default"

    # Exige SECRET_KEY própria e as duas senhas. Desenvolvimento e testes têm
    # valores conhecidos de propósito; qualquer outro ambiente, não.
    REQUIRE_SECURE_CONFIG = True

    SECRET_KEY = DEFAULT_SECRET_KEY
    DEBUG = False
    TESTING = False

    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Cria o esquema com db.create_all() e semeia o catálogo dentro de
    # create_app(). Serve ao banco em memória; não aplica migrations.
    AUTO_CREATE_DB = True

    # Aplica as migrations (o mesmo que `flask db upgrade`) quando o servidor
    # sobe por run.py, e semeia o catálogo se o banco estiver vazio. Fica fora
    # de create_app() para que os comandos `flask db ...` continuem fazendo só
    # o que se pede a eles.
    AUTO_MIGRATE = False

    APP_HOST = "127.0.0.1"
    APP_PORT = 5000
    WAITRESS_THREADS = 4

    # Quantos proxies reversos confiáveis ficam à frente da aplicação (nginx,
    # balanceador da nuvem). Com 0, X-Forwarded-* é ignorado: confiar nele sem
    # proxy deixaria qualquer cliente escolher o próprio IP no rate limit.
    TRUST_PROXY_HOPS = 0

    # Endereço público do portal, usado nos links e QR codes das salas. Vazio
    # significa o endereço pelo qual a página foi aberta.
    PUBLIC_BASE_URL = ""

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
    # Em memória vale por processo. Com mais de uma instância (nuvem), aponte
    # para um armazenamento compartilhado, como redis://.
    RATELIMIT_STORAGE_URI = "memory://"
    RATELIMIT_ORDER = "30 per minute"
    RATELIMIT_LOGIN = "10 per minute"

    # Minutos de espera a partir dos quais o painel da copa destaca o pedido.
    ORDER_WARN_MINUTES = 5
    ORDER_LATE_MINUTES = 10

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
        "manifest-src 'self'; "
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

        ``PORT`` é a variável que Render, Railway, Heroku e Cloud Run definem;
        ``APP_PORT``, quando presente, vence.
        """

        return ServerSettings(
            host=env_str("APP_HOST", cls.APP_HOST),
            port=env_int("APP_PORT", env_int("PORT", cls.APP_PORT)),
            threads=env_int("WAITRESS_THREADS", cls.WAITRESS_THREADS),
        )

    @classmethod
    def init_app(cls, app: Any) -> None:
        """Aplica as variáveis de ambiente sobre os padrões da classe."""

        overrides: dict[str, Callable[[], Any]] = {
            "SECRET_KEY": lambda: env_str("SECRET_KEY", cls.SECRET_KEY),
            "DEBUG": lambda: env_bool("DEBUG", cls.DEBUG),
            "SQLALCHEMY_DATABASE_URI": lambda: normalize_database_url(
                env_str("DATABASE_URL", cls.SQLALCHEMY_DATABASE_URI)
            ),
            "AUTO_CREATE_DB": lambda: env_bool("AUTO_CREATE_DB", cls.AUTO_CREATE_DB),
            "AUTO_MIGRATE": lambda: env_bool("AUTO_MIGRATE", cls.AUTO_MIGRATE),
            "TRUST_PROXY_HOPS": lambda: env_int("TRUST_PROXY_HOPS", cls.TRUST_PROXY_HOPS),
            "PUBLIC_BASE_URL": lambda: env_str(
                "PUBLIC_BASE_URL", cls.PUBLIC_BASE_URL
            ).rstrip("/"),
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
            "RATELIMIT_STORAGE_URI": lambda: env_str(
                "RATELIMIT_STORAGE_URI", cls.RATELIMIT_STORAGE_URI
            ),
            "ORDER_WARN_MINUTES": lambda: env_int(
                "ORDER_WARN_MINUTES", cls.ORDER_WARN_MINUTES
            ),
            "ORDER_LATE_MINUTES": lambda: env_int(
                "ORDER_LATE_MINUTES", cls.ORDER_LATE_MINUTES
            ),
            "LOG_LEVEL": lambda: env_str("LOG_LEVEL", cls.LOG_LEVEL).upper(),
            "LOG_FILE": lambda: env_str("LOG_FILE", cls.LOG_FILE),
        }

        for key, read_value in overrides.items():
            app.config[key] = read_value()

        apply_engine_options(app)

        # Fonte única: a aplicação e o run.py leem os mesmos três valores.
        server = cls.server_settings()
        app.config["APP_HOST"] = server.host
        app.config["APP_PORT"] = server.port
        app.config["WAITRESS_THREADS"] = server.threads

        cls.validate(app)

    @classmethod
    def validate(cls, app: Any) -> None:
        """Impede que a aplicação suba com uma configuração insegura.

        A régua é o ambiente, e não o ``DEBUG``: ligar a depuração em produção
        não pode servir de atalho para subir com a chave de sessão conhecida.
        """

        if not cls.REQUIRE_SECURE_CONFIG:
            return

        if app.config["SECRET_KEY"] in INSECURE_SECRET_KEYS:
            raise RuntimeError(
                "Defina SECRET_KEY no ambiente antes de subir fora de desenvolvimento. "
                "Gere uma com: python -c \"import secrets; print(secrets.token_hex(32))\" "
                "ou rode: python run.py --setup"
            )

        if not app.config["ADMIN_PASSWORD"]:
            raise RuntimeError(
                "Defina ADMIN_PASSWORD no ambiente para liberar o painel administrativo."
            )

        if not app.config["COPA_PASSWORD"]:
            raise RuntimeError(
                "Defina COPA_PASSWORD no ambiente para liberar o painel da copa."
            )


def apply_engine_options(app: Any) -> None:
    """Opções de conexão que dependem do banco escolhido.

    Fora do SQLite, ``pool_pre_ping`` descarta conexões que o servidor do banco
    encerrou por ociosidade — situação comum em bancos gerenciados na nuvem, que
    sem isso viraria um erro 500 na primeira requisição depois da pausa.
    """

    if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
        return

    options = dict(app.config.get("SQLALCHEMY_ENGINE_OPTIONS") or {})
    options.setdefault("pool_pre_ping", True)
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = options


class DevelopmentConfig(Config):
    ENV_NAME = "development"
    REQUIRE_SECURE_CONFIG = False
    DEBUG = True
    ADMIN_PASSWORD = "admin"
    COPA_PASSWORD = "copa"


class TestingConfig(Config):
    ENV_NAME = "testing"
    REQUIRE_SECURE_CONFIG = False
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

        app.config["SQLALCHEMY_DATABASE_URI"] = normalize_database_url(
            env_str("DATABASE_URL", cls.SQLALCHEMY_DATABASE_URI)
        )
        apply_engine_options(app)


class ProductionConfig(Config):
    ENV_NAME = "production"
    DEBUG = False
    # O esquema vem das migrations: create_all() não evolui um banco existente.
    AUTO_CREATE_DB = False
    # O servidor aplica as migrations pendentes ao subir. Com várias instâncias
    # subindo juntas, desligue e rode `flask db upgrade` uma vez antes.
    AUTO_MIGRATE = True
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
        or env_raw("APP_ENV")
        or env_raw("FLASK_ENV")
        or "default"
    ).strip().lower()

    if name not in CONFIG_BY_NAME:
        valid = ", ".join(sorted(CONFIG_BY_NAME))
        raise ValueError(f"Ambiente '{name}' desconhecido. Use um de: {valid}.")

    return CONFIG_BY_NAME[name]
