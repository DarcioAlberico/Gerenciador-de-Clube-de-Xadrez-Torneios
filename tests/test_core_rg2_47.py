"""RG2-47 — o cadastro de membro tem sexo, e a inscrição o repassa.

``members`` não tinha ``sex``: inscrever a partir do cadastro (e o Modo Livre
inscreve turmas inteiras assim) criava o jogador sem sexo, e a classificação
feminina dessas turmas saía vazia.
"""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from src.core.database import Database
from src.services.constants import AppError
from tests.support.core_service_base import CoreServiceTestCase


class SexoDoMembroTest(CoreServiceTestCase):
    def _membro(self, **extra) -> int:
        return self.member_service.create_member(
            {"name": "Ana", "member_type": "aluno", "status": "active", "birth_date": "2015-03-01", **extra}
        )

    def test_inscrita_do_cadastro_entra_na_categoria_feminino(self) -> None:
        self.db.replace_tournament_categories(
            self.tournament_id, [{"name": "Feminino", "kind": "sex", "sex": "F", "position": 0}]
        )
        membro = self._membro(sex="F")
        jogador = self.member_service.register_member_in_tournament(self.tournament_id, membro, allow_out_of_scope=True)
        self.assertEqual("F", self.db.get_player(jogador)["sex"])
        self.assertIn("Feminino", self.db.get_player(jogador)["categories"])

    def test_aceita_as_grafias_e_grava_f_ou_m(self) -> None:
        for texto, esperado in (("feminino", "F"), ("M", "M"), ("", "")):
            with self.subTest(texto=texto):
                self.assertEqual(esperado, self.db.get_member(self._membro(sex=texto))["sex"])

    def test_valor_que_nao_e_sexo_e_recusado(self) -> None:
        with self.assertRaisesRegex(AppError, "Sexo"):
            self._membro(sex="talvez")

    def test_editar_e_desativar_nao_apagam_o_sexo(self) -> None:
        membro = self._membro(sex="F")
        self.member_service.deactivate_member(membro, reason="mudou", date="2026-11-01")
        self.assertEqual("F", self.db.get_member(membro)["sex"])

    def test_importar_membros_le_a_coluna_sexo(self) -> None:
        caminho = Path(self.temp_dir.name) / "membros.csv"
        caminho.write_text("nome;sexo\nBia;F\nCaio;Masculino\n", encoding="utf-8")
        self.import_service.import_members(caminho)
        por_nome = {m["name"]: m["sex"] for m in self.db.list_members()}
        self.assertEqual("F", por_nome["Bia"])
        self.assertEqual("M", por_nome["Caio"])


class MigracaoV60Test(unittest.TestCase):
    def test_banco_antigo_migra_com_sexo_vazio(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "albericus.db"
            Database(caminho, backup_dir=Path(pasta) / "backups").create_member(name="Antigo")
            conexao = sqlite3.connect(caminho)
            try:
                colunas = [linha[1] for linha in conexao.execute("PRAGMA table_info(members)")]
                if "sex" in colunas:
                    conexao.execute("ALTER TABLE members DROP COLUMN sex")
                conexao.execute("PRAGMA user_version = 59")
                conexao.commit()
            finally:
                conexao.close()

            db = Database(caminho, backup_dir=Path(pasta) / "backups")
            (membro,) = db.list_members()
            self.assertEqual("", membro["sex"])
            self.assertGreaterEqual(Database.SCHEMA_VERSION, 60)


if __name__ == "__main__":
    unittest.main()
