"""RGS-01 / RGS-02 (Revisão Geral Suíço, Fase 0): o build congelado.

O `.exe` do PyInstaller (onefile) extrai os recursos em ``sys._MEIPASS`` e tem
``sys.executable`` apontando para o próprio ``Albericus.exe``. Dois defeitos
nasceram de tratar essas duas pastas como a mesma:

* RGS-02: o catálogo de textos era procurado ao lado do `.exe` (só existe no
  ``_MEIPASS``) e a tela mostrava chaves em vez de rótulos;
* RGS-01: o Gacrux era chamado como ``[sys.executable, script.py]``, o que no
  `.exe` abre **outro Albericus** com um argumento que ele ignora.

Estes testes simulam o congelado com ``sys.frozen``/``sys._MEIPASS`` e provam
o despacho ``--gacrux`` rodando ``app.py`` de verdade num subprocesso — que é
exatamente o que o `.exe` faz consigo mesmo.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pytest

from src.core import resources
from src.services.pairing import gacrux_runner

pytestmark = pytest.mark.gacrux  # RGS-37: roda o motor padrão de verdade
ROOT = Path(__file__).resolve().parents[1]


def _frozen(meipass: Path, executable: Path):
    """Simula o PyInstaller: congela, aponta o _MEIPASS e o executável."""
    return mock.patch.multiple(
        sys, create=True, frozen=True, _MEIPASS=str(meipass), executable=str(executable)
    )


class BundledResourceTests(unittest.TestCase):
    def test_dev_resolves_from_project_root(self) -> None:
        self.assertEqual(resources.bundled_resource("i18n"), ROOT / "i18n")

    def test_frozen_resolves_from_meipass_not_from_executable(self) -> None:
        with tempfile.TemporaryDirectory() as meipass, tempfile.TemporaryDirectory() as exe_dir:
            with _frozen(Path(meipass), Path(exe_dir) / "Albericus.exe"):
                self.assertEqual(resources.bundled_resource("i18n"), Path(meipass) / "i18n")


class FrozenCatalogTests(unittest.TestCase):
    """Processo limpo: o congelado e simulado ANTES de importar o i18n.

    O defeito antigo calculava a pasta na importação; simular depois dela
    esconderia o bug (o teste passaria com o código quebrado).
    """

    SCRIPT = (
        "import sys, json\n"
        "sys.frozen = True\n"
        "sys._MEIPASS = sys.argv[1]\n"
        "sys.executable = sys.argv[2]\n"
        "from src.ui import i18n\n"
        "c = i18n.load_catalog()\n"
        "print(json.dumps([len(c), c.get('nav.group.tournament')]))\n"
    )

    def test_catalog_loads_from_meipass_when_frozen(self) -> None:
        # O .exe fica numa pasta SEM i18n/ (como dist/); o catálogo só existe no
        # _MEIPASS. Antes do RGS-02 isto carregava um catálogo vazio.
        with tempfile.TemporaryDirectory() as exe_dir:
            result = subprocess.run(
                [sys.executable, "-c", self.SCRIPT, str(ROOT), str(Path(exe_dir) / "Albericus.exe")],
                capture_output=True, text=True, cwd=str(ROOT), timeout=60,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        entries, label = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertGreater(entries, 100)
        self.assertNotEqual(label, "nav.group.tournament")


class GacruxCommandTests(unittest.TestCase):
    def test_dev_runs_the_script_with_the_interpreter(self) -> None:
        cmd = gacrux_runner.gacrux_command("pairing", ["-i", "x.trf"])
        self.assertEqual(cmd[0], sys.executable)
        self.assertEqual(Path(cmd[1]).name, "pairingchecker.py")
        self.assertTrue(Path(cmd[1]).exists())
        self.assertEqual(cmd[2:], ["-i", "x.trf"])

    def test_frozen_calls_the_executable_itself_in_gacrux_mode(self) -> None:
        with tempfile.TemporaryDirectory() as meipass:
            exe = Path(meipass) / "Albericus.exe"
            with _frozen(Path(meipass), exe):
                cmd = gacrux_runner.gacrux_command("tiebreak", ["-n", "3"])
        self.assertEqual(cmd, [str(exe), "--gacrux", "tiebreak", "-n", "3"])

    def test_frozen_scripts_live_in_meipass(self) -> None:
        with tempfile.TemporaryDirectory() as meipass:
            with _frozen(Path(meipass), Path(meipass) / "Albericus.exe"):
                self.assertEqual(gacrux_runner.gacrux_dir(), Path(meipass) / "gacrux")

    def test_unknown_kind_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            gacrux_runner.gacrux_command("berger", [])


class GacruxDispatchTests(unittest.TestCase):
    """``app.py --gacrux`` roda o script e devolve o código dele, sem abrir a UI."""

    @staticmethod
    def _write_trf(path: Path) -> None:
        """TRF de 4 jogadores escrito pelo MESMO exportador que o motor usa."""
        from src.core.database import Database
        from src.services.export_service import ExportService
        from src.services.federation_exporters.trf16 import TRF16Exporter
        from src.services.pairing_service import PairingService

        db = Database(db_path=str(path.with_suffix(".db")))
        db.initialize()
        tid = db.create_tournament("Despacho", rounds_count=3, bye_points=1.0)
        for i, rating in enumerate((2000, 1900, 1800, 1700), start=1):
            db.create_player(tid, f"Jogador {i}", rating=rating, sex="m",
                             birth_date="2000-01-01")
        TRF16Exporter(ExportService(db, PairingService(db))).export(tid, path)

    def test_pairing_mode_writes_the_gacrux_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trf = Path(tmp) / "in.trf"
            out = Path(tmp) / "out.json"
            self._write_trf(trf)
            result = subprocess.run(
                [sys.executable, str(ROOT / "app.py"), "--gacrux", "pairing",
                 "-i", str(trf), "-o", str(out), "-b", "utf-8", "-p", "-n", "1",
                 "-m", "dutch", "-F", "JSON"],
                capture_output=True, text=True, cwd=tmp, timeout=120,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(data["status"]["code"], 0, data)
        self.assertEqual(len(data["pairingResult"]["pairs"]), 2)

    def test_exit_code_of_the_script_is_propagated(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "app.py"), "--gacrux", "tiebreak",
             "-i", "nao-existe.trf", "-F", "JSON"],
            capture_output=True, text=True, timeout=120,
        )
        self.assertNotEqual(result.returncode, 0)

    def test_bad_kind_fails_without_ui(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "app.py"), "--gacrux", "xyz"],
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(result.returncode, 2)


class SelfTestTests(unittest.TestCase):
    """RGS-05: ``app.py --self-test`` com o motor PADRAO (sem o conftest)."""

    def test_self_test_passes_with_the_default_engines(self) -> None:
        env = {k: v for k, v in os.environ.items() if not k.startswith("ALBERICUS_DEFAULT_")}
        with tempfile.TemporaryDirectory() as out:
            result = subprocess.run(
                [sys.executable, str(ROOT / "app.py"), "--self-test", out],
                capture_output=True, text=True, timeout=600, env=env, cwd=out,
            )
            report = json.loads((Path(out) / "selftest.json").read_text(encoding="utf-8"))
        failed = {s["name"]: s["detail"] for s in report["steps"] if not s["ok"]}
        self.assertEqual(failed, {})
        self.assertEqual(result.returncode, 0, result.stderr)
        names = [s["name"] for s in report["steps"]]
        self.assertEqual(
            names, ["i18n", "database", "gacrux_pairing", "gacrux_tiebreak", "export"]
        )
        tiebreak = next(s for s in report["steps"] if s["name"] == "gacrux_tiebreak")
        self.assertEqual(tiebreak["data"]["used"], "gacrux")

    def test_a_failing_step_gives_nonzero_exit_and_names_the_step(self) -> None:
        from src import selftest

        with tempfile.TemporaryDirectory() as out, mock.patch.object(
            selftest.SelfTest, "step_i18n", side_effect=selftest.SelfTestFailure("sem catalogo")
        ):
            code = selftest.run_self_test(Path(out))
            report = json.loads((Path(out) / "selftest.json").read_text(encoding="utf-8"))
        self.assertEqual(code, 1)
        first = report["steps"][0]
        self.assertEqual((first["name"], first["ok"], first["detail"]), ("i18n", False, "sem catalogo"))


class CallbackExceptionTests(unittest.TestCase):
    """RGS-04: excecao em callback vai ao log e ao dialogo, nao some no stderr."""

    def test_callback_exception_is_logged_and_shown(self) -> None:
        from src.ui.app import AlbericusApp

        shown = []

        class Spy:
            def _show_error(self, error) -> None:
                shown.append(error)

        try:
            raise RuntimeError("botao quebrado")
        except RuntimeError:
            exc_info = sys.exc_info()
        with self.assertLogs("src.ui", level="ERROR") as logs:
            AlbericusApp.report_callback_exception(Spy(), *exc_info)
        self.assertEqual(shown, [exc_info[1]])
        self.assertTrue(any("RuntimeError" in line and "botao quebrado" in line for line in logs.output))


if __name__ == "__main__":
    unittest.main()
