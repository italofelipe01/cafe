"""Testes da camada de serviço, sem passar por HTTP."""

from __future__ import annotations

import unittest
from datetime import date

from app import services
from app.extensions import db
from app.models import Office, Product
from app.services import NotFoundError, ServiceError
from tests.base import AppTestCase


class TestParseQuantity(AppTestCase):
    def test_valores_validos(self):
        with self.app.app_context():
            self.assertEqual(services.parse_quantity("0"), 0)
            self.assertEqual(services.parse_quantity("7"), 7)
            self.assertEqual(services.parse_quantity(" 7 "), 7)
            self.assertEqual(services.parse_quantity(1000), 1000)

    def test_vazio_vale_zero(self):
        with self.app.app_context():
            self.assertEqual(services.parse_quantity(None), 0)
            self.assertEqual(services.parse_quantity(""), 0)
            self.assertEqual(services.parse_quantity("   "), 0)

    def test_recusa_negativo(self):
        with self.app.app_context(), self.assertRaises(ServiceError):
            services.parse_quantity("-1")

    def test_recusa_decimal(self):
        with self.app.app_context(), self.assertRaises(ServiceError):
            services.parse_quantity("1.5")

    def test_recusa_texto(self):
        with self.app.app_context(), self.assertRaises(ServiceError):
            services.parse_quantity("dez")

    def test_recusa_separador_numerico_do_python(self):
        # int("1_000") == 1000: aceitar isso gravaria valor diferente do digitado.
        with self.app.app_context():
            for entrada in ["1_0", "1_000", "+5"]:
                with self.subTest(entrada=entrada), self.assertRaises(ServiceError):
                    services.parse_quantity(entrada)

    def test_recusa_acima_do_maximo(self):
        with self.app.app_context():
            with self.assertRaises(ServiceError) as contexto:
                services.parse_quantity("1001")
            self.assertIn("1000", contexto.exception.message)


class TestSlugAndKeys(AppTestCase):
    def test_slugify_remove_acentos_e_simbolos(self):
        with self.app.app_context():
            self.assertEqual(services.slugify("Café expresso"), "cafe_expresso")
            self.assertEqual(services.slugify("Jarra de água"), "jarra_de_agua")
            self.assertEqual(services.slugify("Chá!!!"), "cha")
            self.assertEqual(services.slugify("   "), "item")
            self.assertEqual(services.slugify("!@#$"), "item")

    def test_chave_de_formulario_resolve_colisao(self):
        with self.app.app_context():
            # "copo" já existe no catálogo semente.
            self.assertEqual(services.unique_product_key("Copo"), "copo_2")
            self.assertEqual(services.unique_product_key("Água"), "agua")

    def test_chave_ignora_o_proprio_registro(self):
        with self.app.app_context():
            product = Product.query.filter_by(form_key="copo").one()
            self.assertEqual(services.unique_product_key("Copo", product.id), "copo")


class TestOrderServices(AppTestCase):
    def test_cria_pedido(self):
        with self.app.app_context():
            space = services.require_space("Sede Centro", "Sala Bourbon")
            produto = Product.query.filter_by(form_key="copo").one()
            order = services.create_order(space, [(produto, 4)])

            self.assertEqual(order.status, "pending")
            self.assertEqual(order.items[0].quantity, 4)
            self.assertIsNone(order.completed_at)

    def test_require_space_recusa_par_invalido(self):
        with self.app.app_context(), self.assertRaises(ServiceError):
            services.require_space("Filial Sul", "Sala Bourbon")

    def test_conclui_e_recusa_repeticao(self):
        with self.app.app_context():
            space = services.require_space("Sede Centro", "Sala Bourbon")
            produto = Product.query.filter_by(form_key="copo").one()
            order = services.create_order(space, [(produto, 1)])

            concluido = services.complete_order(order.id)
            self.assertEqual(concluido.status, "completed")
            self.assertIsNotNone(concluido.completed_at)

            with self.assertRaises(ServiceError) as contexto:
                services.complete_order(order.id)
            self.assertEqual(contexto.exception.status_code, 409)

    def test_conclui_pedido_inexistente(self):
        with self.app.app_context(), self.assertRaises(NotFoundError):
            services.complete_order(4321)

    def test_parse_date(self):
        with self.app.app_context():
            self.assertEqual(services.parse_date("2026-08-10"), date(2026, 8, 10))
            self.assertIsNone(services.parse_date(""))
            self.assertIsNone(services.parse_date(None))

            with self.assertRaises(ServiceError):
                services.parse_date("10/08/2026")

    def test_historico_recusa_intervalo_invertido(self):
        with self.app.app_context(), self.assertRaises(ServiceError):
            services.completed_orders_page(
                start=date(2026, 8, 10), end=date(2026, 8, 1)
            )


class TestCatalogServices(AppTestCase):
    def test_toggle_de_escritorio_leva_as_salas_junto(self):
        with self.app.app_context():
            office = Office.query.filter_by(name="Filial Sul").one()

            desativado = services.toggle_office(office.id)
            self.assertFalse(desativado.active)
            self.assertTrue(all(not space.active for space in desativado.spaces))

            reativado = services.toggle_office(office.id)
            self.assertTrue(reativado.active)
            self.assertTrue(all(space.active for space in reativado.spaces))

    def test_sala_criada_em_escritorio_inativo_nasce_inativa(self):
        with self.app.app_context():
            office = Office.query.filter_by(name="Filial Sul").one()
            services.toggle_office(office.id)

            space = services.create_space(str(office.id), "Sala Nova")
            self.assertFalse(space.active)

    def test_novo_insumo_vai_para_o_fim_da_ordem(self):
        with self.app.app_context():
            total = Product.query.count()
            produto = services.create_product("Chá", "quantity")
            self.assertEqual(produto.sort_order, total + 1)

    def test_reordena_e_valida(self):
        with self.app.app_context():
            ids = [p.id for p in Product.query.order_by(Product.sort_order).all()]
            services.reorder_products(list(reversed(ids)))

            db.session.expire_all()
            nova_ordem = [p.id for p in Product.query.order_by(Product.sort_order).all()]
            self.assertEqual(nova_ordem, list(reversed(ids)))

            with self.assertRaises(ServiceError):
                services.reorder_products([])
            with self.assertRaises(ServiceError):
                services.reorder_products("nao-e-lista")
            with self.assertRaises(NotFoundError):
                services.reorder_products([99999])

    def test_active_offices_ignora_escritorio_sem_sala_ativa(self):
        with self.app.app_context():
            office = Office.query.filter_by(name="Filial Sul").one()
            for space in office.spaces:
                space.active = False
            db.session.commit()

            nomes = [o.name for o in services.active_offices()]
            self.assertNotIn("Filial Sul", nomes)

    def test_dashboard_stats(self):
        with self.app.app_context():
            stats = services.dashboard_stats()
            self.assertEqual(stats["offices"], 3)
            self.assertEqual(stats["pending_orders"], 0)
            self.assertEqual(stats["completed_orders"], 0)


if __name__ == "__main__":
    unittest.main()
