"""RGS-06 — datas legadas: relatório "Datas a revisar" e normalização.

Sem `CHECK` e sem reconstruir tabela (o SQLite não faz `ADD CHECK`, e reconstruir
com `foreign_keys=ON` dispararia o `ON DELETE CASCADE`). Em vez disso:

- o que a regra única converte (`13/11/2026`, `2010/05/12`, ISO com hora) vira
  ISO, com backup antes, e só uma vez (idempotente);
- o que ela recusa fica como está e vai para o relatório;
- ano sozinho no nascimento é dado válido e não é tocado (seção 8).
"""

from __future__ import annotations

import unittest

from src.services.date_review import dates_to_review, format_report, normalize_legacy_dates
from src.ui.home import HomeSnapshot, build_pendencies
from src.ui.navigation import find
from tests.support.core_service_base import CoreServiceTestCase


class DatasLegadasTest(CoreServiceTestCase):
    def _gravar(self, sql: str, *params: object) -> None:
        with self.db.connect() as conexao:
            conexao.execute(sql, params)

    def _ler(self, sql: str, *params: object) -> object:
        with self.db.connect() as conexao:
            return conexao.execute(sql, params).fetchone()[0]

    def setUp(self) -> None:
        super().setUp()
        self.ana = self.db.create_player(self.tournament_id, name="Ana", rating=1500)
        self.bia = self.db.create_player(self.tournament_id, name="Bia", rating=1400)
        self._gravar(
            "UPDATE tournaments SET start_date = ?, end_date = ? WHERE id = ?",
            "13/11/2026",
            "2026-02-30",
            self.tournament_id,
        )
        self._gravar("UPDATE players SET birth_date = ? WHERE id = ?", "1985", self.ana)
        self._gravar("UPDATE players SET birth_date = ? WHERE id = ?", "2010/05/12", self.bia)
        self.db.save_round_schedule(
            self.tournament_id, [{"round_number": 1, "date": "2026-11-13 08:00", "time": "08:00"}]
        )
        self.db.save_tournament_settings(self.tournament_id, {"cutoff_date": "lixo"})

    def _backups(self) -> list:
        return sorted(self.backup_dir.glob("*_before_normalizar_datas*"))

    def test_relatorio_lista_so_o_que_a_regra_recusa(self) -> None:
        itens = dates_to_review(self.db)
        achados = {(item.table, item.column, item.value) for item in itens}
        self.assertEqual(
            {
                ("tournaments", "end_date", "2026-02-30"),
                ("tournament_settings", "cutoff_date", "lixo"),
            },
            achados,
        )
        texto = format_report(itens)
        self.assertIn("2026-02-30", texto)
        self.assertIn("Data de corte", texto)

    def test_normaliza_convertiveis_com_backup_antes(self) -> None:
        resultado = normalize_legacy_dates(self.db)

        self.assertEqual(3, resultado.converted)
        self.assertEqual(1, len(self._backups()))
        self.assertEqual(resultado.backup_path, self._backups()[0])
        self.assertEqual(
            "2026-11-13", self._ler("SELECT start_date FROM tournaments WHERE id = ?", self.tournament_id)
        )
        self.assertEqual("2010-05-12", self._ler("SELECT birth_date FROM players WHERE id = ?", self.bia))
        self.assertEqual(
            "2026-11-13",
            self._ler("SELECT date FROM round_schedule WHERE tournament_id = ?", self.tournament_id),
        )
        # Ano sozinho no nascimento fica como está; inválido também (vai para o relatório).
        self.assertEqual("1985", self._ler("SELECT birth_date FROM players WHERE id = ?", self.ana))
        self.assertEqual(
            "2026-02-30", self._ler("SELECT end_date FROM tournaments WHERE id = ?", self.tournament_id)
        )
        self.assertEqual(2, len(resultado.to_review))

    def test_e_idempotente(self) -> None:
        normalize_legacy_dates(self.db)
        segunda = normalize_legacy_dates(self.db)
        self.assertEqual(0, segunda.converted)
        self.assertIsNone(segunda.backup_path)
        self.assertEqual(1, len(self._backups()))

    def test_banco_em_dia_nao_faz_backup(self) -> None:
        self._gravar("UPDATE tournaments SET start_date = '', end_date = '' WHERE id = ?", self.tournament_id)
        self._gravar("UPDATE players SET birth_date = '' WHERE id = ?", self.bia)
        self._gravar("UPDATE round_schedule SET date = ''")
        self.db.save_tournament_settings(self.tournament_id, {"cutoff_date": ""})
        resultado = normalize_legacy_dates(self.db)
        self.assertEqual(0, resultado.converted)
        self.assertEqual([], self._backups())
        self.assertEqual("", format_report(resultado.to_review))


class PendenciaNaAberturaTest(unittest.TestCase):
    """O relatório aparece na tela inicial, com atalho para o cadastro."""

    def test_datas_a_revisar_viram_pendencia_com_relatorio(self) -> None:
        itens = build_pendencies(
            HomeSnapshot(
                has_tournament=True,
                generated_rounds=1,
                dates_to_review=("players", "tournaments"),
                dates_review_report="2 data(s)...",
            )
        )
        pendencia = next(item for item in itens if item.key == "datas_a_revisar")
        self.assertIn("2", pendencia.title)
        self.assertEqual("players", pendencia.destination)
        self.assertIsNotNone(find(pendencia.destination))
        self.assertEqual("2 data(s)...", pendencia.report)

    def test_sem_datas_a_revisar_sem_pendencia(self) -> None:
        itens = build_pendencies(HomeSnapshot(has_tournament=True, generated_rounds=1))
        self.assertNotIn("datas_a_revisar", [item.key for item in itens])

    def test_destino_de_cada_tabela_existe(self) -> None:
        from src.services.date_review import DATE_COLUMNS

        for coluna in DATE_COLUMNS:
            with self.subTest(tabela=coluna.table):
                itens = build_pendencies(HomeSnapshot(dates_to_review=(coluna.table,)))
                pendencia = next(item for item in itens if item.key == "datas_a_revisar")
                self.assertIsNotNone(find(pendencia.destination))
