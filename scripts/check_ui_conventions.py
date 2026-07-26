"""Lint das convenções de UI que o ruff não expressa (F1.6 e F3.3).

Duas regras, ambas com a mesma logica: o que ja existe fica registrado numa
linha de base explicita, e **qualquer coisa nova reprova**. A divida some pela
lista encolher, nunca por alguem afrouxar a regra.

1. `import *` em `src/ui` (achado P0-4). O ruff acusa F403, mas as telas legadas
   precisariam de um `per-file-ignore` cada; a linha de base abaixo faz esse
   papel e some junto com as telas migradas.

2. Cor ou tamanho de fonte cravado em `src/ui/screens` (P2-1/P2-2/P2-3). Vale a
   regra: **nomear e permitido, embutir nao**. Uma constante de modulo
   (`PROJETOR_FUNDO = "#000000"`) passa; a mesma cor dentro de uma chamada de
   widget reprova — a primeira diz o que a cor significa, a segunda so a esconde.

Uso:
    python scripts/check_ui_conventions.py           # reprova o que e novo
    python scripts/check_ui_conventions.py --baseline # reimprime a linha de base
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
UI = RAIZ / "src" / "ui"
TELAS = UI / "screens"

# --- Linha de base: telas que ainda usam `from ..support import *` -----------
# Encolhe a cada tela migrada para imports explicitos (F1.6). Nao cresce.
WILDCARD_PERMITIDO = {
    "app.py",
    "screens/admin.py",
    "screens/admin_calendar_ranking.py",
    "screens/admin_exercises_inventory.py",
    "screens/admin_training_finance.py",
    "screens/club.py",
    "screens/club_members_ui.py",
    "screens/communication.py",
    "screens/free_tournament.py",
    "screens/integrations.py",
    "screens/pairing_arbitration_ui.py",
    "screens/pairing_results_ui.py",
    "screens/pairings.py",
    "screens/settings.py",
    "screens/settings_certificates_ui.py",
    "screens/settings_reports_ui.py",
    "screens/settings_users_ui.py",
    "screens/tournament_settings_ui.py",
    "screens/tournament_widgets.py",
    "screens/tournaments/pages.py",
}

# `\.+` e nao `\.{1,2}`: a B-6 moveu uma tela para subpacote e o `import *`
# dela virou `from ...support import *` — com o limite antigo, mudar de
# profundidade escapava do lint em silencio.
_WILDCARD = re.compile(r"^\s*from\s+\.+support\s+import\s+\*", re.MULTILINE)
_HEX = re.compile(r"#[0-9a-fA-F]{6}\b")
_FONTE = re.compile(r"CTkFont\(\s*size\s*=\s*\d+")
_CONSTANTE = re.compile(r"^[A-Z][A-Z0-9_]*\s*(:.*)?=")
_CORES_NOMEADAS = re.compile(
    r"(?:text_color|fg_color|hover_color|border_color|foreground|background)\s*=\s*"
    r"[\"'](?:gray|grey|red|white|black|blue|green|yellow|orange)[\"']"
)


def _relativo(caminho: Path) -> str:
    return caminho.relative_to(UI).as_posix()


def checar_wildcards() -> list[str]:
    problemas = []
    for arquivo in sorted(UI.rglob("*.py")):
        texto = arquivo.read_text(encoding="utf-8")
        if not _WILDCARD.search(texto):
            continue
        nome = _relativo(arquivo)
        if nome not in WILDCARD_PERMITIDO:
            problemas.append(
                f"{nome}: `from ..support import *` novo. Importe os nomes "
                f"explicitamente (P0-4/F1.6)."
            )
    # a linha de base tambem nao pode envelhecer: arquivo migrado sai da lista
    presentes = {
        _relativo(arquivo)
        for arquivo in UI.rglob("*.py")
        if _WILDCARD.search(arquivo.read_text(encoding="utf-8"))
    }
    for obsoleto in sorted(WILDCARD_PERMITIDO - presentes):
        problemas.append(
            f"{obsoleto}: nao usa mais `import *` — remova-o de WILDCARD_PERMITIDO "
            f"em scripts/check_ui_conventions.py."
        )
    return problemas


def checar_cores_e_fontes() -> list[str]:
    problemas = []
    for arquivo in sorted(TELAS.rglob("*.py")):
        nome = _relativo(arquivo)
        for numero, linha in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), start=1):
            sem_comentario = linha.split("#", 1)[0] if not _HEX.search(linha) else linha
            if _CONSTANTE.match(linha.strip()):
                continue  # constante nomeada: permitido, e o jeito certo
            if _HEX.search(linha) and not linha.lstrip().startswith("#"):
                problemas.append(
                    f"{nome}:{numero}: cor cravada. Use um token de theme.py ou "
                    f"de uma constante de modulo com nome (P2-1/F3.3)."
                )
            elif _CORES_NOMEADAS.search(sem_comentario):
                problemas.append(
                    f"{nome}:{numero}: cor nomeada do Tk ('gray', 'red'...). "
                    f"Use um token de theme.py (P2-1/F3.3)."
                )
            elif _FONTE.search(sem_comentario):
                problemas.append(
                    f"{nome}:{numero}: tamanho de fonte cravado. Use SIZE_* de "
                    f"theme.py (P2-2/F3.3)."
                )
    return problemas


def main() -> int:
    if "--baseline" in sys.argv:
        atuais = sorted(
            _relativo(arquivo)
            for arquivo in UI.rglob("*.py")
            if _WILDCARD.search(arquivo.read_text(encoding="utf-8"))
        )
        print("WILDCARD_PERMITIDO = {")
        for nome in atuais:
            print(f'    "{nome}",')
        print("}")
        return 0

    problemas = checar_wildcards() + checar_cores_e_fontes()
    if problemas:
        print("Convencoes de UI violadas:\n")
        for problema in problemas:
            print(f"  {problema}")
        print(f"\n{len(problemas)} problema(s).")
        return 1
    print(
        f"Convencoes de UI OK "
        f"({len(WILDCARD_PERMITIDO)} tela(s) ainda com `import *`, e so encolhe)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
