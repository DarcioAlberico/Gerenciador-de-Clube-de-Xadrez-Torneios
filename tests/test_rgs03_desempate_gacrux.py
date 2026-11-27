"""RGS-03 no DESEMPATE — o TRF do tiebreakchecker diz ao Gacrux o placar real.

O arquivo do PAREAMENTO já levava o registro 162 (valor do PAB) e um 299 por
ajuste do árbitro (F3.1). O do DESEMPATE não: com bye de 0 ou 0,5, ajuste de
-0,5 ou entrante tardio, o Gacrux recusava o arquivo ("Erro desconhecido") e a
classificação caía no motor próprio — com evento, mas fora do C.07.

Agora o TRF do desempate passa pela mesma reconciliação do pareamento:

- 162 com ``P = bye_points`` — o PAB vale o que a classificação conta;
- 299 por ajuste de rodada já disputada — o Gacrux o soma só à pontuação de
  PAREAMENTO (ACC); o PTS do desempate continua sendo a soma das rodadas e o
  Albericus aplica o ajuste por cima (TBK-01);
- as rodadas de ausência do entrante tardio viram ``H``/``F`` no valor dos
  pontos de entrada — ver o docstring de ``GacruxTiebreakEngine.prepare`` para
  o efeito no Buchholz (C.07 §16).

Os testes rápidos olham o TRF gerado; ``GacruxDesempateRealTest`` roda o motor
de verdade (``pytest -m gacrux``).
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pytest

import src.services.pairing_service as ps
from src.core.database import Database
from src.services.pairing.gacrux_tiebreak_engine import GacruxTiebreakEngine
from src.services.pairing.gacrux_trf import declared_points, implied_points
from src.services.pairing.tiebreak_engine import ENGINE_GACRUX
from src.services.pairing_service import PairingService
from src.services.trf_layout import cell_blocks


def _torneio(tmp: str, *, bye_points: float = 1.0, late_entry_points: float = 0.0):
    """5 jogadores, 2 rodadas fechadas pelo motor próprio (com PAB nas duas)."""
    db = Database(db_path=Path(tmp) / "t.db", backup_dir=Path(tmp) / "bk")
    service = PairingService(db)
    tid = db.create_tournament("RGS-03 desempate", rounds_count=5, bye_points=bye_points)
    if late_entry_points:
        db.save_tournament_settings(tid, {"late_entry_points": late_entry_points})
    ids = [db.create_player(tid, name=f"J{i}", rating=2000 - 50 * i) for i in range(5)]
    for numero in range(2):
        rodada = service.generate_next_round(tid)
        for pairing in db.get_pairings_for_round(int(rodada["id"])):
            if not pairing["is_bye"]:
                service.update_result(tid, int(pairing["id"]), "0-1" if numero == 0 else "1-0")
        service.close_round(tid, int(rodada["id"]))
    return db, service, tid, ids


def _com_entrante_tardio(tmp: str):
    """Entrante depois da R2 com 0,5 por rodada perdida; R3 fechada com ele."""
    db, service, tid, ids = _torneio(tmp, late_entry_points=0.5)
    tardio = int(db.create_player(tid, name="Tardio", rating=1990))
    rodada = service.generate_next_round(tid)
    for pairing in db.get_pairings_for_round(int(rodada["id"])):
        if not pairing["is_bye"]:
            service.update_result(tid, int(pairing["id"]), "1-0")
    service.close_round(tid, int(rodada["id"]))
    return db, service, tid, [*ids, tardio]


def _linhas_001(job) -> dict[int, str]:
    linhas = job.trf.decode("utf-8").splitlines()
    return {int(linha[4:8]): linha for linha in linhas if linha.startswith("001")}


def _registros(job, codigo: str) -> list[str]:
    return [linha for linha in job.trf.decode("utf-8").splitlines() if linha.startswith(codigo)]


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        ps._GACRUX_TIEBREAK_CACHE.clear()
        ps._LAST_TIEBREAK_ENGINE.clear()
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)

    def tearDown(self) -> None:
        ps._GACRUX_TIEBREAK_CACHE.clear()
        ps._LAST_TIEBREAK_ENGINE.clear()
        self._tmp.cleanup()

    def _job(self, db, tid):
        # Como o standings faz: o export aninhado usa o motor próprio.
        ps._tiebreak_inflight().add(int(tid))
        try:
            return GacruxTiebreakEngine(db).prepare(tid, ["buchholz"])
        finally:
            ps._tiebreak_inflight().discard(int(tid))


class TrfDoDesempateTest(_Base):
    def test_162_leva_o_valor_do_pab(self) -> None:
        db, _service, tid, _ids = _torneio(self._tmp.name, bye_points=0.5)
        job = self._job(db, tid)
        (sistema,) = _registros(job, "162")
        self.assertIn("P 0.5", sistema)

    def test_pontos_declarados_batem_com_as_celulas(self) -> None:
        """Com o 162 o Gacrux confere o campo de pontos e PARA se divergir."""
        for bye in (0.0, 0.5, 1.0):
            with self.subTest(bye=bye):
                db, _service, tid, _ids = _torneio(self._tmp.name, bye_points=bye)
                for linha in _linhas_001(self._job(db, tid)).values():
                    self.assertEqual(implied_points(linha, bye), declared_points(linha), linha)

    def test_ajuste_vira_299_e_sai_do_campo_de_pontos(self) -> None:
        db, _service, tid, ids = _torneio(self._tmp.name)
        db.add_point_adjustment(tid, round_number=1, player_id=ids[0], game_points=-0.5, reason="t")
        job = self._job(db, tid)
        (ajuste,) = _registros(job, "299")
        self.assertEqual("-0.5", ajuste[13:17].strip())
        for linha in _linhas_001(job).values():
            self.assertEqual(implied_points(linha), declared_points(linha), linha)

    def test_ajuste_de_rodada_fora_do_recorte_nao_entra(self) -> None:
        db, _service, tid, ids = _torneio(self._tmp.name)
        db.add_point_adjustment(tid, round_number=3, player_id=ids[0], game_points=1.0, reason="t")
        self.assertEqual([], _registros(self._job(db, tid), "299"))

    def test_ausencia_do_entrante_tardio_vira_bye_de_meio_ponto(self) -> None:
        db, _service, tid, ids = _com_entrante_tardio(self._tmp.name)
        tardio = ids[-1]
        self.assertEqual(1.0, float(db.get_player(tardio)["starting_points"]))
        job = self._job(db, tid)
        rank = next(cid for cid, pid in job.cid_to_id if pid == tardio)
        linha = _linhas_001(job)[rank]
        letras = [celula[7] for celula in cell_blocks(linha)]
        self.assertEqual(["H", "H"], letras[:2])
        self.assertEqual(implied_points(linha), declared_points(linha))

    def test_recorte_de_retrato_declara_os_pontos_daquela_rodada(self) -> None:
        """O campo de pontos do exportador é o de HOJE; o recorte tem menos rodadas."""
        db, _service, tid, _ids = _torneio(self._tmp.name, bye_points=0.5)
        ps._tiebreak_inflight().add(int(tid))
        try:
            job = GacruxTiebreakEngine(db).prepare(tid, ["buchholz"], current_round=1)
        finally:
            ps._tiebreak_inflight().discard(int(tid))
        for linha in _linhas_001(job).values():
            self.assertEqual(implied_points(linha, 0.5), declared_points(linha), linha)


@pytest.mark.gacrux
class GacruxDesempateRealTest(_Base):
    """Aceite: o desempate sai do Gacrux, sem cair no motor próprio."""

    def _assert_gacrux(self, db, service, tid) -> None:
        db.save_tournament_settings(tid, {"tiebreak_engine": ENGINE_GACRUX})
        servida = service.standings(tid)
        report = service.tiebreak_engine_report(tid)
        self.assertEqual("gacrux", report.used, report.error)
        # Os pontos são os da classificação (TBK-01) e a ordem os respeita.
        db.save_tournament_settings(tid, {"tiebreak_engine": "albericus"})
        proprio = {int(i["player_id"]): float(i["points"]) for i in service.standings(tid)}
        self.assertEqual(proprio, {int(i["player_id"]): float(i["points"]) for i in servida})
        pontos = [float(item["points"]) for item in servida]
        self.assertEqual(sorted(pontos, reverse=True), pontos)

    def test_bye_de_meio_ponto(self) -> None:
        self._assert_gacrux(*_torneio(self._tmp.name, bye_points=0.5)[:3])

    def test_bye_de_zero_ponto(self) -> None:
        self._assert_gacrux(*_torneio(self._tmp.name, bye_points=0.0)[:3])

    def test_ajuste_de_menos_meio_ponto(self) -> None:
        db, service, tid, ids = _torneio(self._tmp.name)
        db.add_point_adjustment(tid, round_number=1, player_id=ids[1], game_points=-0.5, reason="t")
        self._assert_gacrux(db, service, tid)

    def test_entrante_tardio(self) -> None:
        self._assert_gacrux(*_com_entrante_tardio(self._tmp.name)[:3])

    def test_ajuste_derruba_quem_empatava_em_pontos(self) -> None:
        """O ajuste move a ordem: quem perdeu meio ponto fica abaixo do empatado."""
        db, service, tid, ids = _torneio(self._tmp.name)
        db.save_tournament_settings(tid, {"tiebreak_engine": ENGINE_GACRUX})
        antes = {int(i["player_id"]): float(i["points"]) for i in service.standings(tid)}
        lider = max(antes, key=antes.get)
        db.add_point_adjustment(tid, round_number=2, player_id=lider, game_points=-0.5, reason="t")
        depois = service.standings(tid)
        self.assertEqual("gacrux", service.tiebreak_engine_report(tid).used)
        self.assertEqual(antes[lider] - 0.5, next(
            float(i["points"]) for i in depois if int(i["player_id"]) == lider
        ))


if __name__ == "__main__":
    unittest.main()
