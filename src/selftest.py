"""Autoteste do build: ``Albericus.exe --self-test <pasta>`` (RGS-05).

A suíte de testes roda o código-fonte; o árbitro roda o `.exe`. Os defeitos do
build de 11/11 (Gacrux ausente, catálogo de textos no lugar errado) moravam
justamente nessa diferença. Este autoteste roda **dentro do executável**,
sem janela, e grava ``<pasta>/selftest.json`` (com ``console=False`` não há
stdout). O código de saída é 0 só se todos os passos passarem.

Passos:
  1. ``i18n`` — o catálogo carrega e traduz uma chave real;
  2. ``database`` — um banco temporário é criado e migrado;
  3. ``gacrux_pairing`` — torneio sintético de 8 jogadores, 3 rodadas geradas
     pelo motor **padrão** (não forçado), que tem de ser o Gacrux;
  4. ``gacrux_tiebreak`` — o desempate é calculado pelo Gacrux, sem
     ``tiebreak_engine_fallback`` no banco;
  5. ``export`` — 1 PDF de classificação e 1 TRF.

O tempo de cada chamada ao Gacrux vai no JSON: é a medida da decisão D1
(onefile × onedir) do roadmap.
"""
from __future__ import annotations

import json
import os
import platform
import sys
import tempfile
import time
import traceback
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

RESULT_FILE = "selftest.json"
PLAYERS = 8
ROUNDS = 3


@dataclass
class Step:
    name: str
    ok: bool = False
    seconds: float = 0.0
    detail: str = ""
    data: dict[str, Any] = field(default_factory=dict)


class SelfTestFailure(Exception):
    """Falha esperada de um passo, com mensagem para o árbitro."""


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise SelfTestFailure(message)


