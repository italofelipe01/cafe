"""Testes das rotas HTTP: pedido público, painel da copa e administração."""

from __future__ import annotations

import csv
import io
import re
import unittest
from datetime import timedelta

from app.extensions import db
from app.models import STATUS_COMPLETED, Office, Order, Product, Space
from tests.base import AppTestCase


class TestPublicOrderFlow(AppTestCase):
    def test_index_lista_escritorios_ativos(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Sede Centro", response.data)

    def test_index_renderiza_todas_as_salas_para_funcionar_sem_javascript(self):
        response = self.client.get("/")
        html = response.get_data(as_text=True)

        # As salas vêm agrupadas por escritório no próprio HTML: sem isso, a
        # página dependeria de JavaScript para ser utilizável.
        self.assertIn('<optgroup label="Sede Centro"', html)
        self.assertIn("Sala Bourbon", html)
        self.assertIn("Sala Arábica", html)

    def test_get_rooms_aceita_get_e_post(self):
        via_post = self.client.post("/get_rooms", json={"office": "Sede Centro"})
        via_get = self.client.get("/api/rooms?office=Sede Centro")

        self.assertEqual(via_post.status_code, 200)
        self.assertEqual(via_get.status_code, 200)
        self.assertIn("Sala Bourbon", via_post.get_json())
        self.assertEqual(via_post.get_json(), via_get.get_json())

    def test_get_rooms_com_escritorio_invalido(self):
        response = self.client.post("/get_rooms", json={"office": "Invalid Office"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), [])

    def test_select_room_redireciona_para_o_endereco_da_sala(self):
        response = self.client.post(
            "/select_room", data={"office": "Sede Centro", "room": "Sala Bourbon"}
        )
        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            space_id = Space.query.filter_by(name="Sala Bourbon").one().id
        self.assertTrue(response.headers["Location"].endswith(f"/pedido/sala/{space_id}"))

        page = self.client.get(response.headers["Location"])
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"Sala Bourbon", page.data)
        self.assertIn(b'name="request_token"', page.data)

    def test_select_room_recusa_par_invalido(self):
        response = self.client.post(
            "/select_room", data={"office": "Sede Centro", "room": "Sala Geisha"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Escolha um escritório e uma sala válidos".encode(), response.data)

    def test_submit_form_cria_pedido(self):
        response = self.submit_order(cafe_expresso_sem_acucar="1", copo="2")

        with self.app.app_context():
            order = Order.query.one()
            self.assertEqual(order.office.name, "Sede Centro")
            self.assertEqual(order.space.name, "Sala Bourbon")
            self.assertEqual(len(order.items), 2)
            order_id = order.id

        # Post/Redirect/Get: a confirmação é uma página própria.
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith(f"/pedido/{order_id}"))

        confirmation = self.client.get(response.headers["Location"])
        self.assertEqual(confirmation.status_code, 200)
        self.assertIn(b"Pedido solicitado com sucesso", confirmation.data)

    def test_recarregar_a_confirmacao_nao_cria_outro_pedido(self):
        response = self.submit_order(copo="1")

        for _ in range(3):
            self.assertEqual(self.client.get(response.headers["Location"]).status_code, 200)

        with self.app.app_context():
            self.assertEqual(Order.query.count(), 1)

    def test_confirmacao_e_so_de_quem_pediu(self):
        response = self.submit_order(copo="1")

        # Outro navegador, sem o pedido na sessão, não vê o pedido pelo número.
        other = self.app.test_client()
        self.assertEqual(other.get(response.headers["Location"]).status_code, 404)

    def test_reenvio_do_mesmo_formulario_nao_duplica(self):
        token = "t" * 32
        primeira = self.submit_order(copo="2", request_token=token)
        segunda = self.submit_order(copo="2", request_token=token)

        self.assertEqual(primeira.headers["Location"], segunda.headers["Location"])
        with self.app.app_context():
            self.assertEqual(Order.query.count(), 1)

        page = self.client.get(segunda.headers["Location"])
        self.assertIn("já tinha sido enviado".encode(), page.data)

    def test_formularios_diferentes_criam_pedidos_diferentes(self):
        self.submit_order(copo="1", request_token="a" * 32)
        self.submit_order(copo="1", request_token="b" * 32)

        with self.app.app_context():
            self.assertEqual(Order.query.count(), 2)

    def test_token_malformado_nao_impede_o_pedido(self):
        response = self.submit_order(copo="1", request_token="<script>")
        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            self.assertIsNone(Order.query.one().request_token)

    def test_observacao_chega_a_copa(self):
        self.submit_order(copo="1", note="  Adoçante   à parte  ")
        self.login_as_copa()

        orders = self.client.get("/api/orders").get_json()
        self.assertEqual(orders[0]["note"], "Adoçante à parte")
        self.assertIn("waiting_seconds", orders[0])

    def test_observacao_longa_e_recusada_sem_perder_o_que_foi_digitado(self):
        response = self.submit_order(copo="7", note="x" * 281)

        self.assertEqual(response.status_code, 400)
        self.assertIn("até 280 caracteres".encode(), response.data)
        self.assertIn(b'value="7"', response.data)

        with self.app.app_context():
            self.assertEqual(Order.query.count(), 0)

    def test_erro_de_validacao_preserva_as_quantidades(self):
        response = self.submit_order(copo="3", jarra_agua="abc")

        self.assertEqual(response.status_code, 400)
        self.assertIn(b'value="3"', response.data)

    def test_submit_form_exige_ao_menos_um_item(self):
        response = self.submit_order()
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Selecione pelo menos um item", response.data)

    def test_link_direto_da_sala(self):
        with self.app.app_context():
            space_id = Space.query.filter_by(name="Sala Bourbon").one().id

        response = self.client.get(f"/pedido/sala/{space_id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Sala Bourbon", response.data)
        self.assertIn(b'name="copo"', response.data)

    def test_link_de_sala_inativa_ou_inexistente(self):
        with self.app.app_context():
            space = Space.query.filter_by(name="Sala Bourbon").one()
            space.active = False
            db.session.commit()
            space_id = space.id

        for path in [f"/pedido/sala/{space_id}", "/pedido/sala/9999"]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 404)
                self.assertIn("não está disponível".encode(), response.data)

    def test_submit_form_recusa_sala_de_outro_escritorio(self):
        response = self.client.post(
            "/submit_form",
            data={"office": "Filial Sul", "room": "Sala Bourbon", "copo": "1"},
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
        self.assertEqual(response.status_code, 302)

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
        # Endereços da API resolvidos pelo servidor, não fixos no script.
        self.assertIn(b'data-orders-url="/api/orders"', response.data)
        self.assertIn(b'data-complete-url="/api/complete_order"', response.data)
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
        self.assertEqual(orders[0]["room"], "Sala Bourbon")
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
            "/admin/offices", data={"name": "Unidade Teste"}, follow_redirects=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Unidade Teste", response.data)

        with self.app.app_context():
            office_id = Office.query.filter_by(name="Unidade Teste").one().id

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
            "/admin/offices", data={"name": "Sede Centro"}, follow_redirects=True
        )
        self.assertIn("Já existe um escritório com esse nome".encode(), response.data)

        with self.app.app_context():
            self.assertEqual(Office.query.filter_by(name="Sede Centro").count(), 1)

    def test_recusa_escritorio_sem_nome(self):
        response = self.client.post(
            "/admin/offices", data={"name": "   "}, follow_redirects=True
        )
        self.assertIn("Informe o nome do escritório".encode(), response.data)

    def test_renomeia_escritorio(self):
        with self.app.app_context():
            office_id = Office.query.filter_by(name="Filial Sul").one().id

        response = self.client.post(
            f"/admin/offices/{office_id}/update",
            data={"name": "Unidade Sul"},
            follow_redirects=True,
        )
        self.assertIn("Escritório atualizado".encode(), response.data)

        with self.app.app_context():
            self.assertEqual(self.fetch(Office, office_id).name, "Unidade Sul")

    def test_renomear_para_nome_existente_e_recusado(self):
        with self.app.app_context():
            office_id = Office.query.filter_by(name="Filial Sul").one().id

        response = self.client.post(
            f"/admin/offices/{office_id}/update",
            data={"name": "Sede Centro"},
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
            office = Office.query.filter_by(name="Sede Centro").one()
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
            office = Office.query.filter_by(name="Filial Sul").one()
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
            space_id = Space.query.filter_by(name="Sala Bourbon").one().id

        self.client.post(f"/admin/spaces/{space_id}/toggle", follow_redirects=True)

        response = self.client.post("/get_rooms", json={"office": "Sede Centro"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Sala Bourbon", response.get_json())

    def test_recusa_sala_duplicada_no_mesmo_escritorio(self):
        with self.app.app_context():
            office_id = Office.query.filter_by(name="Sede Centro").one().id

        response = self.client.post(
            "/admin/spaces",
            data={"office_id": str(office_id), "name": "Sala Bourbon"},
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
            "/select_room",
            data={"office": "Sede Centro", "room": "Sala Bourbon"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'name="jarra_agua"', response.data)
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
        self.assertIn(b"Sala Bourbon", response.data)

    def test_historico_soma_os_totais_do_periodo(self):
        self.submit_order(copo="3", cafe_expresso_sem_acucar="2", limpeza_sala="Sim")

        with self.app.app_context():
            order_id = Order.query.one().id

        self.login_as_admin()
        self.client.post(f"/api/complete_order/{order_id}")

        html = self.client.get("/admin/history").get_data(as_text=True)

        # O total precisa aparecer como número. Quando o resumo era um dict, o
        # Jinja resolvia `summary.items` para o método dict.items e a tela
        # mostrava "<built-in method items of dict object at 0x...>".
        self.assertNotIn("built-in method", html)
        self.assertNotIn("dict object at", html)

        totais = re.findall(r"<strong>(\d+)</strong>\s*<span>([^<]+)</span>", html)
        resumo = {rotulo.strip(): int(valor) for valor, rotulo in totais}

        self.assertEqual(resumo["Pedidos concluídos"], 1)
        # 3 copos + 2 cafés + 1 pela limpeza da sala.
        self.assertEqual(resumo["Itens atendidos"], 6)

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
            outro_id = Office.query.filter_by(name="Filial Sul").one().id

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


class TestHistoryExportAndMetrics(AppTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.submit_order(copo="3", limpeza_sala="Sim", note="Para a diretoria")

        with self.app.app_context():
            order = Order.query.one()
            # Pedido feito 12 minutos antes da conclusão.
            order.created_at = order.created_at - timedelta(minutes=12)
            db.session.commit()
            self.order_id = order.id

        self.login_as_admin()
        self.client.post(f"/api/complete_order/{self.order_id}")

    def test_exporta_csv_para_o_excel(self):
        response = self.client.get("/admin/history.csv")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/csv")
        self.assertIn("attachment;", response.headers["Content-Disposition"])

        text = response.get_data(as_text=True)
        # BOM e ponto e vírgula: o Excel em português abre com acentos e colunas.
        self.assertTrue(text.startswith("\ufeff"))
        linhas = list(csv.reader(io.StringIO(text.lstrip("\ufeff")), delimiter=";"))

        self.assertEqual(linhas[0][0], "Pedido")
        self.assertEqual(linhas[1][0], str(self.order_id))
        self.assertEqual(linhas[1][2], "Sala Bourbon")
        self.assertEqual(linhas[1][5], "12")
        self.assertIn("Copo: 3", linhas[1][6])
        self.assertIn("Limpeza da sala: Sim", linhas[1][6])
        self.assertEqual(linhas[1][7], "Para a diretoria")

    def test_exportacao_neutraliza_formulas(self):
        # A observação vem do formulário público: não pode virar fórmula no Excel.
        self.submit_order(copo="1", note='=HYPERLINK("http://exemplo.invalido","x")')
        with self.app.app_context():
            novo_id = max(order.id for order in Order.query.all())
        self.client.post(f"/api/complete_order/{novo_id}")

        text = self.client.get("/admin/history.csv").get_data(as_text=True)
        linhas = list(csv.reader(io.StringIO(text.lstrip("\ufeff")), delimiter=";"))
        observacoes = [linha[7] for linha in linhas[1:]]

        self.assertIn("'=HYPERLINK(\"http://exemplo.invalido\",\"x\")", observacoes)
        self.assertFalse(any(obs.startswith("=") for obs in observacoes))

    def test_exportacao_respeita_os_filtros(self):
        with self.app.app_context():
            outro_id = Office.query.filter_by(name="Filial Sul").one().id

        text = self.client.get(f"/admin/history.csv?office_id={outro_id}").get_data(
            as_text=True
        )
        self.assertEqual(len(text.strip().splitlines()), 1)  # só o cabeçalho

    def test_exportacao_com_data_invalida_volta_ao_historico(self):
        response = self.client.get("/admin/history.csv?start=ontem")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/admin/history"))

    def test_historico_mostra_o_tempo_medio_e_a_observacao(self):
        html = self.client.get("/admin/history").get_data(as_text=True)

        self.assertIn("12 min", html)
        self.assertIn("Tempo médio de atendimento", html)
        self.assertIn("Para a diretoria", html)
        self.assertIn("/admin/history.csv", html)


class TestRoomQrCodes(AppTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.login_as_admin()

    def test_gera_um_qr_por_sala_ativa(self):
        with self.app.app_context():
            ativas = Space.query.filter_by(active=True).count()
            space_id = Space.query.filter_by(name="Sala Bourbon").one().id

        html = self.client.get("/admin/spaces/qrcodes").get_data(as_text=True)

        self.assertEqual(html.count('class="qr-code"'), ativas)
        self.assertIn(f"/pedido/sala/{space_id}", html)

    def test_avisa_quando_o_endereco_so_abre_nesta_maquina(self):
        html = self.client.get("/admin/spaces/qrcodes").get_data(as_text=True)
        self.assertIn("só abre nesta máquina", html)

    def test_usa_o_endereco_publico_configurado(self):
        self.app.config["PUBLIC_BASE_URL"] = "http://192.168.0.10:5000"

        html = self.client.get("/admin/spaces/qrcodes").get_data(as_text=True)

        self.assertIn("http://192.168.0.10:5000/pedido/sala/", html)
        self.assertNotIn("só abre nesta máquina", html)

    def test_tela_de_salas_tem_link_direto(self):
        html = self.client.get("/admin/spaces").get_data(as_text=True)
        self.assertIn("/pedido/sala/", html)
        self.assertIn("/admin/spaces/qrcodes", html)


class TestHealthCheck(AppTestCase):
    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "ok")
        self.assertEqual(response.get_json()["version"], self.app.config["APP_VERSION"])


if __name__ == "__main__":
    unittest.main()
