from __future__ import annotations

from pathlib import Path

import markdown
from xhtml2pdf import pisa

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "docs" / "Manual_Operacional_Arbitragem.md"
OUTPUT_PATH = ROOT / "docs" / "Manual_Operacional_Arbitragem.pdf"


def build_pdf() -> Path:
    html_content = markdown.markdown(
        SOURCE_PATH.read_text(encoding="utf-8"),
        extensions=["tables"],
    )
    full_html = f"""
    <html>
    <head>
    <meta charset="utf-8">
    <style>
        @page {{
            size: A4;
            margin: 1.3cm;
        }}
        body {{
            color: #1f2937;
            font-family: Helvetica, Arial, sans-serif;
            font-size: 9pt;
            line-height: 1.25;
        }}
        h1 {{ color: #1d4ed8; font-size: 18pt; text-align: center; }}
        h2 {{ color: #1e3a8a; font-size: 13pt; margin-top: 14px; }}
        h3 {{ color: #334155; font-size: 10.5pt; margin-top: 10px; }}
        p {{ margin: 4px 0; }}
        ul {{ margin: 4px 0 8px 16px; padding: 0; }}
        li {{ margin-bottom: 2px; }}
        table {{
            border-collapse: collapse;
            margin: 6px 0 10px 0;
            width: 100%;
        }}
        th {{
            background-color: #dbeafe;
            color: #1e3a8a;
            font-weight: bold;
        }}
        th, td {{
            border: 0.5px solid #94a3b8;
            padding: 3px;
            vertical-align: top;
        }}
        code {{ color: #0f172a; font-family: Courier; font-size: 8pt; }}
    </style>
    </head>
    <body>{html_content}</body>
    </html>
    """
    with OUTPUT_PATH.open("wb") as output_file:
        status = pisa.CreatePDF(
            full_html.encode("utf-8"),
            dest=output_file,
            encoding="utf-8",
        )
    if status.err:
        raise RuntimeError(f"Falha ao gerar manual operacional: {status.err}")
    return OUTPUT_PATH


if __name__ == "__main__":
    print(build_pdf().resolve())
