"""Testes das rotas HTTP: pedido público, painel da copa e administração."""

from __future__ import annotations

import unittest

from app.models import STATUS_COMPLETED, Office, Order, Product, Space
from tests.base import AppTestCase


class TestPublicOrderFlow(AppTestCase):
    def test_index_lista_escritorios_ativos(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("EBM Office Goiânia".encode(), response.data)

    def test_index_renderiza_todas_as_salas_para_funcionar_sem_javascript(self):
        response = self.client.get("/")
        html = response.get_data(as_text=True)

        # As salas vêm agrupadas por escritório no próprio HTML: sem isso, a
        # página dependeria de JavaScript para ser utilizável.
        self.assertIn('<optgroup label="EBM Office Goiânia"', html)
        self.assertIn("Sala Aton", html)
        self.assertIn("Sala Smart Cambuí", html)

    def test_get_rooms_aceita_get_e_post(self):
        via_post = self.client.post("/get_rooms", json={"office": "EBM Office Goiânia"})
        via_get = self.client.get("/api/rooms?office=EBM Office Goiânia")

        self.assertEqual(via_post.status_code, 200)
        self.assertEqual(via_get.status_code, 200)
        self.assertIn("Sala Aton", via_post.get_json())
        self.assertEqual(via_post.get_json(), via_get.get_json())

    def test_get_rooms_com_escritorio_invalido(self):
        response = self.client.post("/get_rooms", json={"office": "Invalid Office"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), [])

    def test_select_room(self):
        response = self.client.post(
            "/select_room", data={"office": "EBM Office Goiânia", "room": "Sala Aton"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Sala Aton", response.data)

    def test_select_room_recusa_par_invalido(self):
        response = self.client.post(
            "/select_room", data={"office": "EBM Office Goiânia", "room": "Sala Wish"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Escolha um escritório e uma sala válidos".encode(), response.data)

    def test_submit_form_cria_pedido(self):
        response = self.submit_order(cafe_expresso_sem_acucar="1", copo="2")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Pedido solicitado com sucesso", response.data)

        with self.app.app_context():
            order = Order.query.one()
            self.assertEqual(order.office.name, "EBM Office Goiânia")
            self.assertEqual(order.space.name, "Sala Aton")
            self.assertEqual(len(order.items), 2)

    def test_submit_form_exige_ao_menos_um_item(self):
        response = self.submit_order()
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Selecione pelo menos um item", response.data)

    def test_submit_form_recusa_sala_de_outro_escritorio(self):
        response = self.client.post(
            "/submit_form",
            data={"office": "EBM Office Campinas", "room": "Sala Aton", "copo": "1"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Escritório ou sala inválidos".encode(), response.data)

        with self.app.app_context():
            self.assertEqual(Order.query.count(), 0)


class TestQuantityValidation(AppTestCase):
    def test_recusa_quantidade_negativa(self):
        response = self.submit_order(copo="-1")
        self.assertEqual(response.status_code, 400)
        self.assertIn("números inteiros e positivos".encode(), response.data)

    def test_recusa_texto(self):
        response = self.submit_order(copo="dois")
        self.assertEqual(response.status_code, 400)
        self.assertIn("números inteiros e positivos".encode(), response.data)

    def test_recusa_separador_numerico_do_python(self):
        # int("1_0") vale 10: o valor gravado não podia divergir do digitado.
        response = self.submit_order(copo="1_0")
        self.assertEqual(response.status_code, 400)

        with self.app.app_context():
            self.assertEqual(Order.query.count(), 0)

    def test_recusa_acima_do_maximo(self):
        response = self.submit_order(copo="1001")
        self.assertEqual(response.status_code, 400)
        self.assertIn("não podem passar de 1000".encode(), response.data)

    def test_aceita_o_maximo(self):
        response = self.submit_order(copo="1000")
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            self.assertEqual(Order.query.one().items[0].quantity, 1000)


class TestCopaDashboard(AppTestCase):
    def test_painel_exige_autenticacao(self):
        response = self.client.get("/copa")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_api_de_pedidos_exige_autenticacao(self):
        response = self.client.get("/api/orders")
        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.get_json()["success"])

    def test_painel_usa_modal_proprio_de_conclusao(self):
        self.login_as_copa()
        response = self.client.get("/copa")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'id="complete-modal"', response.data)
        self.assertIn(b"data-modal-confirm", response.data)
        self.assertIn(b"data-modal-cancel", response.data)
        # Confirma que o diálogo nativo não voltou por engano.
        self.assertNotIn(b"window.confirm", response.data)

    def test_lista_pedidos_pendentes(self):
        self.submit_order(copo="2")
        self.login_as_copa()

        response = self.client.get("/api/orders")
        self.assertEqual(response.status_code, 200)

        orders = response.get_json()
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]["room"], "Sala Aton")
        self.assertEqual(orders[0]["items"]["Copo"], 2)

    def test_conclui_pedido(self):
        self.submit_order(limpeza_sala="Sim")
        self.login_as_copa()

        with self.app.app_context():
            order_id = Order.query.one().id

        response = self.client.post(f"/api/complete_order/{order_id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"success": True})

        with self.app.app_context():
            order = self.fetch(Order, order_id)
            self.assertEqual(order.status, STATUS_COMPLETED)
            self.assertIsNotNone(order.completed_at)

    def test_concluir_duas_vezes_preserva_o_horario_original(self):
        self.submit_order(copo="1")
        self.login_as_copa()

        with self.app.app_context():
            order_id = Order.query.one().id

        self.client.post(f"/api/complete_order/{order_id}")

        with self.app.app_context():
            primeiro_horario = self.fetch(Order, order_id).completed_at

        response = self.client.post(f"/api/complete_order/{order_id}")
        self.assertEqual(response.status_code, 409)
        self.assertIn("já foi concluído", response.get_json()["message"])

        with self.app.app_context():
            self.assertEqual(self.fetch(Order, order_id).completed_at, primeiro_horario)

    def test_concluir_pedido_inexistente(self):
        self.login_as_copa()
        response = self.client.post("/api/complete_order/999")
        self.assertEqual(response.status_code, 404)

    def test_perfil_copa_nao_acessa_administracao(self):
        self.login_as_copa()
        response = self.client.get("/admin")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])


class TestAdminCatalog(AppTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.login_as_admin()

    def test_cria_escritorio_sala_e_insumo(self):
        response = self.client.post(
            "/admin/offices", data={"name": "EBM Teste"}, follow_redirects=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"EBM Teste", response.data)

        with self.app.app_context():
            office_id = Office.query.filter_by(name="EBM Teste").one().id

        response = self.client.post(
            "/admin/spaces",
            data={"office_id": str(office_id), "name": "Sala Teste"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Sala Teste", response.data)

        response = self.client.post(
            "/admin/products",
            data={"name": "Chá", "input_type": "quantity"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            self.assertIsNotNone(Space.query.filter_by(name="Sala Teste").first())
            product = Product.query.filter_by(name="Chá").one()
            self.assertEqual(product.form_key, "cha")
            self.assertEqual(product.sort_order, Product.query.count())

    def test_recusa_escritorio_duplicado(self):
        response = self.client.post(
            "/admin/offices", data={"name": "EBM Office Goiânia"}, follow_redirects=True
        )
        self.assertIn("Já existe um escritório com esse nome".encode(), response.data)

        with self.app.app_context():
            self.assertEqual(Office.query.filter_by(name="EBM Office Goiânia").count(), 1)

    def test_recusa_escritorio_sem_nome(self):
        response = self.client.post(
            "/admin/offices", data={"name": "   "}, follow_redirects=True
        )
        self.assertIn("Informe o nome do escritório".encode(), response.data)

    def test_renomeia_escritorio(self):
        with self.app.app_context():
            office_id = Office.query.filter_by(name="EBM Office Campinas").one().id

        response = self.client.post(
            f"/admin/offices/{office_id}/update",
            data={"name": "EBM Campinas"},
            follow_redirects=True,
        )
        self.assertIn("Escritório atualizado".encode(), response.data)

        with self.app.app_context():
            self.assertEqual(self.fetch(Office, office_id).name, "EBM Campinas")

    def test_renomear_para_nome_existente_e_recusado(self):
        with self.app.app_context():
            office_id = Office.query.filter_by(name="EBM Office Campinas").one().id

        response = self.client.post(
            f"/admin/offices/{office_id}/update",
            data={"name": "EBM Office Goiânia"},
            follow_redirects=True,
        )
        self.assertIn("Já existe outro escritório com esse nome".encode(), response.data)

    def test_escritorio_inexistente(self):
        response = self.client.post(
            "/admin/offices/999/update", data={"name": "X"}, follow_redirects=True
        )
        self.assertIn("Escritório não encontrado".encode(), response.data)

    def test_inativar_escritorio_cascateia_para_as_salas(self):
        with self.app.app_context():
            office = Office.query.filter_by(name="EBM Office Goiânia").one()
            office_id = office.id
            space_ids = [space.id for space in office.spaces]

        self.client.post(f"/admin/offices/{office_id}/toggle", follow_redirects=True)

        with self.app.app_context():
            self.assertFalse(self.fetch(Office, office_id).active)
            spaces = Space.query.filter(Space.id.in_(space_ids)).all()
            self.assertTrue(all(not space.active for space in spaces))

        self.client.post(f"/admin/offices/{office_id}/toggle", follow_redirects=True)

        with self.app.app_context():
            self.assertTrue(self.fetch(Office, office_id).active)
            spaces = Space.query.filter(Space.id.in_(space_ids)).all()
            self.assertTrue(all(space.active for space in spaces))

    def test_sala_de_escritorio_inativo_nao_pode_ser_reativada(self):
        with self.app.app_context():
            office = Office.query.filter_by(name="EBM Office Campinas").one()
            office_id, space_id = office.id, office.spaces[0].id

        self.client.post(f"/admin/offices/{office_id}/toggle", follow_redirects=True)
        response = self.client.post(
            f"/admin/spaces/{space_id}/toggle", follow_redirects=True
        )

        self.assertIn("Reative o escritório antes".encode(), response.data)
        with self.app.app_context():
            self.assertFalse(self.fetch(Space, space_id).active)

    def test_sala_inativa_some_do_formulario_publico(self):
        with self.app.app_context():
            space_id = Space.query.filter_by(name="Sala Aton").one().id

        self.client.post(f"/admin/spaces/{space_id}/toggle", follow_redirects=True)

        response = self.client.post("/get_rooms", json={"office": "EBM Office Goiânia"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Sala Aton", response.get_json())

    def test_recusa_sala_duplicada_no_mesmo_escritorio(self):
        with self.app.app_context():
            office_id = Office.query.filter_by(name="EBM Office Goiânia").one().id

        response = self.client.post(
            "/admin/spaces",
            data={"office_id": str(office_id), "name": "Sala Aton"},
            follow_redirects=True,
        )
        self.assertIn("Já existe uma sala com esse nome".encode(), response.data)

    def test_recusa_sala_sem_escritorio_valido(self):
        response = self.client.post(
            "/admin/spaces",
            data={"office_id": "nao-numerico", "name": "Sala X"},
            follow_redirects=True,
        )
        self.assertIn("Informe escritório e nome da sala".encode(), response.data)

    def test_recusa_tipo_de_insumo_invalido(self):
        response = self.client.post(
            "/admin/products",
            data={"name": "Suco", "input_type": "texto-livre"},
            follow_redirects=True,
        )
        self.assertIn("Tipo de insumo inválido".encode(), response.data)

        with self.app.app_context():
            self.assertIsNone(Product.query.filter_by(name="Suco").first())

    def test_insumo_inativo_some_do_formulario_de_pedido(self):
        with self.app.app_context():
            product_id = Product.query.filter_by(form_key="copo").one().id

        self.client.post(f"/admin/products/{product_id}/toggle", follow_redirects=True)

        response = self.client.post(
            "/select_room", data={"office": "EBM Office Goiânia", "room": "Sala Aton"}
        )
        self.assertNotIn(b'name="copo"', response.data)


class TestProductReorder(AppTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.login_as_admin()

    def _product_ids(self) -> list[int]:
        with self.app.app_context():
            return [
                product.id
                for product in Product.query.order_by(Product.sort_order.asc()).all()
            ]

    def test_reordena(self):
        reordered = list(reversed(self._product_ids()))

        response = self.client.post(
            "/admin/products/reorder", json={"product_ids": reordered}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"success": True})
        self.assertEqual(self._product_ids(), reordered)

    def test_recusa_lista_vazia(self):
        response = self.client.post("/admin/products/reorder", json={"product_ids": []})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Envie a nova ordem", response.get_json()["message"])

    def test_recusa_lista_ausente(self):
        response = self.client.post("/admin/products/reorder", json={})
        self.assertEqual(response.status_code, 400)

    def test_recusa_identificadores_nao_numericos(self):
        response = self.client.post(
            "/admin/products/reorder", json={"product_ids": ["a", "b"]}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("inválida", response.get_json()["message"])

    def test_recusa_duplicidades(self):
        first = self._product_ids()[0]
        response = self.client.post(
            "/admin/products/reorder", json={"product_ids": [first, first]}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("duplicidades", response.get_json()["message"])

    def test_recusa_insumo_inexistente(self):
        response = self.client.post(
            "/admin/products/reorder", json={"product_ids": [99999]}
        )
        self.assertEqual(response.status_code, 404)

    def test_exige_autenticacao(self):
        self.logout()
        response = self.client.post(
            "/admin/products/reorder", json={"product_ids": [1, 2]}
        )
        self.assertEqual(response.status_code, 401)


class TestAdminFiltersAndHistory(AppTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.login_as_admin()

    def test_tela_de_salas_expoe_dados_de_filtro(self):
        response = self.client.get("/admin/spaces")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"data-space-filters", response.data)
        self.assertIn(b"data-space-office-filter", response.data)
        self.assertIn(b"data-space-name-filter", response.data)
        self.assertIn(b"data-space-row", response.data)

    def test_historico_vazio(self):
        response = self.client.get("/admin/history")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Nenhum pedido concluído".encode(), response.data)

    def test_historico_lista_pedido_concluido(self):
        self.submit_order(copo="3")

        with self.app.app_context():
            order_id = Order.query.one().id

        self.login_as_admin()
        self.client.post(f"/api/complete_order/{order_id}")

        response = self.client.get("/admin/history")
        self.assertEqual(response.status_code, 200)
        self.assertIn(f"#{order_id}".encode(), response.data)
        self.assertIn(b"Sala Aton", response.data)
        # Um pedido concluído, três copos.
        self.assertIn(b">1<", response.data)
        self.assertIn(b">3<", response.data)

    def test_historico_recusa_data_invalida(self):
        response = self.client.get("/admin/history?start=10-08-2026")
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"AAAA-MM-DD", response.data)

    def test_historico_recusa_intervalo_invertido(self):
        response = self.client.get("/admin/history?start=2026-08-10&end=2026-08-01")
        self.assertEqual(response.status_code, 400)
        self.assertIn("não pode ser posterior".encode(), response.data)

    def test_historico_filtra_por_escritorio(self):
        self.submit_order(copo="1")

        with self.app.app_context():
            order_id = Order.query.one().id
            outro_id = Office.query.filter_by(name="EBM Office Campinas").one().id

        self.login_as_admin()
        self.client.post(f"/api/complete_order/{order_id}")

        response = self.client.get(f"/admin/history?office_id={outro_id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Nenhum pedido concluído".encode(), response.data)

    def test_painel_conta_pedidos(self):
        self.submit_order(copo="1")
        self.login_as_admin()

        response = self.client.get("/admin")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Pedidos pendentes", response.data)
        self.assertIn("Pedidos concluídos".encode(), response.data)


class TestHealthCheck(AppTestCase):
    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "ok")


if __name__ == "__main__":
    unittest.main()
