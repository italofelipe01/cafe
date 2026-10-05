"""Cópia de segurança do banco SQLite.

Com o modo WAL, as gravações recentes moram no arquivo ``-wal`` até o próximo
checkpoint: copiar só o ``.db`` com o servidor no ar pode perder os últimos
pedidos. A API de backup do SQLite copia um retrato consistente, mesmo com a
aplicação gravando ao mesmo tempo.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime

from sqlalchemy.engine import make_url

BACKUP_PREFIX = "copa-"
BACKUP_SUFFIX = ".db"


def sqlite_path(database_url: str) -> str | None:
    """Caminho do arquivo do banco, ou ``None`` se não for SQLite em arquivo."""

    url = make_url(database_url)
    if url.get_backend_name() != "sqlite":
        return None
    database = url.database or ""
    if not database or database == ":memory:" or "mode=memory" in database_url:
        return None
    return database


def backup_sqlite(source: str, directory: str, keep: int) -> str:
    """Grava ``copa-AAAAMMDD-HHMMSS.db`` em ``directory`` e mantém as ``keep`` mais novas."""

    os.makedirs(directory, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = os.path.join(directory, f"{BACKUP_PREFIX}{stamp}{BACKUP_SUFFIX}")

    with sqlite3.connect(source) as origin, sqlite3.connect(target) as copy:
        origin.backup(copy)
    # O `with` do sqlite3 só encerra a transação; fechar libera o arquivo, o
    # que no Windows é condição para a rotação conseguir apagá-lo depois.
    origin.close()
    copy.close()

    backups = sorted(
        name
        for name in os.listdir(directory)
        if name.startswith(BACKUP_PREFIX) and name.endswith(BACKUP_SUFFIX)
    )
    for old in backups[: max(0, len(backups) - keep)]:
        os.remove(os.path.join(directory, old))

    return target
