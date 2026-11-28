"""Texto que vem de fora — arquivo ou download — lido por um caminho só (RG2-30).

Os importadores abriam cada um do seu jeito: ``utf-8-sig`` sem alternativa (o
CSV do Excel em português, cp1252, derrubava com ``UnicodeDecodeError``), o TRF
caía em ``latin-1`` (que nunca falha e troca letra calado), os downloads liam a
resposta inteira e um ``csv.Error`` subia como traceback. Aqui fica a regra:
UTF-8 (com ou sem BOM), depois Windows-1252, depois ``AppError`` que diz o
arquivo; download com teto; CSV com ``csv.Error`` traduzido.
"""
from __future__ import annotations

import csv
import io
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from src.services.constants import AppError

ENCODINGS = ("utf-8-sig", "cp1252")
MAX_DOWNLOAD_BYTES = 10 * 1024 * 1024


def decode_text(data: bytes, label: str) -> str:
    """Decodifica em UTF-8 e, se não for, em Windows-1252; senão, ``AppError``."""
    for encoding in ENCODINGS:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise AppError(
        f"{label}: o texto não está em UTF-8 nem em Windows-1252 (ANSI). "
        "Salve de novo como \"CSV UTF-8\" e importe outra vez."
    )


def read_text_file(path: str | Path) -> str:
    """Lê um arquivo de texto de importação pela regra única de codificação."""
    caminho = Path(path)
    try:
        data = caminho.read_bytes()
    except OSError as exc:
        raise AppError(f"Não foi possível ler {caminho.name}: {exc}") from exc
    return decode_text(data, caminho.name)


def download_text(
    url: str,
    *,
    timeout: float,
    label: str,
    user_agent: str = "Albericus",
    limit: int = MAX_DOWNLOAD_BYTES,
) -> str:
    """Baixa texto com teto de tamanho; falha de rede ou excesso viram ``AppError``."""
    request = Request(url, headers={"User-Agent": user_agent})
    try:
        with urlopen(request, timeout=timeout) as response:
            data = response.read(limit + 1)
    except (OSError, ValueError) as exc:
        raise AppError(f"Não foi possível baixar {label}: {exc}") from exc
    if len(data) > limit:
        raise AppError(f"Não foi possível baixar {label}: passa de {limit // (1024 * 1024)} MB.")
    return decode_text(data, label)


def csv_dialect(sample: str) -> Any:
    """Separador ``,`` ou ``;`` detectado na amostra; aspas sempre duplas."""
    try:
        detectado = csv.Sniffer().sniff(sample, delimiters=",;")
    except csv.Error:
        detectado = None
    if detectado is not None:
        # Do Sniffer, só o separador (RG2-20): com duas células protegidas
        # lado a lado ("'=1+1;'+55…") ele elegia "'" como aspas e partia o
        # texto. Excel, Google Sheets e o exportador usam aspas duplas.
        class DetectedDialect(csv.excel):
            delimiter = detectado.delimiter

        return DetectedDialect
    first_line = sample.splitlines()[0] if sample.splitlines() else ""
    if first_line.count(";") > first_line.count(","):
        class SemicolonDialect(csv.excel):
            delimiter = ";"

        return SemicolonDialect
    return csv.get_dialect("excel")


def csv_records(content: str, label: str = "CSV") -> tuple[list[str], Iterator[tuple[int, dict[str, Any]]]]:
    """Cabeçalhos e ``(linha, registro)`` de um CSV; sem cabeçalho ou ilegível → ``AppError``.

    A linha conta como antes nos importadores: o 1º registro é a linha 2.
    """
    reader = csv.DictReader(io.StringIO(content), dialect=csv_dialect(content[:4096]))
    try:
        fieldnames = reader.fieldnames
    except csv.Error as exc:
        raise AppError(f"{label}: cabeçalho ilegível ({exc}).") from exc
    if not fieldnames:
        raise AppError(f"{label} sem cabeçalho.")
    return [str(name) for name in fieldnames], _records(reader, label)


def _records(reader: csv.DictReader[str], label: str) -> Iterator[tuple[int, dict[str, Any]]]:
    try:
        for line_number, row in enumerate(reader, start=2):
            yield line_number, row
    except csv.Error as exc:
        raise AppError(f"{label}: linha {reader.line_num} ilegível ({exc}).") from exc
