"""RG2-07b — o que o motor próprio pareia hoje, fixado antes de trocar o motor.

O RG2-07b junta o suíço de jogadores e o de equipes num motor só e proíbe a
repetição. Antes de mexer, este arquivo grava o que os dois motores pareiam em
cenários com sementes fixas — rodada a rodada, até a primeira rodada que fere
um critério absoluto (repetição, segundo PAB ou três cores iguais seguidas,
que são exatamente o que o RG2-07b corrige). O que era legal continua igual.

Regravar (só quando a mudança de pareamento for intencional e explicada no
commit)::

    python -m tests.test_rg2_07b_caracterizacao --gravar
"""
from __future__ import annotations

import json
import os
import random
import sys
import unittest
from pathlib import Path
from typing import Any

os.environ.setdefault("ALBERICUS_DEFAULT_PAIRING_SYSTEM", "fide_dutch")
os.environ.setdefault("ALBERICUS_DEFAULT_TIEBREAK_ENGINE", "albericus")
os.environ.setdefault("ALBERICUS_INITIAL_COLOR", "W")

from tests.support.core_service_base import CoreServiceTestCase  # noqa: E402

ARQUIVO = Path(__file__).with_name("fixtures") / "rg2_07b_caracterizacao.json"

# (equipes, tabuleiros, rodadas, semente)
CENARIOS_EQUIPES = [(7, 2, 6, s) for s in range(10)] + [(6, 2, 5, s) for s in range(5)] + [
    (8, 2, 5, s) for s in range(5)
]
# (jogadores, rodadas, semente)
CENARIOS_JOGADORES = [(9, 5, s) for s in range(4)] + [(10, 6, s) for s in range(4)] + [
    (13, 6, s) for s in range(3)
]


class _Base(CoreServiceTestCase):
    __test__ = False  # só a infraestrutura do banco de teste; não é um teste

    def runTest(self) -> None:  # pragma: no cover - só para instanciar fora do unittest
        pass


def _ilegal(historico: dict[int, list[Any]], cores: dict[int, str], byes: dict[int, int]) -> bool:
    if any(len(set(rivais)) != len(rivais) for rivais in historico.values()):
        return True
    if any(vezes > 1 for vezes in byes.values()):
        return True
    return any("WWW" in seq or "BBB" in seq for seq in cores.values())


def rodadas_de_equipes(equipes: int, tabuleiros: int, rodadas: int, semente: int) -> list[list[list[Any]]]:
    """Confrontos de cada rodada legal, como [brancas, pretas] pelo nome."""
    sorteio = random.Random(semente)
    base = _Base()
    base.setUp()
    try:
        torneio, _ids = base._create_team_tournament(teams_count=equipes, boards_count=tabuleiros)
        with base.db.connect() as conexao:
            conexao.execute("UPDATE tournaments SET rounds_count=? WHERE id=?", (rodadas, torneio))
        nomes = {int(t["id"]): str(t["name"]) for t in base.db.list_teams(torneio, active_only=False)}
        saida: list[list[list[Any]]] = []
        historico: dict[int, list[Any]] = {}
        cores: dict[int, str] = {}
        byes: dict[int, int] = {}
        for _ in range(rodadas):
            try:
                rodada = base.service.generate_next_round(torneio)
            except Exception:  # noqa: BLE001 - a recusa encerra o cenário: é o que se fixa
                break
            confrontos = base.db.list_team_matches_for_round(int(rodada["id"]))
            linha: list[list[Any]] = []
            for m in confrontos:
                brancas, pretas = m["white_team_id"], m["black_team_id"]
                if m.get("is_bye") or not pretas:
                    byes[brancas] = byes.get(brancas, 0) + 1
                    linha.append([nomes[int(brancas)], None])
                    continue
                historico.setdefault(brancas, []).append(pretas)
                historico.setdefault(pretas, []).append(brancas)
                cores[brancas] = cores.get(brancas, "") + "W"
                cores[pretas] = cores.get(pretas, "") + "B"
                linha.append([nomes[int(brancas)], nomes[int(pretas)]])
            if _ilegal(historico, cores, byes):
                break
            saida.append(sorted(linha, key=lambda par: (par[1] is None, par[0])))
            for m in confrontos:
                if m.get("is_bye"):
                    continue
                for tabuleiro in base.db.list_team_boards(int(m["id"])):
                    base.service.update_result(
                        torneio, int(tabuleiro["id"]), sorteio.choice(["1-0", "0-1", "1/2-1/2", "1-0", "0-1"])
                    )
            base.service.close_round(torneio, int(rodada["id"]))
        return saida
    finally:
        base.tearDown()


