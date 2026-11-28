"""RG2-01 + RG2-44 — a retenção de backups só apaga backups do Albericus.

RG2-01: a poda tratava como backup qualquer ``.db`` da pasta, num balde só, em
ordem de texto com resolução de segundo. Com a pasta de backups apontada para
a pasta do banco, o fechamento apagava o banco vivo; sem esse engano, o único
retrato antes de uma migração sumia no primeiro dia de torneio.

RG2-44: o backup do fechamento passava pela permissão ``settings_write``, que
o árbitro não tem — quem fechava o programa como árbitro saía sem backup.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from src.core.database import Database
from src.services.security_service import SecurityService


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.raiz = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _banco(self, backups: Path | None = None) -> Database:
        return Database(self.raiz / "albericus.db", backup_dir=backups or self.raiz / "backups")

    @staticmethod
    def _envelhecer(caminho: Path, segundos: int) -> None:
        """mtime ``segundos`` no passado, para a ordem não depender do relógio."""
        agora = caminho.stat().st_mtime_ns
        alvo = agora - segundos * 1_000_000_000
        os.utime(caminho, ns=(alvo, alvo))


class RetencaoSoDoAlbericusTest(_Base):
    def test_pasta_do_banco_como_pasta_de_backups_nao_apaga_o_banco_vivo(self) -> None:
        db = self._banco(backups=self.raiz)
        estranho = self.raiz / "planilha_antiga.db"
        estranho.write_bytes(b"x")
        for indice in range(3):
            self._envelhecer(db.backup("manual"), 10 - indice)
        self._envelhecer(db.db_path, 1000)  # o banco vivo é o mais antigo da pasta
        self._envelhecer(estranho, 2000)

        db.prune_backups(1)

        self.assertTrue(db.db_path.exists(), "a retenção apagou o banco vivo")
        self.assertTrue(estranho.exists(), "a retenção apagou um arquivo que não é dela")
        self.assertEqual(1, len(db.list_backups()))

    def test_retrato_de_migracao_fica_fora_da_cota_comum(self) -> None:
        db = self._banco()
        migracao = db.backup("before_schema_migration")
        self._envelhecer(migracao, 1000)
        for indice in range(12):
            self._envelhecer(db.backup("before_close_round_t1_r1"), 100 - indice)

        db.prune_backups(10)

        self.assertTrue(migracao.exists(), "o único retrato pré-migração foi apagado")
        nomes = [item["name"] for item in db.list_backups()]
        self.assertEqual(11, len(nomes))

    def test_retratos_de_seguranca_tem_cota_propria_de_tres(self) -> None:
        db = self._banco()
        seguranca = []
        for indice, motivo in enumerate(
            ["before_schema_migration", "before_restore", "before_normalizar_datas", "before_restore"]
        ):
            caminho = db.backup(motivo)
            self._envelhecer(caminho, 100 - indice)
            seguranca.append(caminho)

        db.prune_backups(1)

        self.assertFalse(seguranca[0].exists(), "o mais antigo dos 4 sai")
        self.assertTrue(all(caminho.exists() for caminho in seguranca[1:]))

    def test_tres_backups_no_mesmo_instante_o_ultimo_criado_sobrevive(self) -> None:
        db = self._banco()
        criados = [db.backup("manual") for _ in range(3)]
        instante = criados[0].stat().st_mtime_ns
        for caminho in criados:
            os.utime(caminho, ns=(instante, instante))

        db.prune_backups(1)

        self.assertEqual([criados[-1].name], [item["name"] for item in db.list_backups()])

    def test_salvar_a_pasta_do_banco_como_pasta_de_backups_e_recusado(self) -> None:
        db = self._banco()
        with self.assertRaises(ValueError):
            db.save_app_settings({"backup_dir": str(self.raiz)})
        self.assertNotEqual(self.raiz.resolve(), db.backup_dir.resolve())


class BackupDeFechamentoSemPermissaoTest(_Base):
    def test_arbitro_fecha_o_programa_e_fica_o_backup(self) -> None:
        db = self._banco()
        seguranca = SecurityService(db)
        seguranca.create_user("arb", "senha-do-arbitro", "arbiter")
        self.assertTrue(seguranca.login("arb", "senha-do-arbitro"))

        caminho = seguranca.shutdown_backup()

        self.assertIn("auto_shutdown", caminho.name)
        self.assertTrue(caminho.exists())

    def test_backup_manual_continua_exigindo_permissao(self) -> None:
        db = self._banco()
        seguranca = SecurityService(db)
        seguranca.create_user("arb", "senha-do-arbitro", "arbiter")
        seguranca.login("arb", "senha-do-arbitro")

        with self.assertRaises(Exception):
            seguranca.create_backup("manual")

    def test_o_fechamento_do_app_usa_o_backup_do_sistema(self) -> None:
        fonte = (Path(__file__).resolve().parents[1] / "src" / "ui" / "app.py").read_text(encoding="utf-8")
        self.assertIn("security_service.shutdown_backup()", fonte)
        self.assertNotIn('create_backup("auto_shutdown")', fonte)
