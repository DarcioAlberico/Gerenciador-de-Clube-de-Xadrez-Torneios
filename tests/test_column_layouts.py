"""Testes da largura de colunas por usuário (B-1 / P2-9).

Duas camadas, nenhuma abrindo janela: as regras puras
(`src/services/column_layouts.py`) e o serviço sobre banco de verdade
(`ColumnLayoutService`). O que só a janela prova — arrastar o separador e a
largura voltar na visita seguinte — está em `test_ui_layout`.
"""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from src.core.database import Database
from src.services.column_layout_service import ColumnLayoutService
from src.services.column_layouts import (
    MAX_COLUMN_WIDTH,
    MIN_COLUMN_WIDTH,
    clamp_width,
    deviations,
    effective_widths,
    layout_key,
    normalize_widths,
    serialize_widths,
)

COLUNAS = ["id", "nome", "clube"]
TITULOS = {"id": "ID", "nome": "Nome", "clube": "Clube"}
PADROES = {"id": 60, "nome": 220, "clube": 140}


class ChaveDaTabelaTest(unittest.TestCase):
    def test_mesmas_colunas_e_titulos_dao_a_mesma_chave(self) -> None:
        self.assertEqual(layout_key(COLUNAS, TITULOS), layout_key(list(COLUNAS), dict(TITULOS)))

    def test_titulo_diferente_e_outra_tabela(self) -> None:
        """Duas telas com as mesmas colunas mas títulos distintos não se misturam."""
        outros = {**TITULOS, "nome": "Jogador"}
        self.assertNotEqual(layout_key(COLUNAS, TITULOS), layout_key(COLUNAS, outros))

    def test_ordem_das_colunas_conta(self) -> None:
        self.assertNotEqual(
            layout_key(COLUNAS, TITULOS), layout_key(list(reversed(COLUNAS)), TITULOS)
        )

    def test_chave_sobrevive_ao_reinicio(self) -> None:
        """Determinística de verdade: ``hash()`` do Python não serviria.

        O valor está cravado porque a chave é o endereço da preferência no
        banco — se ela mudar entre versões, a largura salva vira lixo silencioso.
        """
        self.assertEqual("9fb0160076fa2531", layout_key(COLUNAS, TITULOS))

    def test_concatenacao_ambigua_nao_confunde_duas_tabelas(self) -> None:
        """("ab" → "c") e ("a" → "bc") são tabelas distintas, e a chave sabe."""
        self.assertNotEqual(layout_key(["ab"], {"ab": "c"}), layout_key(["a"], {"a": "bc"}))

    def test_sem_titulos_ainda_produz_chave(self) -> None:
        self.assertEqual(16, len(layout_key(COLUNAS)))


class LarguraTest(unittest.TestCase):
    def test_piso_impede_a_coluna_de_sumir(self) -> None:
        self.assertEqual(MIN_COLUMN_WIDTH, clamp_width(3))

    def test_teto_barra_valor_absurdo(self) -> None:
        self.assertEqual(MAX_COLUMN_WIDTH, clamp_width(99_999))

    def test_zero_e_negativo_significam_sem_preferencia(self) -> None:
        self.assertEqual(0, clamp_width(0))
        self.assertEqual(0, clamp_width(-40))

    def test_lixo_nao_estoura(self) -> None:
        for valor in ("abc", None, [1], {}):
            with self.subTest(valor=valor):
                self.assertEqual(0, clamp_width(valor))


class NormalizacaoTest(unittest.TestCase):
    def test_le_json_do_banco(self) -> None:
        self.assertEqual({"nome": 300}, normalize_widths('{"nome": 300}'))

    def test_banco_corrompido_vira_ausencia_de_preferencia(self) -> None:
        for cru in ("{nao é json", "", "   ", "[1,2]", None, 7):
            with self.subTest(cru=cru):
                self.assertEqual({}, normalize_widths(cru))

    def test_valor_invalido_e_descartado_sem_derrubar_o_resto(self) -> None:
        self.assertEqual({"nome": 300}, normalize_widths('{"nome": 300, "clube": "largo"}'))

    def test_aplica_piso_e_teto_no_que_veio_do_banco(self) -> None:
        lido = normalize_widths('{"id": 2, "nome": 5000}')
        self.assertEqual({"id": MIN_COLUMN_WIDTH, "nome": MAX_COLUMN_WIDTH}, lido)


