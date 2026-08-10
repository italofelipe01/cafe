"""Instâncias das extensões Flask, isoladas para evitar imports circulares."""

from typing import TYPE_CHECKING, Any

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()


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
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="memory://",
    default_limits=[],
    headers_enabled=True,
)
