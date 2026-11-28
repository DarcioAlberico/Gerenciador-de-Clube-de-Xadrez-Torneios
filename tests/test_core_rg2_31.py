"""RG2-31 — importar a lista oficial substitui o retrato anterior da mesma fonte.

Cada importação acumulava uma cópia inteira: o banco real chegou a 110 MB, e
cada backup carregava esse peso. As consultas só leem o retrato mais recente de
cada fonte, então o anterior não serve a ninguém.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.core.database import Database


def _lista(total: int, rating: int) -> list[dict]:
    return [
        {
            "external_id": str(100000 + indice),
            "fide_id": str(100000 + indice),
            "name": f"Jogador Oficial {indice:06d}",
            "federation": "BRA",
            "standard_rating": rating,
        }
        for indice in range(total)
    ]


class SubstituiORetratoTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        raiz = Path(self.temp.name)
        self.db = Database(raiz / "albericus.db", backup_dir=raiz / "backups")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _retratos(self) -> list[tuple[str, int]]:
        with self.db.connect() as conexao:
            return [
                (str(linha[0]), int(linha[1]))
                for linha in conexao.execute(
                    "SELECT s.source, COUNT(p.id) FROM official_rating_snapshots s "
                    "LEFT JOIN official_players p ON p.snapshot_id = s.id GROUP BY s.id ORDER BY s.id"
                )
            ]

    def test_duas_importacoes_da_mesma_fonte_deixam_um_retrato(self) -> None:
        self.db.create_official_rating_snapshot_with_players("FIDE", "2026-05", "a.xml", _lista(50, 2000))
        self.db.create_official_rating_snapshot_with_players("CBX", "", "c.xls", _lista(5, 1500))
        self.db.create_official_rating_snapshot_with_players("FIDE", "2026-06", "b.xml", _lista(40, 2100))

        self.assertEqual([("CBX", 5), ("FIDE", 40)], self._retratos())
        achado = self.db.find_latest_official_player(fide_id="100001")
        self.assertEqual(2100, int(achado["standard_rating"]))

    def test_reimportar_uma_lista_grande_nao_dobra_o_banco(self) -> None:
        lista = _lista(20000, 2000)
        self.db.create_official_rating_snapshot_with_players("FIDE", "2026-05", "a.xml", lista)
        depois_da_primeira = self.db.db_path.stat().st_size

        self.db.create_official_rating_snapshot_with_players("FIDE", "2026-06", "b.xml", lista)

        self.assertLess(self.db.db_path.stat().st_size, depois_da_primeira * 1.5)
