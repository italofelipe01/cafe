"""Instâncias das extensões Flask, isoladas para evitar imports circulares."""

import sqlite3
from typing import TYPE_CHECKING, Any

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import event
from sqlalchemy.engine import Engine

db = SQLAlchemy()


@event.listens_for(Engine, "connect")
def configure_sqlite_connection(dbapi_connection: Any, _record: Any) -> None:
    """Ajusta cada conexão SQLite aberta pela aplicação.

    ``foreign_keys``: o SQLite só verifica chave estrangeira quando pedido, a
    cada conexão. Sem isso, um pedido podia apontar para uma sala inexistente.

    ``journal_mode=WAL``: leitura e escrita deixam de se bloquear. O painel da
    copa consulta a cada poucos segundos enquanto as salas gravam pedidos, e no
    modo padrão cada gravação travava as leituras. Em banco na memória o SQLite
    ignora o pedido e segue no modo dele.
    """

    if not isinstance(dbapi_connection, sqlite3.Connection):
        return

    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
    finally:
        cursor.close()


class ModelBase(db.Model):
    """Base abstrata dos modelos do portal.

    Existe por um motivo só: o construtor que o SQLAlchemy gera em tempo de
    execução aceita os campos mapeados como argumentos nomeados, mas essa
    assinatura não chega ao verificador de tipos através de ``db.Model``, e
    todo ``Office(name=...)`` era reportado como parâmetro inexistente.

    ``__abstract__`` mantém a classe fora do mapeamento: ela não vira tabela e
    não aparece nas migrations.
    """

    __abstract__ = True

    if TYPE_CHECKING:

        def __init__(self, **kwargs: Any) -> None: ...
migrate = Migrate()
csrf = CSRFProtect()
# O armazenamento vem de RATELIMIT_STORAGE_URI: um argumento aqui venceria a
# configuração e prenderia o limite à memória do processo mesmo na nuvem.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    headers_enabled=True,
)