def rodadas_de_jogadores(jogadores: int, rodadas: int, semente: int) -> list[list[list[Any]]]:
    """Mesas de cada rodada legal do motor próprio individual, pelo nome."""
    sorteio = random.Random(semente)
    base = _Base()
    base.setUp()
    try:
        torneio = base.tournament_id
        with base.db.connect() as conexao:
            conexao.execute("UPDATE tournaments SET rounds_count=? WHERE id=?", (rodadas, torneio))
        base.db.save_tournament_settings(torneio, {"pairing_system": "fide_dutch", "pairing_method": "swiss"})
        base._create_players(jogadores)
        nomes = {int(p["id"]): str(p["name"]) for p in base.db.list_players(torneio)}
        saida: list[list[list[Any]]] = []
        historico: dict[int, list[Any]] = {}
        cores: dict[int, str] = {}
        byes: dict[int, int] = {}
        for _ in range(rodadas):
            try:
                rodada = base.service.generate_next_round(torneio)
            except Exception:  # noqa: BLE001 - a recusa encerra o cenário: é o que se fixa
                break
            mesas = base.db.get_pairings_for_round(int(rodada["id"]))
            linha: list[list[Any]] = []
            for mesa in mesas:
                brancas, pretas = mesa["white_player_id"], mesa["black_player_id"]
                if mesa["is_bye"] or not pretas:
                    byes[brancas] = byes.get(brancas, 0) + 1
                    linha.append([nomes[int(brancas)], None])
                    continue
                historico.setdefault(brancas, []).append(pretas)
                historico.setdefault(pretas, []).append(brancas)
                cores[brancas] = cores.get(brancas, "") + "W"
                cores[pretas] = cores.get(pretas, "") + "B"
                linha.append([nomes[int(brancas)], nomes[int(pretas)]])
            if _ilegal(historico, cores, byes):
                break
            saida.append(sorted(linha, key=lambda par: (par[1] is None, par[0])))
            for mesa in mesas:
                if not mesa["is_bye"]:
                    base.service.update_result(
                        torneio, int(mesa["id"]), sorteio.choice(["1-0", "0-1", "1/2-1/2", "1-0", "0-1"])
                    )
            base.service.close_round(torneio, int(rodada["id"]))
        return saida
    finally:
        base.tearDown()


def _chave_equipes(cenario: tuple[int, ...]) -> str:
    return "equipes-{}x{}-r{}-s{}".format(*cenario)


def _chave_jogadores(cenario: tuple[int, ...]) -> str:
    return "jogadores-{}-r{}-s{}".format(*cenario)


def calcular() -> dict[str, Any]:
    dados: dict[str, Any] = {}
    for cenario in CENARIOS_EQUIPES:
        dados[_chave_equipes(cenario)] = rodadas_de_equipes(*cenario)
    for cenario in CENARIOS_JOGADORES:
        dados[_chave_jogadores(cenario)] = rodadas_de_jogadores(*cenario)
    return dados


class CaracterizacaoTest(unittest.TestCase):
    """Cada rodada legal fixada continua saindo igual."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.fixado = json.loads(ARQUIVO.read_text(encoding="utf-8"))

    def _conferir(self, chave: str, obtido: list[list[list[Any]]]) -> None:
        esperado = self.fixado[chave]
        # O motor novo pode ir ALÉM de onde o antigo parou (rodada que antes era
        # ilegal), mas não pode mudar o que já era legal.
        self.assertEqual(esperado, obtido[: len(esperado)], chave)

    def test_equipes(self) -> None:
        for cenario in CENARIOS_EQUIPES:
            with self.subTest(cenario=cenario):
                self._conferir(_chave_equipes(cenario), rodadas_de_equipes(*cenario))

    def test_jogadores(self) -> None:
        for cenario in CENARIOS_JOGADORES:
            with self.subTest(cenario=cenario):
                self._conferir(_chave_jogadores(cenario), rodadas_de_jogadores(*cenario))


if __name__ == "__main__" and "--gravar" in sys.argv:
    ARQUIVO.write_text(json.dumps(calcular(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("gravado", ARQUIVO)
