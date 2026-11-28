"""RG2-19 + RG2-45 — o portal serve só o publicado, no modo publicado, e o QR aponta para a rede.

D4 (decidida pelo dono em 2026-11-28): o portal responde na rede local quando
o torneio é publicado — é para os pais na Wi-Fi —, só no modo público e só o
torneio publicado; o modo ``privado`` responde só nesta máquina.

Antes: ``/portal/{id}`` e ``/api/tournaments/{id}/public`` serviam qualquer id
(um pai trocava o número na URL e lia a lista de outra turma, com menores), o
modo vinha do ``?mode=`` do cliente, e o QR impresso apontava para
``localhost`` — no celular, nada abria.
"""
from __future__ import annotations

import unittest
from unittest import mock

from fastapi.testclient import TestClient

from src.services import result_server
from src.services.result_server import LocalResultServer, build_app
from tests.support.core_service_base import CoreServiceTestCase

REDE = ("192.168.0.10", 50000)
ESTA_MAQUINA = ("127.0.0.1", 50000)


class PortalPublicadoTest(CoreServiceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.db.save_tournament_settings(self.tournament_id, {"contact_email": "org@clube.test"})
        self.outro = self.db.create_tournament("Turma B", rounds_count=3)
        self.servidor = LocalResultServer(self.qr_result_service)

    def _cliente(self, origem: tuple[str, int]) -> TestClient:
        return TestClient(build_app(self.servidor), client=origem)

    def _publicar(self, modo: str = "publico") -> None:
        with mock.patch.object(LocalResultServer, "start", return_value="http://x:8765"):
            self.servidor.publish_tournament(self.tournament_id, self.export_service, mode=modo)

    def test_aceite_da_espec(self) -> None:
        self._publicar("publico")
        cliente = self._cliente(REDE)
        resposta = cliente.get(f"/api/tournaments/{self.tournament_id}/public?mode=privado")
        self.assertEqual(200, resposta.status_code)
        self.assertNotIn("org@clube.test", resposta.text)
        self.assertEqual(404, cliente.get(f"/api/tournaments/{self.outro}/public").status_code)
        self.assertEqual(404, cliente.get(f"/portal/{self.outro}").status_code)

    def test_nada_publicado_e_404(self) -> None:
        cliente = self._cliente(REDE)
        self.assertEqual(404, cliente.get(f"/api/tournaments/{self.tournament_id}/public").status_code)
        self.assertEqual(404, cliente.get(f"/portal/{self.tournament_id}").status_code)

    def test_nesta_maquina_o_modo_da_url_vale(self) -> None:
        self._publicar("publico")
        resposta = self._cliente(ESTA_MAQUINA).get(f"/api/tournaments/{self.tournament_id}/public?mode=privado")
        self.assertIn("org@clube.test", resposta.text)

    def test_publicado_em_privado_nao_responde_para_a_rede(self) -> None:
        self._publicar("privado")
        self.assertEqual(403, self._cliente(REDE).get(f"/portal/{self.tournament_id}").status_code)
        self.assertEqual(200, self._cliente(ESTA_MAQUINA).get(f"/portal/{self.tournament_id}").status_code)

    def test_cabecalhos_de_privacidade(self) -> None:
        self._publicar("publico")
        resposta = self._cliente(REDE).get(f"/portal/{self.tournament_id}")
        self.assertEqual("no-store", resposta.headers["cache-control"])
        self.assertEqual("DENY", resposta.headers["x-frame-options"])

    def test_formulario_do_qr_continua_respondendo_na_rede(self) -> None:
        resposta = self._cliente(REDE).get("/resultado?token=abc")
        self.assertEqual(200, resposta.status_code)


class EnderecoDoQrTest(unittest.TestCase):
    def test_com_bind_em_todas_as_interfaces_a_url_usa_o_ip_da_rede(self) -> None:
        servidor = LocalResultServer(mock.Mock(), host="0.0.0.0", port=8765)
        with mock.patch.object(result_server, "lan_addresses", return_value=["192.168.0.7"]):
            self.assertEqual("http://192.168.0.7:8765", servidor.url)

    def test_o_ip_escolhido_vale_quando_ha_mais_de_um(self) -> None:
        servidor = LocalResultServer(mock.Mock(), host="0.0.0.0", port=8765)
        with mock.patch.object(result_server, "lan_addresses", return_value=["192.168.0.7", "10.0.0.5"]):
            servidor.advertised_host = "10.0.0.5"
            self.assertEqual("http://10.0.0.5:8765", servidor.url)

    def test_sem_rede_nao_usa_o_nome_localhost(self) -> None:
        servidor = LocalResultServer(mock.Mock(), host="0.0.0.0", port=8765)
        with mock.patch.object(result_server, "lan_addresses", return_value=[]):
            self.assertNotIn("localhost", servidor.url)

    def test_lan_addresses_nao_traz_loopback_nem_link_local(self) -> None:
        for endereco in result_server.lan_addresses():
            with self.subTest(endereco=endereco):
                self.assertFalse(endereco.startswith(("127.", "169.254.")))


class QrImpressoTest(CoreServiceTestCase):
    def test_o_qr_da_sumula_usa_o_endereco_da_rede(self) -> None:
        servidor = LocalResultServer(self.qr_result_service, host="0.0.0.0", port=8765)
        with mock.patch.object(result_server, "lan_addresses", return_value=["192.168.0.7"]):
            self.db.save_app_settings({"local_result_server_url": servidor.url})
        self._create_players(2)
        rodada = self.service.generate_next_round(self.tournament_id)
        mesa = self.db.get_pairings_for_round(int(rodada["id"]))[0]
        payload = self.qr_result_service.result_url_for_pairing(
            self.tournament_id, int(mesa["id"]), base_url=self.db.get_app_settings()["local_result_server_url"]
        )
        self.assertTrue(payload["url"].startswith("http://192.168.0.7:8765/resultado"))


if __name__ == "__main__":
    unittest.main()
