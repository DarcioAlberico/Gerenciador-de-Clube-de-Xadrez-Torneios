"""Run the local BBP Pairings reference fixtures.

This helper downloads the official v6.0.0 Windows binary on demand, verifies the
published SHA256 digest, and runs the reference fixtures stored in
``bbpPairings-6.0.0/test/tests``.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

VERSION = "v6.0.0"
ASSET_NAME = "bbpPairings-v6.0.0-x86_64-pc-windows.zip"
ASSET_URL = (
    "https://github.com/BieremaBoyzProgramming/bbpPairings/releases/download/"
    f"{VERSION}/{ASSET_NAME}"
)
ASSET_SHA256 = "d2bfc61cbd291a5458f18adccb43b19b6f1be40a9c0cc86a5142b605298dc0d7"
CASES = (
    ("dutch_2025_C5", "--dutch", "pair"),
    ("dutch_2025_C9", "--dutch", "pair"),
    ("issue_7", "--dutch", "pair"),
    ("issue_15", "--burstein", "check"),
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bbp-root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "bbpPairings-6.0.0",
        help="Path to the local bbpPairings-6.0.0 source/research folder.",
    )
    parser.add_argument(
        "--exe",
        type=Path,
        default=None,
        help="Use an existing bbpPairings.exe instead of the downloaded release binary.",
    )
    args = parser.parse_args()

    bbp_root = args.bbp_root.resolve()
    tests_dir = bbp_root / "test" / "tests"
    if not tests_dir.exists():
        print(f"BBP tests folder not found: {tests_dir}", file=sys.stderr)
        return 2

    exe_path = args.exe.resolve() if args.exe else ensure_bbp_exe(bbp_root)
    print(f"BBP executable: {exe_path}")
    print(f"Fixture folder: {tests_dir}")

    failures: list[str] = []
    for case_name, system, mode in CASES:
        ok, line_count, detail = run_case(exe_path, tests_dir, case_name, system, mode)
        status = "PASS" if ok else "FAIL"
        print(f"{status:4} {case_name:15} {system:10} lines={line_count}")
        if not ok:
            failures.append(f"{case_name}: {detail}")

    if failures:
        print("\nFailures:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    return 0


def ensure_bbp_exe(bbp_root: Path) -> Path:
    bin_dir = bbp_root / ".bin" / VERSION
    zip_path = bin_dir / ASSET_NAME
    extract_dir = bin_dir / "extract"
    exe_path = extract_dir / "bbpPairings-v6.0.0" / "bbpPairings.exe"

    bin_dir.mkdir(parents=True, exist_ok=True)
    if not zip_path.exists():
        print(f"Downloading {ASSET_URL}")
        urllib.request.urlretrieve(ASSET_URL, zip_path)

    digest = sha256(zip_path)
    if digest != ASSET_SHA256:
        raise RuntimeError(f"SHA256 mismatch for {zip_path}: {digest}")

    if not exe_path.exists():
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(extract_dir)
    if not exe_path.exists():
        matches = sorted(extract_dir.rglob("bbpPairings.exe"))
        if matches:
            exe_path = matches[0]
    if not exe_path.exists():
        raise RuntimeError(f"bbpPairings.exe not found after extraction under: {extract_dir}")
    return exe_path


def run_case(
    exe_path: Path,
    tests_dir: Path,
    case_name: str,
    system: str,
    mode: str,
) -> tuple[bool, int, str]:
    input_path = tests_dir / f"{case_name}.input"
    output_path = tests_dir / f"{case_name}.output"
    expected_path = tests_dir / f"{case_name}.output.expected"
    output_path.unlink(missing_ok=True)

    if mode == "pair":
        completed = subprocess.run(
            [str(exe_path), system, str(input_path), "-p", str(output_path)],
            check=False,
            capture_output=True,
            text=True,
        )
    else:
        completed = subprocess.run(
            [str(exe_path), system, str(input_path), "-c"],
            check=False,
            capture_output=True,
            text=True,
        )
        output_path.write_text(completed.stdout, encoding="utf-8")

    if completed.returncode != 0:
        return False, 0, completed.stderr.strip() or f"exit code {completed.returncode}"

    output_text = normalized_text(output_path)
    expected_text = normalized_text(expected_path)
    line_count = len([line for line in output_text.split("\n") if line])
    if output_text != expected_text:
        return False, line_count, "output differs from expected text"
    return True, line_count, ""


def normalized_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
