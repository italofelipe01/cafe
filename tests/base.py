"""Base compartilhada pelos testes.

Cada teste roda contra um SQLite em memória, criado e destruído no ciclo de
``setUp``/``tearDown``. Nada toca o banco local.
"""

from __future__ import annotations

import unittest
from typing import TypeVar

from app import create_app
from app.extensions import db

ADMIN_PASSWORD = "admin-teste"
COPA_PASSWORD = "copa-teste"

ModelT = TypeVar("ModelT")


def get_or_fail(model: type[ModelT], primary_key: object) -> ModelT:
    """``db.session.get`` que falha na hora se o registro não existir.

    ``get`` devolve ``Model | None``. Nos testes o registro sempre precisa
    existir — se não existe, o teste é que está errado —, então a asserção vem
    antes: ela dá uma mensagem melhor do que um ``AttributeError`` em ``None``
    e deixa o tipo resolvido para quem lê o código e para o verificador.
    """

    instance = db.session.get(model, primary_key)
    assert instance is not None, (
        f"{model.__name__} {primary_key!r} não foi encontrado no banco."
    )
    return instance


class AppTestCase(unittest.TestCase):
    """Aplicação de teste com catálogo semeado e helpers de autenticação."""

    def setUp(self) -> None:
        self.app = create_app("testing")
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()

    # -- autenticação ----------------------------------------------------- #

    def login(self, password: str = ADMIN_PASSWORD):
        """Autentica o cliente de teste no perfil correspondente à senha."""

        return self.client.post(
            "/login", data={"password": password}, follow_redirects=True
        )

    def login_as_admin(self):
        return self.login(ADMIN_PASSWORD)

    def login_as_copa(self):
        return self.login(COPA_PASSWORD)

    def logout(self):
        return self.client.post("/logout", follow_redirects=True)

    # -- atalhos ----------------------------------------------------------- #

    def fetch(self, model: type[ModelT], primary_key: object) -> ModelT:
        """Atalho de instância para :func:`get_or_fail`."""

        return get_or_fail(model, primary_key)

    def submit_order(self, **items: str):
        payload = {"office": "EBM Office Goiânia", "room": "Sala Aton"}
        payload.update(items)
        return self.client.post("/submit_form", data=payload)
