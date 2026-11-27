"""RGS-36 (F1.9): o cache do desempate Gacrux cobre TUDO o que entra no TRF.

A chave antiga era montada à mão (resultados + rating + critérios) e não via
``bye_points``, pontos iniciais nem ajustes: mudar um deles com o torneio em
andamento servia a classificação antiga — jogador com mais pontos abaixo de
quem tem menos. A chave agora é o hash do próprio TRF entregue ao motor.

As guardas do cache também ficam seguras para threads (RGS-10, item 4): a
reentrância é por thread, então a classificação pedida pela UI enquanto outra
thread calcula NÃO cai em silêncio no motor próprio.

Os testes rápidos trocam só o subprocesso; ``GacruxRealTest`` roda o Gacrux de
verdade (``pytest -m gacrux``).
"""
from __future__ import annotations

import json
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

import src.services.pairing_service as ps
from src.core.database import Database
from src.services.pairing.tiebreak_engine import ENGINE_GACRUX
from src.services.pairing_service import PairingService

_SUBPROCESSO = "src.services.pairing.gacrux_tiebreak_engine.subprocess.run"


def _torneio_com_bye(tmp: str) -> tuple[Database, PairingService, int, list[int]]:
    """5 jogadores, 2 rodadas fechadas (com bye), pareadas pelo motor próprio."""
    db = Database(db_path=Path(tmp) / "t.db", backup_dir=Path(tmp) / "bk")
    service = PairingService(db)
    tid = db.create_tournament("RGS-36", rounds_count=4, bye_points=1.0)
    ids = [db.create_player(tid, name=f"J{i}", rating=2000 - 50 * i) for i in range(5)]
    for numero in range(2):
        rodada = service.generate_next_round(tid)
        for pairing in db.get_pairings_for_round(int(rodada["id"])):
            if not pairing["is_bye"]:
                service.update_result(tid, int(pairing["id"]), "0-1" if numero == 0 else "1-0")
        service.close_round(tid, int(rodada["id"]))
    db.save_tournament_settings(tid, {"tiebreak_engine": ENGINE_GACRUX})
    return db, service, tid, ids


def _mudar_bye(db: Database, tid: int, pontos: float) -> None:
    with db.connect() as conexao:
        conexao.execute("UPDATE tournaments SET bye_points = ? WHERE id = ?", (pontos, tid))


def _mudar_pontos_iniciais(db: Database, player_id: int, pontos: float) -> None:
    with db.connect() as conexao:
        conexao.execute("UPDATE players SET starting_points = ? WHERE id = ?", (pontos, player_id))


