"""RGS-08 (base, F1.5): ``Database.transaction()`` reentrante, por thread.

Dentro da transação, todo ``db.*`` da MESMA thread grava na mesma conexão e
nada chega ao arquivo antes da saída da transação mais externa; uma exceção que
atravessa a transação desfaz tudo. Fora dela, o comportamento antigo vale
(cada método abre, grava e fecha). Outra thread nunca enxerga nem reutiliza a
conexão desta: lê o último estado gravado e, para gravar, ESPERA
(``busy_timeout``) em vez de falhar com "database is locked".
"""
from __future__ import annotations

import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path

from src.core.database import Database


class _Falha(RuntimeError):
    pass


class TransacaoTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        base = Path(self._tmp.name)
        self.db = Database(db_path=base / "t.db", backup_dir=base / "bk")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _nomes_gravados(self) -> set[str]:
        """Lê por uma conexão independente: só o que já foi gravado no arquivo."""
        conexao = sqlite3.connect(self.db.db_path)
        try:
            return {str(row[0]) for row in conexao.execute("SELECT name FROM tournaments")}
        finally:
            conexao.close()

    # -- Atomicidade ------------------------------------------------------- #

    def test_excecao_na_transacao_aninhada_nao_grava_nada(self) -> None:
        with self.assertRaises(_Falha):
            with self.db.transaction():
                self.db.create_tournament("Externo")
                with self.db.transaction():
                    self.db.create_tournament("Interno")
                    raise _Falha("falha injetada")

        self.assertEqual(set(), self._nomes_gravados())

    def test_nada_chega_ao_arquivo_antes_da_saida_mais_externa(self) -> None:
        with self.db.transaction():
            self.db.create_tournament("A")
            with self.db.transaction():
                self.db.create_tournament("B")
            # A transação interna terminou, mas a externa ainda não.
            self.assertEqual(set(), self._nomes_gravados())
            # A própria thread enxerga o que gravou.
            self.assertEqual({"A", "B"}, {t["name"] for t in self.db.list_tournaments()})

        self.assertEqual({"A", "B"}, self._nomes_gravados())

    def test_metodo_que_falha_dentro_da_transacao_desfaz_so_a_propria_parte(self) -> None:
        """Cada ``db.*`` continua atômico por si, como antes, mesmo dentro da transação."""
        with self.db.transaction():
            self.db.create_tournament("Fica")
            try:
                with self.db.connect() as conexao:
                    conexao.execute(
                        "INSERT INTO tournaments (name, created_at) VALUES ('Some', '2026-01-01')"
                    )
                    raise _Falha("falha no meio do metodo")
            except _Falha:
                pass

        self.assertEqual({"Fica"}, self._nomes_gravados())

    # -- Fora da transação: o comportamento de sempre ---------------------- #

    def test_sem_transacao_cada_metodo_grava_na_hora(self) -> None:
        self.db.create_tournament("Na hora")
        self.assertEqual({"Na hora"}, self._nomes_gravados())

    def test_sem_transacao_excecao_desfaz_so_aquele_bloco(self) -> None:
        self.db.create_tournament("Antes")
        with self.assertRaises(_Falha):
            with self.db.connect() as conexao:
                conexao.execute(
                    "INSERT INTO tournaments (name, created_at) VALUES ('Desfeito', '2026-01-01')"
                )
                raise _Falha("falha injetada")
        self.assertEqual({"Antes"}, self._nomes_gravados())

    def test_banco_em_wal(self) -> None:
        conexao = sqlite3.connect(self.db.db_path)
        try:
            modo = conexao.execute("PRAGMA journal_mode").fetchone()[0]
        finally:
            conexao.close()
        self.assertEqual("wal", str(modo).lower())

    def test_conexao_espera_ate_5s_pelo_bloqueio(self) -> None:
        with self.db.connect() as conexao:
            self.assertEqual(5000, conexao.execute("PRAGMA busy_timeout").fetchone()[0])

    # -- Outra thread ------------------------------------------------------ #

    def test_outra_thread_nao_reutiliza_a_conexao_nem_ve_o_que_nao_foi_gravado(self) -> None:
        aberta = threading.Event()
        pode_sair = threading.Event()
        visto_pela_outra: dict[str, object] = {}

        def outra_thread() -> None:
            aberta.wait(5)
            visto_pela_outra["nomes"] = {t["name"] for t in self.db.list_tournaments()}
            pode_sair.set()

        leitora = threading.Thread(target=outra_thread)
        leitora.start()
        with self.db.transaction():
            self.db.create_tournament("Pendente")
            aberta.set()
            # A leitora NÃO pode ficar bloqueada pela escrita em aberto (WAL).
            self.assertTrue(pode_sair.wait(3), "leitura de outra thread bloqueou")
        leitora.join(5)

        self.assertEqual(set(), visto_pela_outra["nomes"])
        self.assertEqual({"Pendente"}, self._nomes_gravados())

    def test_escrita_de_outra_thread_espera_em_vez_de_falhar(self) -> None:
        aberta = threading.Event()
        erro: list[BaseException] = []
        gravou_em: list[float] = []

        def escritora() -> None:
            aberta.wait(5)
            try:
                self.db.create_tournament("Da outra thread")
                gravou_em.append(time.monotonic())
            except BaseException as exc:  # noqa: BLE001 - o teste relata qualquer falha
                erro.append(exc)

        thread = threading.Thread(target=escritora)
        thread.start()
        with self.db.transaction():
            self.db.create_tournament("Desta thread")
            aberta.set()
            time.sleep(0.8)
            saiu_em = time.monotonic()
        thread.join(10)

        self.assertEqual([], erro)
        self.assertEqual(1, len(gravou_em))
        self.assertGreaterEqual(gravou_em[0], saiu_em, "a outra thread gravou dentro da transacao")
        self.assertEqual({"Desta thread", "Da outra thread"}, self._nomes_gravados())


if __name__ == "__main__":
    unittest.main()
