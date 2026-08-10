"""Testes da camada de segurança: autenticação, CSRF, cabeçalhos e limites."""

from __future__ import annotations

import os
import unittest
from unittest import mock

from app import create_app
from app.extensions import limiter
from app.security import safe_redirect_target
from tests.base import ADMIN_PASSWORD, COPA_PASSWORD, AppTestCase

PROTECTED_GET_ROUTES = ["/copa", "/admin", "/admin/offices", "/admin/spaces",
                        "/admin/products", "/admin/history"]

PROTECTED_POST_ROUTES = [
    "/admin/offices",
    "/admin/spaces",
    "/admin/products",
    "/admin/offices/1/toggle",
    "/admin/spaces/1/toggle",
    "/admin/products/1/toggle",
]


class TestAuthentication(AppTestCase):
    def test_pedido_permanece_publico(self):
        # O formulário de pedido é aberto de propósito: quem está numa sala
        # precisa pedir café sem credencial.
        for path in ["/", "/health", "/login"]:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

        self.assertEqual(self.submit_order(copo="1").status_code, 200)

    def test_rotas_internas_exigem_login(self):
        for path in PROTECTED_GET_ROUTES:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/login", response.headers["Location"])

    def test_escritas_administrativas_exigem_login(self):
        for path in PROTECTED_POST_ROUTES:
            with self.subTest(path=path):
                response = self.client.post(path, data={"name": "X"})
                self.assertEqual(response.status_code, 302)
                self.assertIn("/login", response.headers["Location"])

    def test_senha_incorreta(self):
        response = self.client.post("/login", data={"password": "errada"})
        self.assertEqual(response.status_code, 401)
        self.assertIn(b"Senha incorreta", response.data)
        self.assertEqual(self.client.get("/admin").status_code, 302)

    def test_senha_vazia(self):
        response = self.client.post("/login", data={"password": ""})
        self.assertEqual(response.status_code, 401)

    def test_admin_tambem_acessa_a_copa(self):
        self.login(ADMIN_PASSWORD)
        self.assertEqual(self.client.get("/copa").status_code, 200)
        self.assertEqual(self.client.get("/admin").status_code, 200)

    def test_copa_nao_acessa_admin(self):
        self.login(COPA_PASSWORD)
        self.assertEqual(self.client.get("/copa").status_code, 200)
        self.assertEqual(self.client.get("/admin").status_code, 302)

    def test_logout_encerra_a_sessao(self):
        self.login(ADMIN_PASSWORD)
        self.assertEqual(self.client.get("/admin").status_code, 200)

        self.logout()
        self.assertEqual(self.client.get("/admin").status_code, 302)

    def test_login_preserva_o_destino(self):
        response = self.client.get("/admin/products")
        self.assertIn("next=/admin/products", response.headers["Location"])

        response = self.client.post(
            "/login",
            data={"password": ADMIN_PASSWORD, "next": "/admin/products"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/admin/products"))

    def test_destino_externo_e_ignorado(self):
        # Sem essa checagem, /login?next=https://exemplo.invalido viraria um
        # redirecionador aberto com o domínio do portal no endereço.
        for hostil in [
            "https://exemplo.invalido/phishing",
            "//exemplo.invalido/phishing",
            "http://exemplo.invalido",
            "javascript:alert(1)",
        ]:
            with self.subTest(destino=hostil):
                self.assertIsNone(safe_redirect_target(hostil))

        self.assertEqual(safe_redirect_target("/admin/products"), "/admin/products")
        self.assertIsNone(safe_redirect_target(None))

    def test_api_responde_json_quando_sem_sessao(self):
        response = self.client.get("/api/orders")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers["Content-Type"].split(";")[0], "application/json")


class TestSecurityHeaders(AppTestCase):
    def test_cabecalhos_presentes(self):
        response = self.client.get("/")

        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertEqual(response.headers["Referrer-Policy"], "same-origin")
        self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])
        self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])

    def test_csp_usa_nonce_novo_a_cada_requisicao(self):
        primeira = self.client.get("/").headers["Content-Security-Policy"]
        segunda = self.client.get("/").headers["Content-Security-Policy"]

        self.assertIn("'nonce-", primeira)
        self.assertNotEqual(primeira, segunda)
        # 'unsafe-inline' anularia a proteção que o nonce oferece.
        self.assertNotIn("unsafe-inline", primeira)

    def test_nonce_do_cabecalho_autoriza_o_script_da_pagina(self):
        response = self.client.get("/")
        policy = response.headers["Content-Security-Policy"]
        nonce = policy.split("'nonce-")[1].split("'")[0]

        self.assertIn(f'nonce="{nonce}"'.encode(), response.data)

    def test_cookie_de_sessao_e_httponly(self):
        self.login(ADMIN_PASSWORD)
        cookie = self.client.get_cookie("session")

        assert cookie is not None, "o login não gravou o cookie de sessão"
        self.assertTrue(cookie.http_only)


