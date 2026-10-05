"""Testes de operação: configuração por ambiente, preparo do banco e run.py.

Cobrem o caminho de "subir sem passo manual": um .env copiado do modelo, um .env
gerado por ``run.py --setup``, as migrations aplicadas pelo próprio servidor e
os ajustes de nuvem (porta, proxy, URL do PostgreSQL).
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
import unittest
import uuid
from unittest import mock

from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

import run
from app import create_app, prepare_database
from app.extensions import db
from app.models import Office, Order
from config import normalize_database_url

# Variáveis que um teste daqui pode ler. Cada teste parte delas vazias, para não
# herdar nada do ambiente de quem roda a suíte.
CONFIG_VARS = [
    "APP_ENV", "FLASK_ENV", "SECRET_KEY", "ADMIN_PASSWORD", "COPA_PASSWORD",
    "DEBUG", "DATABASE_URL", "AUTO_CREATE_DB", "AUTO_MIGRATE", "APP_HOST",
    "APP_PORT", "PORT", "TRUST_PROXY_HOPS", "RATELIMIT_STORAGE_URI",
    "PUBLIC_BASE_URL", "SESSION_COOKIE_SECURE", "LOG_FILE",
]


def clean_env(**values: str):
    env = dict.fromkeys(CONFIG_VARS, "")
    env.update(values)
    env["LOG_LEVEL"] = "CRITICAL"
    return mock.patch.dict(os.environ, env)


class TestBlankMeansDefault(unittest.TestCase):
    def test_env_example_copiado_sobe_em_desenvolvimento(self):
        # Exatamente o que o .env.example traz: senhas em branco e DEBUG=false.
        # Antes, isso derrubava a subida com "Defina ADMIN_PASSWORD".
        with clean_env(APP_ENV="development", DEBUG="false", ADMIN_PASSWORD="",
                       COPA_PASSWORD="", SECRET_KEY=""):
            app = create_app()

        self.assertEqual(app.config["ADMIN_PASSWORD"], "admin")
        self.assertEqual(app.config["COPA_PASSWORD"], "copa")
        self.assertFalse(app.config["DEBUG"])

    def test_banco_em_branco_vale_o_padrao(self):
        with clean_env(DATABASE_URL="   "):
            app = create_app("development")
        self.assertEqual(app.config["SQLALCHEMY_DATABASE_URI"], "sqlite:///:memory:")


class TestProductionValidation(unittest.TestCase):
    def test_debug_ligado_nao_dispensa_a_validacao(self):
        with clean_env(DEBUG="true"), self.assertRaises(RuntimeError) as contexto:
            create_app("production")
        self.assertIn("SECRET_KEY", str(contexto.exception))

    def test_chave_do_modelo_e_recusada(self):
        with clean_env(SECRET_KEY="troque-esta-chave-em-producao", ADMIN_PASSWORD="a",
                       COPA_PASSWORD="c"), self.assertRaises(RuntimeError):
            create_app("production")

    def test_producao_aplica_migrations_ao_subir(self):
        with clean_env(SECRET_KEY="k" * 32, ADMIN_PASSWORD="a", COPA_PASSWORD="c"):
            app = create_app("production")
        self.assertTrue(app.config["AUTO_MIGRATE"])
        self.assertFalse(app.config["AUTO_CREATE_DB"])


class TestCloudSettings(unittest.TestCase):
    def test_porta_da_plataforma(self):
        with clean_env(PORT="8080"):
            self.assertEqual(create_app("development").config["APP_PORT"], 8080)

        with clean_env(PORT="8080", APP_PORT="9000"):
            self.assertEqual(create_app("development").config["APP_PORT"], 9000)

    def test_url_do_postgres(self):
        self.assertEqual(
            normalize_database_url("postgres://u:p@h:5432/copa"),
            "postgresql+psycopg://u:p@h:5432/copa",
        )
        self.assertEqual(
            normalize_database_url("postgresql://u:p@h/copa"),
            "postgresql+psycopg://u:p@h/copa",
        )
        # Driver explícito é respeitado.
        self.assertEqual(
            normalize_database_url("postgresql+psycopg2://u:p@h/copa"),
            "postgresql+psycopg2://u:p@h/copa",
        )
        self.assertEqual(normalize_database_url("sqlite:///copa.db"), "sqlite:///copa.db")

    def test_proxy_confiavel_entrega_o_ip_do_cliente(self):
        with clean_env(TRUST_PROXY_HOPS="1"):
            app = create_app("development")

        @app.route("/_ip")
        def _ip():
            from flask import request

            return f"{request.remote_addr} {request.scheme}"

        response = app.test_client().get(
            "/_ip",
            headers={"X-Forwarded-For": "203.0.113.7", "X-Forwarded-Proto": "https"},
        )
        self.assertEqual(response.get_data(as_text=True), "203.0.113.7 https")

    def test_sem_proxy_o_cabecalho_e_ignorado(self):
        with clean_env():
            app = create_app("development")

        @app.route("/_ip")
        def _ip():
            from flask import request

            return request.remote_addr or ""

        response = app.test_client().get(
            "/_ip", headers={"X-Forwarded-For": "203.0.113.7"}
        )
        self.assertNotEqual(response.get_data(as_text=True), "203.0.113.7")

    def test_armazenamento_do_rate_limit_configuravel(self):
        with clean_env(RATELIMIT_STORAGE_URI="memory://"):
            app = create_app("development")
        self.assertEqual(app.config["RATELIMIT_STORAGE_URI"], "memory://")


class FileDatabaseTestCase(unittest.TestCase):
    """Banco SQLite em arquivo temporário, como numa instalação de verdade."""

    def setUp(self) -> None:
        self.db_path = os.path.join(
            tempfile.gettempdir(), f"cafe-op-{uuid.uuid4().hex}.db"
        )
        self.env = clean_env(
            DATABASE_URL="sqlite:///" + self.db_path.replace("\\", "/"),
            AUTO_CREATE_DB="false",
        )
        self.env.start()
        # O env.py do Alembic reconfigura o logging a cada execução; no teste
        # isso só espalharia linhas de INFO pela saída da suíte.
        self.file_config = mock.patch("logging.config.fileConfig")
        self.file_config.start()
        self.app = create_app("development")

    def tearDown(self) -> None:
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()
        self.file_config.stop()
        self.env.stop()
        for suffix in ("", "-wal", "-shm"):
            if os.path.exists(self.db_path + suffix):
                os.remove(self.db_path + suffix)


class TestPrepareDatabase(FileDatabaseTestCase):
    def test_primeira_subida_aplica_migrations_e_semeia(self):
        with self.app.app_context():
            resumo = prepare_database()
            tabelas = set(inspect(db.engine).get_table_names())

            self.assertIn("alembic_version", tabelas)
            self.assertIn("order", tabelas)
            self.assertEqual(Office.query.count(), 3)
            self.assertIn("catálogo inicial semeado", resumo)

    def test_subidas_seguintes_preservam_o_catalogo(self):
        with self.app.app_context():
            prepare_database()
            office = Office.query.filter_by(name="Sede Centro").one()
            office.name = "Matriz"
            db.session.commit()

            resumo = prepare_database()

            # A semeadura aditiva recriaria "Sede Centro" ao lado de "Matriz".
            self.assertIsNone(Office.query.filter_by(name="Sede Centro").first())
            self.assertIn("catálogo existente preservado", resumo)

    def test_banco_criado_por_create_all_pede_stamp(self):
        with self.app.app_context():
            db.create_all()
            with self.assertRaises(RuntimeError) as contexto:
                prepare_database()
        self.assertIn("flask db stamp head", str(contexto.exception))

    def test_chave_estrangeira_e_verificada(self):
        with self.app.app_context():
            prepare_database()
            self.assertEqual(db.session.execute(text("PRAGMA foreign_keys")).scalar(), 1)

            db.session.add(Order(office_id=999, space_id=999))
            with self.assertRaises(IntegrityError):
                db.session.commit()
            db.session.rollback()


class TestBackup(FileDatabaseTestCase):
    def test_copia_consistente_com_rotacao(self):
        with self.app.app_context():
            prepare_database()

        pasta = tempfile.mkdtemp(prefix="cafe-backup-")
        # Duas cópias antigas: com --keep 2, só a mais nova delas sobrevive.
        for antigo in ("copa-20200101-000000.db", "copa-20200102-000000.db"):
            open(os.path.join(pasta, antigo), "w").close()

        resultado = self.app.test_cli_runner().invoke(
            args=["backup-db", "--dir", pasta, "--keep", "2"]
        )

        self.assertEqual(resultado.exit_code, 0, resultado.output)
        arquivos = sorted(os.listdir(pasta))
        self.assertEqual(len(arquivos), 2)
        self.assertEqual(arquivos[0], "copa-20200102-000000.db")

        copia = sqlite3.connect(os.path.join(pasta, arquivos[1]))
        try:
            self.assertEqual(copia.execute("SELECT COUNT(*) FROM office").fetchone()[0], 3)
        finally:
            copia.close()
        shutil.rmtree(pasta)

    def test_banco_em_memoria_nao_tem_backup(self):
        with clean_env():
            app = create_app("development")
        resultado = app.test_cli_runner().invoke(args=["backup-db"])
        self.assertNotEqual(resultado.exit_code, 0)
        self.assertIn("SQLite em arquivo", resultado.output)


class TestRunScript(unittest.TestCase):
    def test_setup_gera_configuracao_que_sobe_em_producao(self):
        content, passwords = run.build_env_file("192.168.0.10")
        values = dict(
            line.split("=", 1)
            for line in content.splitlines()
            if line and not line.startswith("#")
        )

        self.assertEqual(values["APP_ENV"], "production")
        self.assertEqual(values["ADMIN_PASSWORD"], passwords["ADMIN_PASSWORD"])
        self.assertNotEqual(values["ADMIN_PASSWORD"], values["COPA_PASSWORD"])
        self.assertEqual(values["PUBLIC_BASE_URL"], "http://192.168.0.10:5000")

        values["DATABASE_URL"] = "sqlite:///:memory:"
        values["LOG_FILE"] = ""
        with clean_env(**values):
            app = create_app()

        self.assertEqual(app.config["ENV_NAME"], "production")
        self.assertFalse(app.config["SESSION_COOKIE_SECURE"])
        self.assertEqual(run.config_warnings(app.config), [])

    def test_cada_setup_gera_segredos_novos(self):
        primeiro, _ = run.build_env_file()
        segundo, _ = run.build_env_file()
        self.assertNotEqual(primeiro, segundo)

    def test_avisos_de_configuracao(self):
        with clean_env(APP_HOST="0.0.0.0"):
            dev = create_app("development")
        self.assertTrue(any("desenvolvimento exposto" in w for w in run.config_warnings(dev.config)))

        with clean_env(SECRET_KEY="k" * 32, ADMIN_PASSWORD="a", COPA_PASSWORD="c",
                       DATABASE_URL="sqlite:///:memory:"):
            prod = create_app("production")
        self.assertTrue(any("SESSION_COOKIE_SECURE" in w for w in run.config_warnings(prod.config)))

    def test_comando_para_desligar(self):
        self.assertIn("123", run.stop_hint(123))


if __name__ == "__main__":
    unittest.main()
