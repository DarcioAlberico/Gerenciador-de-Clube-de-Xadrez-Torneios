"""RG2-24 — Scheveningen e eliminatória são desempatados como sistema pré-determinado.

``swiss = pairing_method != "round_robin"`` mandava ``-s`` (regras de suíço)
para todo sistema que não fosse o rodízio. No Gacrux a flag muda o adversário
virtual e o confronto direto: Scheveningen e mata-mata saíam com as regras de
suíço. Agora só o suíço é suíço.
"""
from __future__ import annotations

from src.services.pairing.gacrux_tiebreak_engine import GacruxTiebreakEngine
from tests.support.core_service_base import CoreServiceTestCase


class FlagDoSistemaTest(CoreServiceTestCase):
    def _args(self, metodo: str) -> tuple[str, ...]:
        self.db.save_tournament_settings(self.tournament_id, {"pairing_method": metodo})
        job = GacruxTiebreakEngine(self.db).prepare(self.tournament_id, ["buchholz"], current_round=1)
        assert job is not None
        return job.args

    def test_scheveningen_usa_as_regras_pre_determinadas(self) -> None:
        self._create_players(4)
        args = self._args("scheveningen")
        self.assertIn("-p", args)
        self.assertNotIn("-s", args)

    def test_eliminatoria_usa_as_regras_pre_determinadas(self) -> None:
        self._create_players(4)
        self.assertIn("-p", self._args("knockout"))

    def test_suico_continua_suico(self) -> None:
        self._create_players(4)
        self.assertIn("-s", self._args("swiss"))

    def test_sem_metodo_gravado_e_suico(self) -> None:
        self._create_players(4)
        self.assertIn("-s", self._args(""))