class TestCsrfProtection(AppTestCase):
    """A suíte roda com CSRF desligado; aqui ele é religado de propósito."""

    def setUp(self) -> None:
        super().setUp()
        self.app.config["WTF_CSRF_ENABLED"] = True

    def _csrf_token(self) -> str:
        html = self.client.get("/login").get_data(as_text=True)
        marker = 'name="csrf_token" value="'
        return html.split(marker)[1].split('"')[0]

    def test_post_sem_token_e_recusado(self):
        response = self.client.post("/login", data={"password": ADMIN_PASSWORD})
        self.assertEqual(response.status_code, 400)
        self.assertIn("sessão desta página expirou".encode(), response.data)

    def test_post_com_token_e_aceito(self):
        response = self.client.post(
            "/login",
            data={"password": ADMIN_PASSWORD, "csrf_token": self._csrf_token()},
        )
        self.assertEqual(response.status_code, 302)

    def test_pedido_sem_token_e_recusado(self):
        response = self.submit_order(copo="1")
        self.assertEqual(response.status_code, 400)

    def test_consulta_de_salas_permanece_isenta(self):
        # É leitura sem efeito colateral: exigir token só quebraria o formulário.
        response = self.client.post("/get_rooms", json={"office": "EBM Office Goiânia"})
        self.assertEqual(response.status_code, 200)

    def test_todo_formulario_post_carrega_o_campo_de_token(self):
        self.client.post(
            "/login", data={"password": ADMIN_PASSWORD, "csrf_token": self._csrf_token()}
        )

        paginas = ["/", "/admin/offices", "/admin/spaces", "/admin/products"]
        for pagina in paginas:
            with self.subTest(pagina=pagina):
                html = self.client.get(pagina).get_data(as_text=True)
                forms_post = html.lower().count('method="post"')
                tokens = html.count('name="csrf_token"')
                self.assertGreaterEqual(tokens, forms_post, f"{pagina} tem form sem token")


class TestRateLimiting(AppTestCase):
    def setUp(self) -> None:
        super().setUp()
        limiter.enabled = True
        limiter.reset()

    def tearDown(self) -> None:
        limiter.enabled = False
        super().tearDown()

    def test_limita_rajada_de_pedidos(self):
        self.app.config["RATELIMIT_ORDER"] = "3 per minute"

        codigos = [self.submit_order(copo="1").status_code for _ in range(5)]

        self.assertEqual(codigos[:3], [200, 200, 200])
        self.assertIn(429, codigos)

    def test_limita_tentativas_de_login(self):
        self.app.config["RATELIMIT_LOGIN"] = "2 per minute"

        codigos = [
            self.client.post("/login", data={"password": "errada"}).status_code
            for _ in range(4)
        ]
        self.assertIn(429, codigos)


class TestProductionGuards(unittest.TestCase):
    """A configuração de produção recusa subir com segredos padrão."""

    def _create(self, **env: str):
        limpo = {
            "SECRET_KEY": "", "ADMIN_PASSWORD": "", "COPA_PASSWORD": "",
            "DEBUG": "", "APP_ENV": "", "FLASK_ENV": "", "DATABASE_URL": "",
            "AUTO_CREATE_DB": "", "LOG_LEVEL": "CRITICAL",
        }
        limpo.update(env)
        with mock.patch.dict(os.environ, limpo, clear=False):
            for chave, valor in list(limpo.items()):
                if valor == "":
                    os.environ.pop(chave, None)
            return create_app("production")

    def test_recusa_secret_key_padrao(self):
        with self.assertRaises(RuntimeError) as contexto:
            self._create()
        self.assertIn("SECRET_KEY", str(contexto.exception))

    def test_recusa_sem_senha_de_admin(self):
        with self.assertRaises(RuntimeError) as contexto:
            self._create(SECRET_KEY="x" * 32)
        self.assertIn("ADMIN_PASSWORD", str(contexto.exception))

    def test_recusa_sem_senha_da_copa(self):
        with self.assertRaises(RuntimeError) as contexto:
            self._create(SECRET_KEY="x" * 32, ADMIN_PASSWORD="s3nh4")
        self.assertIn("COPA_PASSWORD", str(contexto.exception))

    def test_sobe_com_tudo_definido(self):
        app = self._create(
            SECRET_KEY="x" * 32,
            ADMIN_PASSWORD="s3nh4-admin",
            COPA_PASSWORD="s3nh4-copa",
            DATABASE_URL="sqlite:///:memory:",
        )
        self.assertFalse(app.config["DEBUG"])
        self.assertTrue(app.config["SESSION_COOKIE_SECURE"])
        # Em produção o esquema é responsabilidade das migrations.
        self.assertFalse(app.config["AUTO_CREATE_DB"])


class TestConfigResolution(unittest.TestCase):
    def test_ambiente_por_variavel(self):
        from config import DevelopmentConfig, ProductionConfig, resolve_config

        with mock.patch.dict(os.environ, {"APP_ENV": "production"}):
            self.assertIs(resolve_config(), ProductionConfig)

        with mock.patch.dict(os.environ, {"APP_ENV": "development"}):
            self.assertIs(resolve_config(), DevelopmentConfig)

    def test_argumento_vence_a_variavel(self):
        from config import TestingConfig, resolve_config

        with mock.patch.dict(os.environ, {"APP_ENV": "production"}):
            self.assertIs(resolve_config("testing"), TestingConfig)

    def test_ambiente_desconhecido(self):
        from config import resolve_config

        with self.assertRaises(ValueError):
            resolve_config("homologacao")

    def test_config_lida_em_runtime_e_nao_no_import(self):
        # O valor precisa ser lido na criação da aplicação: antes, mudar
        # os.environ depois do import não tinha efeito nenhum.
        with mock.patch.dict(
            os.environ, {"APP_PORT": "8123", "LOG_LEVEL": "CRITICAL"}
        ):
            app = create_app("development")
            self.assertEqual(app.config["APP_PORT"], 8123)


if __name__ == "__main__":
    unittest.main()
