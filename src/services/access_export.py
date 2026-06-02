"""Exportação para Microsoft Access (Fase J).

Replica o "Salvar em Access" do Swiss-Manager de forma **universal e sem
dependência obrigatória de driver**:

- Sempre gera um **pacote importável**: um ``.csv`` por tabela (UTF-8) + um
  ``schema.ini`` (Text ISAM) que o Access lê nativamente para importar/vincular
  as tabelas (Dados Externos → Arquivo de Texto).
- Quando o **driver ACE/Jet** (e o pywin32/ADOX) está disponível, também escreve
  um ``.accdb`` real automaticamente.

Módulo **puro** (stdlib); o ``.accdb`` é best-effort e nunca quebra a exportação.
"""

from __future__ import annotations

import csv
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# tabelas = {nome_tabela: (headers, rows)}
Tables = dict[str, "tuple[list[str], list[list[Any]]]"]


def _slug(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", (name or "Tabela").strip()).strip("_")
    return slug or "Tabela"


def build_schema_ini(csv_filenames: list[str]) -> str:
    """Conteúdo do ``schema.ini`` (Text ISAM) descrevendo cada CSV para o Access."""
    blocks = []
    for filename in csv_filenames:
        blocks.append(
            f"[{filename}]\n"
            "ColNameHeader=True\n"
            "Format=CSVDelimited\n"
            "CharacterSet=65001\n"
        )
    return "\n".join(blocks)


def write_csv_bundle(tables: Tables, dest_dir: str | Path) -> dict[str, Any]:
    """Escreve um CSV por tabela + ``schema.ini``. Devolve caminhos gerados."""
    directory = Path(dest_dir)
    directory.mkdir(parents=True, exist_ok=True)

    csv_paths: list[str] = []
    csv_filenames: list[str] = []
    for table_name, (headers, rows) in tables.items():
        filename = f"{_slug(table_name)}.csv"
        path = directory / filename
        # UTF-8 sem BOM combina com CharacterSet=65001 do schema.ini.
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(headers)
            for row in rows:
                writer.writerow(["" if cell is None else cell for cell in row])
        csv_paths.append(str(path))
        csv_filenames.append(filename)

    schema_path = directory / "schema.ini"
    schema_path.write_text(build_schema_ini(csv_filenames), encoding="utf-8")
    return {"csv_paths": csv_paths, "schema_ini": str(schema_path)}


def access_driver_available() -> bool:
    """True se houver um driver ODBC da Microsoft Access instalado (pyodbc)."""
    try:
        import pyodbc  # type: ignore
    except Exception:
        return False
    try:
        return any("microsoft access driver" in driver.lower() for driver in pyodbc.drivers())
    except Exception:
        return False


def write_accdb(tables: Tables, dest_path: str | Path) -> bool:
    """Best-effort: cria um ``.accdb`` real quando o stack (ADOX + ACE) existe.

    Devolve ``False`` (sem levantar) quando o driver/pywin32 não estão disponíveis
    ou em qualquer falha — nesse caso o pacote CSV é o entregável.
    """
    path = Path(dest_path)
    if not access_driver_available():
        return False
    try:
        import pyodbc  # type: ignore
        import win32com.client  # type: ignore

        if path.exists():
            path.unlink()
        catalog = win32com.client.Dispatch("ADOX.Catalog")
        catalog.Create(
            f"Provider=Microsoft.ACE.OLEDB.12.0;Data Source={path};"
        )
        catalog = None

        driver = next(d for d in pyodbc.drivers() if "microsoft access driver" in d.lower())
        connection = pyodbc.connect(f"DRIVER={{{driver}}};DBQ={path};")
        cursor = connection.cursor()
        for table_name, (headers, rows) in tables.items():
            table = _slug(table_name)
            columns = ", ".join(f"[{_slug(header)}] TEXT(255)" for header in headers)
            cursor.execute(f"CREATE TABLE [{table}] ({columns})")
            placeholders = ", ".join("?" for _ in headers)
            insert = f"INSERT INTO [{table}] VALUES ({placeholders})"
            for row in rows:
                cursor.execute(insert, ["" if cell is None else str(cell) for cell in row])
        connection.commit()
        connection.close()
        logger.info("Banco Access (.accdb) gerado em %s", path)
        return True
    except Exception as exc:  # driver ausente, ADOX indisponível, etc.
        logger.info("Nao foi possivel gerar .accdb real (%s); usando pacote CSV.", exc)
        return False
