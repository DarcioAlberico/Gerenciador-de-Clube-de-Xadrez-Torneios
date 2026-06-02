"""Listas de rating estrangeiras (Fase J).

O Albericus já importa FIDE/CBX/LBX. Este módulo abre a importação para
**federações estrangeiras** (nacionais) por um **mapeamento genérico de colunas**:
em vez de embutir o formato de dezenas de federações, mantemos um registro
semeado (extensível pelo usuário) e um mapeador de linhas que aceita aliases
comuns ou um mapa explícito campo→coluna.

Módulo **puro** (só stdlib). O rating nacional da federação entra em
``national_rating``/``standard_rating`` (espelho), mantendo o mesmo shape de
payload de :meth:`OfficialRatingService._official_payload`.
"""

from __future__ import annotations

from typing import Any

# Registro semeado de federações estrangeiras (código FIDE de 3 letras).
# ``url`` opcional habilita o download direto; vazio = só import por arquivo.
# É um ponto de partida — o usuário adiciona outras pela UI (app_settings).
FOREIGN_FEDERATIONS: dict[str, dict[str, str]] = {
    "POR": {"name": "Portugal (FPX)", "url": "", "notes": "Federacao Portuguesa de Xadrez"},
    "ESP": {"name": "Espanha (FEDA)", "url": "", "notes": "Federacion Espanola de Ajedrez"},
    "ARG": {"name": "Argentina (FADA)", "url": "", "notes": "Federacion Argentina de Ajedrez"},
    "URU": {"name": "Uruguai (FAU)", "url": "", "notes": "Federacion Uruguaya de Ajedrez"},
    "PAR": {"name": "Paraguai (FEPARAX)", "url": "", "notes": "Federacion Paraguaya de Ajedrez"},
    "CHI": {"name": "Chile (FENACHED)", "url": "", "notes": "Federacion Nacional de Ajedrez de Chile"},
    "COL": {"name": "Colombia (FECODAZ)", "url": "", "notes": "Federacion Colombiana de Ajedrez"},
    "USA": {"name": "Estados Unidos (USCF)", "url": "", "notes": "US Chess Federation"},
    "GER": {"name": "Alemanha (DSB)", "url": "", "notes": "Deutscher Schachbund"},
    "FRA": {"name": "Franca (FFE)", "url": "", "notes": "Federation Francaise des Echecs"},
    "ITA": {"name": "Italia (FSI)", "url": "", "notes": "Federazione Scacchistica Italiana"},
    "POL": {"name": "Polonia (PZSzach)", "url": "", "notes": "Polski Zwiazek Szachowy"},
}

# Campos de saída e seus aliases de cabeçalho (minúsculos) para o mapeamento.
COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "external_id": ("id", "id_no", "idno", "codigo", "code", "no", "nr", "rid", "player_id"),
    "name": ("name", "nome", "jogador", "player", "spieler", "nombre", "fullname"),
    "surname": ("surname", "sobrenome", "last_name", "apellido", "nachname"),
    "given_name": ("given_name", "nome_proprio", "first_name", "nombre_propio", "vorname"),
    "rating": ("rating", "elo", "rtg", "rtg_nat", "rtgnat", "rating_nacional", "national_rating", "puntos"),
    "fide_id": ("fide_id", "fide", "fideid", "fide_no", "id_fide"),
    "cbx_id": ("cbx_id", "cbx", "cbxid"),
    "title": ("title", "titulo", "tit", "titel"),
    "sex": ("sex", "sexo", "s", "geschlecht"),
    "federation": ("federation", "fed", "federacao", "pais", "country"),
    "club": ("club", "clube", "cidade", "city", "clubname", "verein"),
    "birth_date": ("birth_date", "nascimento", "data_nascimento", "ano", "ano_nasc", "byear", "b-year", "birthday", "gj"),
}


def normalize_federation_code(code: str) -> str:
    """Código FIDE em maiúsculas (2–4 letras). Devolve "" se claramente inválido."""
    text = (code or "").strip().upper()
    if not (2 <= len(text) <= 4) or not text.isalpha():
        return ""
    return text


def seed_federations() -> dict[str, dict[str, str]]:
    """Cópia do registro semeado (para a UI mesclar com extensões do usuário)."""
    return {code: dict(info) for code, info in FOREIGN_FEDERATIONS.items()}


def _parse_int(value: Any) -> int:
    text = str(value or "").strip()
    if not text:
        return 0
    try:
        return int(float(text))
    except ValueError:
        return 0


def _pick(row: dict[str, str], field: str, mapping: dict[str, str] | None) -> str:
    if mapping and mapping.get(field):
        header = str(mapping[field]).strip().lower()
        return str(row.get(header, "")).strip()
    for alias in COLUMN_ALIASES.get(field, ()):
        if alias in row and str(row[alias]).strip():
            return str(row[alias]).strip()
    return ""


def map_row(
    row: dict[str, str],
    federation: str,
    mapping: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    """Mapeia uma linha (cabeçalhos já em minúsculas) para o payload oficial.

    ``mapping`` opcional é campo→cabeçalho explícito; sem ele, usa ``COLUMN_ALIASES``.
    Devolve ``None`` quando não há nome reconhecível.
    """
    normalized = {str(key).strip().lower(): ("" if value is None else str(value)) for key, value in row.items()}
    fed_code = normalize_federation_code(federation) or normalize_federation_code(_pick(normalized, "federation", mapping))

    name = _pick(normalized, "name", mapping)
    surname = _pick(normalized, "surname", mapping)
    given_name = _pick(normalized, "given_name", mapping)
    if not name:
        name = " ".join(part for part in [given_name, surname] if part).strip()
    if not name and "," in surname:
        surname, name = [part.strip() for part in surname.split(",", maxsplit=1)]
    if not name:
        return None

    rating = _parse_int(_pick(normalized, "rating", mapping))
    external_id = _pick(normalized, "external_id", mapping) or _pick(normalized, "fide_id", mapping)

    return {
        "external_id": external_id,
        "fide_id": _pick(normalized, "fide_id", mapping),
        "cbx_id": _pick(normalized, "cbx_id", mapping),
        "name": name,
        "surname": surname,
        "given_name": given_name,
        "title": _pick(normalized, "title", mapping),
        "sex": _pick(normalized, "sex", mapping)[:1].upper(),
        "federation": fed_code,
        "club": _pick(normalized, "club", mapping),
        "birth_date": _pick(normalized, "birth_date", mapping),
        "national_rating": rating,
        # Lista nacional estrangeira carrega o rating da própria federação (nacional),
        # não um Elo FIDE internacional — este fica zerado.
        "international_rating": 0,
        "standard_rating": rating,
        "rapid_rating": 0,
        "blitz_rating": 0,
    }