class DesvioTest(unittest.TestCase):
    def test_guarda_so_o_que_saiu_do_padrao(self) -> None:
        atual = {"id": 60, "nome": 320, "clube": 140}
        self.assertEqual({"nome": 320}, deviations(PADROES, atual))

    def test_nada_mexido_nao_guarda_nada(self) -> None:
        self.assertEqual({}, deviations(PADROES, dict(PADROES)))

    def test_padrao_novo_alcanca_quem_nunca_arrastou(self) -> None:
        """A razão de guardar desvio e não largura absoluta.

        O usuário arrastou só 'nome'. Se amanhã o padrão de 'clube' mudar de
        140 para 200, ele tem de receber 200 — e não ficar preso ao 140 que
        estava na tela no dia em que mexeu em outra coluna.
        """
        guardado = deviations(PADROES, {"id": 60, "nome": 320, "clube": 140})
        novos_padroes = {**PADROES, "clube": 200}
        final = effective_widths(COLUNAS, novos_padroes, guardado)
        self.assertEqual({"id": 60, "nome": 320, "clube": 200}, final)


class LarguraEfetivaTest(unittest.TestCase):
    def test_sem_nada_salvo_usa_o_padrao(self) -> None:
        self.assertEqual(PADROES, effective_widths(COLUNAS, PADROES, {}))

    def test_coluna_sem_padrao_cai_no_fallback(self) -> None:
        self.assertEqual({"novo": 100}, effective_widths(["novo"], {}, {}))

    def test_salvo_vence_o_padrao(self) -> None:
        final = effective_widths(COLUNAS, PADROES, {"nome": 400})
        self.assertEqual(400, final["nome"])
        self.assertEqual(60, final["id"])

    def test_coluna_que_saiu_da_tabela_e_ignorada(self) -> None:
        """Layout salvo com coluna que a tela não tem mais não vaza para a saída."""
        final = effective_widths(COLUNAS, PADROES, {"coluna_extinta": 500})
        self.assertEqual(set(COLUNAS), set(final))


class SerializacaoTest(unittest.TestCase):
    def test_ordena_para_o_json_ser_estavel(self) -> None:
        self.assertEqual('{"a": 100, "z": 200}', serialize_widths({"z": 200, "a": 100}))

    def test_largura_zerada_nao_e_gravada(self) -> None:
        self.assertEqual('{"a": 100}', serialize_widths({"a": 100, "b": 0}))


class ColumnLayoutServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        base = Path(self.temp.name)
        self.db = Database(base / "albericus.db", backup_dir=base / "backups")
        self.service = ColumnLayoutService(self.db)
        self.chave = ColumnLayoutService.key_for(COLUNAS, TITULOS)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_sem_preferencia_devolve_os_padroes(self) -> None:
        self.assertEqual(
            PADROES, self.service.widths_for(1, self.chave, COLUNAS, PADROES)
        )

    def test_guarda_e_devolve_na_proxima_leitura(self) -> None:
        self.service.remember(1, self.chave, PADROES, {**PADROES, "nome": 350})
        self.assertEqual(
            350, self.service.widths_for(1, self.chave, COLUNAS, PADROES)["nome"]
        )

    def test_cada_usuario_tem_a_sua_largura(self) -> None:
        self.service.remember(1, self.chave, PADROES, {**PADROES, "nome": 350})
        self.assertEqual(
            PADROES["nome"], self.service.widths_for(2, self.chave, COLUNAS, PADROES)["nome"]
        )

    def test_voltar_ao_padrao_apaga_a_linha_em_vez_de_gravar_vazio(self) -> None:
        self.service.remember(1, self.chave, PADROES, {**PADROES, "nome": 350})
        self.service.remember(1, self.chave, PADROES, dict(PADROES))
        self.assertEqual("", self.db.get_column_layout(1, self.chave))

    def test_reset_limpa_todas_as_tabelas_do_usuario(self) -> None:
        outra = ColumnLayoutService.key_for(["x"], {"x": "X"})
        self.service.remember(1, self.chave, PADROES, {**PADROES, "nome": 350})
        self.service.remember(1, outra, {"x": 50}, {"x": 120})
        self.service.remember(2, self.chave, PADROES, {**PADROES, "nome": 400})

        self.assertEqual(2, self.service.reset(1))
        self.assertEqual(PADROES, self.service.widths_for(1, self.chave, COLUNAS, PADROES))
        self.assertEqual(400, self.service.widths_for(2, self.chave, COLUNAS, PADROES)["nome"])

    def test_banco_quebrado_nao_derruba_a_tela(self) -> None:
        """Ler a preferência é conveniência; falhar nela não pode fechar a lista."""
        def explode(*_args: object, **_kwargs: object) -> str:
            raise RuntimeError("banco fora do ar")

        self.db.get_column_layout = explode  # type: ignore[method-assign]
        self.assertEqual(PADROES, self.service.widths_for(1, self.chave, COLUNAS, PADROES))

    def test_falha_ao_gravar_tambem_e_engolida(self) -> None:
        def explode(*_args: object, **_kwargs: object) -> None:
            raise RuntimeError("disco cheio")

        self.db.save_column_layout = explode  # type: ignore[method-assign]
        self.service.remember(1, self.chave, PADROES, {**PADROES, "nome": 350})


class MigracaoV44Test(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_banco_novo_ja_nasce_com_a_tabela(self) -> None:
        db = Database(self.base / "albericus.db", backup_dir=self.base / "backups")
        with db.connect() as conn:
            achou = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='ui_column_layouts'"
            ).fetchone()
            versao = conn.execute("PRAGMA user_version").fetchone()[0]
        self.assertIsNotNone(achou)
        self.assertEqual(Database.SCHEMA_VERSION, versao)

    def test_banco_v43_existente_e_atualizado_sem_perder_dado(self) -> None:
        """O caminho que importa: quem já usa o app, não quem instala hoje."""
        legado = self.base / "legado_v43.db"
        conn = sqlite3.connect(legado)
        try:
            conn.executescript(
                """
                CREATE TABLE app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                INSERT INTO app_settings (key, value, updated_at)
                VALUES ('operator_name', 'Arbitro Antigo', '2026-07-01 00:00:00');
                PRAGMA user_version = 43;
                """
            )
            conn.commit()
        finally:
            conn.close()

        db = Database(legado, backup_dir=self.base / "backups")
        with db.connect() as migrado:
            versao = migrado.execute("PRAGMA user_version").fetchone()[0]
            preservado = migrado.execute(
                "SELECT value FROM app_settings WHERE key = 'operator_name'"
            ).fetchone()
        self.assertEqual(Database.SCHEMA_VERSION, versao)
        self.assertEqual("Arbitro Antigo", preservado["value"])

        # E a tabela nova ja aceita escrita.
        db.save_column_layout(1, "abc", '{"nome": 200}')
        self.assertEqual('{"nome": 200}', db.get_column_layout(1, "abc"))

    def test_migracao_e_idempotente(self) -> None:
        """Reabrir um banco já na versão corrente não pode explodir.

        Vale porque ``_ensure_current_schema`` reexecuta todas as migrações
        quando o banco já está na versão atual — um ``CREATE TABLE`` sem
        ``IF NOT EXISTS`` só apareceria aqui.
        """
        caminho = self.base / "reaberto.db"
        db = Database(caminho, backup_dir=self.base / "backups")
        db.save_column_layout(7, "tabela", '{"nome": 150}')
        de_novo = Database(caminho, backup_dir=self.base / "backups")
        self.assertEqual('{"nome": 150}', de_novo.get_column_layout(7, "tabela"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
