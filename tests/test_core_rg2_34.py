"""RG2-34 — desativar ou editar membro não apaga dados.

``update_member`` do banco regravava TODAS as colunas: o que o chamador não
mandava voltava ao padrão. Desativar apagava usuário do Lichess/Chess.com e
ratings online; editar o telefone apagava o motivo de saída. Agora o UPDATE é
parcial — só as colunas presentes.
"""
from __future__ import annotations

import unittest

from tests.support.core_service_base import CoreServiceTestCase


class MembroNaoPerdeDadosTest(CoreServiceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.membro = self.member_service.create_member(
            {
                "name": "João", "member_type": "aluno", "status": "active", "phone": "1111",
                "lichess_username": "joaolx", "chesscom_username": "joaocc",
                "online_blitz_rating": "1700", "online_rapid_rating": "1650",
            }
        )

    def _campos(self) -> dict:
        membro = self.db.get_member(self.membro)
        return {k: membro[k] for k in (
            "lichess_username", "chesscom_username", "online_blitz_rating", "online_rapid_rating",
            "status", "departure_reason", "departure_date", "phone",
        )}

    def test_desativar_preserva_os_dados_online(self) -> None:
        self.member_service.deactivate_member(self.membro, reason="mudou de cidade", date="2026-11-01")
        campos = self._campos()
        self.assertEqual(("joaolx", "joaocc", 1700, 1650), (
            campos["lichess_username"], campos["chesscom_username"],
            campos["online_blitz_rating"], campos["online_rapid_rating"],
        ))
        self.assertEqual("inactive", campos["status"])
        self.assertEqual("mudou de cidade", campos["departure_reason"])

    def test_editar_o_telefone_depois_preserva_o_motivo_de_saida(self) -> None:
        self.member_service.deactivate_member(self.membro, reason="mudou de cidade", date="2026-11-01")
        membro = self.db.get_member(self.membro)
        formulario = {chave: membro[chave] for chave in (
            "name", "member_type", "status", "lichess_username", "chesscom_username",
            "online_blitz_rating", "online_rapid_rating",
        )}
        self.member_service.update_member(self.membro, {**formulario, "phone": "2222"})
        campos = self._campos()
        self.assertEqual("2222", campos["phone"])
        self.assertEqual("mudou de cidade", campos["departure_reason"])
        self.assertEqual("2026-11-01", campos["departure_date"])
        self.assertEqual("joaolx", campos["lichess_username"])

    def test_update_parcial_no_banco_so_toca_o_que_veio(self) -> None:
        self.db.update_member(self.membro, phone="3333")
        campos = self._campos()
        self.assertEqual("3333", campos["phone"])
        self.assertEqual("joaolx", campos["lichess_username"])
        self.assertEqual(1700, campos["online_blitz_rating"])

    def test_coluna_desconhecida_levanta(self) -> None:
        with self.assertRaisesRegex(ValueError, "xyz"):
            self.db.update_member(self.membro, xyz="1")


if __name__ == "__main__":
    unittest.main()