class SelfTest:
    def __init__(self, workdir: Path) -> None:
        self.workdir = workdir
        self.db = None
        self.pairing = None
        self.tournament_id: int | None = None

    # -- passos ----------------------------------------------------------
    def step_i18n(self, step: Step) -> None:
        from src.ui.i18n import catalog_path, load_catalog

        catalog = load_catalog()
        step.data["catalog"] = str(catalog_path())
        step.data["entries"] = len(catalog)
        _check(len(catalog) > 0, f"catálogo vazio ou ausente: {catalog_path()}")
        texto = catalog.get("nav.group.tournament")
        _check(texto != "nav.group.tournament", "a chave nav.group.tournament não foi traduzida")
        step.detail = f"{len(catalog)} textos"

    def step_database(self, step: Step) -> None:
        from src.core.database import Database
        from src.services.pairing_service import PairingService

        self.db = Database(db_path=str(self.workdir / "selftest.db"))
        self.db.initialize()
        self.pairing = PairingService(self.db)
        step.detail = "banco temporário migrado"

    def step_gacrux_pairing(self, step: Step) -> None:
        _check(self.db is not None, "sem banco (passo database falhou)")
        db, pairing = self.db, self.pairing
        tid = db.create_tournament("Autoteste", rounds_count=ROUNDS, bye_points=1.0)
        self.tournament_id = tid
        settings = db.get_tournament_settings(tid) or {}
        system = str(settings.get("pairing_system") or "")
        step.data["pairing_system"] = system
        _check(system == "gacrux_swiss", f"motor padrão de pareamento é {system!r}, não gacrux_swiss")
        for index in range(PLAYERS):
            db.create_player(
                tid, f"Jogador {index + 1:02d}", rating=2200 - 50 * index, sex="m",
                birth_date="2000-01-01",
            )
        timings = []
        for _ in range(ROUNDS):
            start = time.perf_counter()
            round_data = pairing.generate_next_round(tid)
            timings.append(round(time.perf_counter() - start, 3))
            boards = db.get_pairings_for_round(round_data["id"])
            _check(len(boards) == PLAYERS // 2, f"rodada {round_data.get('round_number')}: {len(boards)} mesas")
            for board in boards:
                if not board.get("is_bye"):
                    pairing.update_result(tid, board["id"], "1-0")
            pairing.close_round(tid, round_data["id"])
        step.data["seconds_per_round"] = timings
        step.detail = f"{ROUNDS} rodadas pelo Gacrux ({max(timings):.2f}s na mais lenta)"

    def step_gacrux_tiebreak(self, step: Step) -> None:
        _check(self.tournament_id is not None, "sem torneio (passo gacrux_pairing falhou)")
        tid = self.tournament_id
        start = time.perf_counter()
        rows = self.pairing.standings(tid)
        step.data["seconds"] = round(time.perf_counter() - start, 3)
        report = self.pairing.tiebreak_engine_report(tid)
        step.data["configured"] = report.configured
        step.data["used"] = report.used
        step.data["error"] = report.error
        fallbacks = self.db.list_audit_events(tid, action="tiebreak_engine_fallback", limit=10)
        step.data["fallback_events"] = len(fallbacks)
        _check(len(rows) == PLAYERS, f"classificação com {len(rows)} linhas")
        _check(report.used == "gacrux", f"desempate calculado por {report.used!r}: {report.error}")
        _check(not fallbacks, f"{len(fallbacks)} evento(s) tiebreak_engine_fallback")
        step.detail = "desempate pelo Gacrux"

    def step_export(self, step: Step) -> None:
        _check(self.tournament_id is not None, "sem torneio (passo gacrux_pairing falhou)")
        from src.services.export_service import ExportService

        export = ExportService(self.db, self.pairing)
        pdf = self.workdir / "classificacao.pdf"
        trf = self.workdir / "torneio.trf"
        export.export_standings(self.tournament_id, pdf)
        export.export_trf(self.tournament_id, trf)
        _check(pdf.exists() and pdf.read_bytes()[:4] == b"%PDF", "PDF não gerado")
        _check(trf.exists() and "001 " in trf.read_text(encoding="utf-8", errors="replace"), "TRF sem jogadores")
        step.detail = "PDF e TRF gerados"

    # -- execução --------------------------------------------------------
    def steps(self) -> list[tuple[str, Callable[[Step], None]]]:
        return [
            ("i18n", self.step_i18n),
            ("database", self.step_database),
            ("gacrux_pairing", self.step_gacrux_pairing),
            ("gacrux_tiebreak", self.step_gacrux_tiebreak),
            ("export", self.step_export),
        ]

    def run(self) -> list[Step]:
        results = []
        for name, action in self.steps():
            step = Step(name)
            start = time.perf_counter()
            try:
                action(step)
                step.ok = True
            except SelfTestFailure as exc:
                step.detail = str(exc)
            except Exception as exc:  # o autoteste relata, nunca derruba
                step.detail = f"{type(exc).__name__}: {exc}"
                step.data["traceback"] = traceback.format_exc()
            step.seconds = round(time.perf_counter() - start, 3)
            results.append(step)
        return results


def run_self_test(output_dir: Path) -> int:
    """Roda os passos e grava ``output_dir/selftest.json``. Devolve o código de saída."""
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="albericus-selftest-", ignore_cleanup_errors=True
    ) as tmp:
        workdir = Path(tmp)
        # Antes de importar o banco: backups e logs do autoteste vão para a
        # pasta temporária, nunca para os dados reais do árbitro.
        previous = os.environ.get("ALBERICUS_DATA_DIR")
        os.environ["ALBERICUS_DATA_DIR"] = str(workdir / "data")
        try:
            steps = SelfTest(workdir).run()
        finally:
            if previous is None:
                os.environ.pop("ALBERICUS_DATA_DIR", None)
            else:
                os.environ["ALBERICUS_DATA_DIR"] = previous
    from src.core.version import APP_VERSION

    report = {
        "ok": all(step.ok for step in steps),
        "version": APP_VERSION,
        "frozen": bool(getattr(sys, "frozen", False)),
        "executable": sys.executable,
        "python": platform.python_version(),
        "steps": [asdict(step) for step in steps],
    }
    (output_dir / RESULT_FILE).write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 0 if report["ok"] else 1


def main(argv: list[str]) -> int:
    output_dir = Path(argv[0]) if argv else Path.cwd()
    try:
        return run_self_test(output_dir)
    except Exception:  # última linha: até o JSON falhou
        (output_dir / "selftest-crash.txt").write_text(traceback.format_exc(), encoding="utf-8")
        return 2