class _MotorFalso:
    """Subprocesso do Gacrux trocado por um que responde vazio e conta as chamadas."""

    def __init__(self) -> None:
        self.chamadas: list[str] = []

    def __call__(self, cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess:
        self.chamadas.append(threading.current_thread().name)
        saida = cmd[cmd.index("-o") + 1]
        Path(saida).write_text(
            json.dumps({"status": {"code": 0}, "tiebreakResult": {"competitors": []}}),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")


class ChaveDoCacheTest(unittest.TestCase):
    def setUp(self) -> None:
        ps._GACRUX_TIEBREAK_CACHE.clear()
        ps._LAST_TIEBREAK_ENGINE.clear()
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db, self.service, self.tid, self.ids = _torneio_com_bye(self._tmp.name)
        self.motor = _MotorFalso()
        patcher = mock.patch(_SUBPROCESSO, side_effect=self.motor)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self) -> None:
        ps._GACRUX_TIEBREAK_CACHE.clear()
        self._tmp.cleanup()

    def test_mesmo_estado_usa_o_cache(self) -> None:
        self.service.standings(self.tid)
        self.service.standings(self.tid)
        self.assertEqual(1, len(self.motor.chamadas))

    def test_mudar_bye_points_recalcula(self) -> None:
        self.service.standings(self.tid)
        _mudar_bye(self.db, self.tid, 0.0)
        self.service.standings(self.tid)
        self.assertEqual(2, len(self.motor.chamadas))

    def test_mudar_pontos_iniciais_recalcula(self) -> None:
        self.service.standings(self.tid)
        _mudar_pontos_iniciais(self.db, self.ids[4], 2.0)
        self.service.standings(self.tid)
        # Pontos iniciais SEM rodada de ausência onde caber (o J4 jogou as
        # duas) não tem representação no TRF do desempate (162/299): desde o
        # RGS-03 no desempate o Gacrux e recusado ANTES de rodar e a
        # classificação sai do motor próprio, com registro. O que este teste
        # guarda continua valendo: o resultado antigo do cache NÃO foi servido.
        self.assertEqual(1, len(self.motor.chamadas))
        report = self.service.tiebreak_engine_report(self.tid)
        self.assertNotEqual(ENGINE_GACRUX, report.used)
        self.assertIn("pontuação", report.error)

    def test_ajuste_manual_recalcula(self) -> None:
        self.service.standings(self.tid)
        self.db.add_point_adjustment(
            self.tid, round_number=2, player_id=self.ids[4], game_points=1.0, reason="teste"
        )
        self.service.standings(self.tid)
        self.assertEqual(2, len(self.motor.chamadas))


class ReentranciaPorThreadTest(unittest.TestCase):
    """Uma thread calculando não faz a outra cair no motor próprio (RGS-10, item 4)."""

    def setUp(self) -> None:
        ps._GACRUX_TIEBREAK_CACHE.clear()
        ps._LAST_TIEBREAK_ENGINE.clear()
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db, self.service, self.tid, _ids = _torneio_com_bye(self._tmp.name)

    def tearDown(self) -> None:
        ps._GACRUX_TIEBREAK_CACHE.clear()
        self._tmp.cleanup()

    def test_classificacao_pedida_durante_outro_calculo_tambem_vai_ao_gacrux(self) -> None:
        motor = _MotorFalso()
        dentro = threading.Event()
        libera = threading.Event()

        def motor_lento(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
            if threading.current_thread().name == "calculo-lento":
                dentro.set()
                libera.wait(10)
            return motor(cmd, **kwargs)

        with mock.patch(_SUBPROCESSO, side_effect=motor_lento):
            lenta = threading.Thread(
                target=self.service.standings, args=(self.tid,), name="calculo-lento"
            )
            lenta.start()
            try:
                self.assertTrue(dentro.wait(10), "o calculo da outra thread nao comecou")
                # Mesmo torneio, outra thread, ENQUANTO a primeira calcula.
                PairingService(self.db).standings(self.tid)
            finally:
                libera.set()
                lenta.join(10)

        self.assertIn(threading.current_thread().name, motor.chamadas)


@pytest.mark.gacrux
class GacruxRealTest(unittest.TestCase):
    """Aceite do RGS-36 com o motor de verdade: a mudança vale já na chamada seguinte."""

    def setUp(self) -> None:
        ps._GACRUX_TIEBREAK_CACHE.clear()
        ps._LAST_TIEBREAK_ENGINE.clear()
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db, self.service, self.tid, self.ids = _torneio_com_bye(self._tmp.name)
        self.service.standings(self.tid)  # aquece o cache com o estado antigo

    def tearDown(self) -> None:
        ps._GACRUX_TIEBREAK_CACHE.clear()
        self._tmp.cleanup()

    def _assert_classificacao_atual(self) -> None:
        servida = self.service.standings(self.tid)
        pontos_em_ordem = [float(item["points"]) for item in servida]
        self.assertEqual(
            sorted(pontos_em_ordem, reverse=True),
            pontos_em_ordem,
            f"quem tem mais pontos ficou abaixo: {[(i['name'], i['points']) for i in servida]}",
        )
        ps._GACRUX_TIEBREAK_CACHE.clear()
        recalculada = self.service.standings(self.tid)
        self.assertEqual(
            [(i["player_id"], i["position"], i["points"]) for i in recalculada],
            [(i["player_id"], i["position"], i["points"]) for i in servida],
        )

    def test_mudar_bye_points_muda_a_classificacao_na_chamada_seguinte(self) -> None:
        _mudar_bye(self.db, self.tid, 0.0)
        self._assert_classificacao_atual()

    def test_mudar_pontos_iniciais_muda_a_classificacao_na_chamada_seguinte(self) -> None:
        _mudar_pontos_iniciais(self.db, self.ids[4], 2.0)
        self._assert_classificacao_atual()


if __name__ == "__main__":
    unittest.main()
