"""Ponte com o Chess-Results.com (spec — Fase J).

O Chess-Results.com **não expõe API pública de upload**: o envio é feito pelo
próprio binário Swiss-Manager (mesmo autor). A integração honesta e coerente com
o offline-first do Albericus é, portanto, uma **ponte**:

- **Saída (publicar):** geramos o arquivo TRF16 (FIDE/Krause) — o formato de
  intercâmbio universal — e abrimos a página do Chess-Results no navegador para o
  organizador enviar/gerir o torneio manualmente (login próprio).
- **Entrada (importar):** lemos a lista de jogadores/inscrições publicada do
  Chess-Results em CSV e a convertemos em jogadores do torneio.

Este módulo é **puro** (só stdlib): mapeamento de colunas e textos de apoio. A
persistência/efeitos ficam no `ChessResultsService`.
"""

from __future__ import annotations

import csv
import io
from typing import Any

# Páginas públicas do Chess-Results usadas pela ponte (abrir no navegador).
CHESS_RESULTS_HOME = "https://chess-results.com/"
# Formulário público de "registro de torneio" (organizador solicita a criação).
CHESS_RESULTS_REGISTER_URL = "https://chess-results.com/anmeldung.aspx?lan=1"


def normalize_results_url(raw: str) -> str:
    """Normaliza um link de torneio do Chess-Results (ou devolve "" se inválido).

    Aceita formas como ``chess-results.com/tnr123.aspx`` e devolve a URL https
    completa. Não faz requisição de rede — é só validação textual.
    """
    text = (raw or "").strip()
    if not text:
        return ""
    lowered = text.lower()
    if lowered.startswith("http://"):
        text = "https://" + text[len("http://"):]
        lowered = text.lower()
    if not lowered.startswith("https://"):
        text = "https://" + text
        lowered = text.lower()
    # Precisa apontar para o domínio do Chess-Results para evitar links soltos.
    if "chess-results.com" not in lowered:
        return ""
    return text


def build_upload_steps(tournament: dict[str, Any], trf_name: str) -> list[str]:
    """Passos honestos (PT-BR) para publicar o torneio no Chess-Results.

    Não promete upload automático (não há API pública); descreve a ponte via TRF.
    """
    name = str((tournament or {}).get("name") or "torneio").strip() or "torneio"
    return [
        f"1. O arquivo TRF16 do torneio \"{name}\" foi gerado: {trf_name}.",
        "2. Faça login na sua conta de organizador em chess-results.com "
        "(ou solicite o cadastro do torneio na página de registro).",
        "3. No Chess-Results/Swiss-Manager, crie/abra o torneio e use a opção de "
        "importar arquivo FIDE (TRF16) para carregar jogadores e resultados.",
        "4. Publique/atualize o torneio pelo próprio Chess-Results. O Albericus "
        "não envia automaticamente porque o site não oferece API pública de upload.",
        "5. Opcional: cole a URL publicada do torneio no Albericus para guardar o "
        "link e reabri-lo depois.",
    ]


# Cabeçalhos comuns das listas exportadas do Chess-Results (PT/EN/DE), por campo.
_ENTRY_ALIASES: dict[str, tuple[str, ...]] = {
    "name": ("name", "nome", "player", "jogador", "spieler", "nombre"),
    "surname": ("surname", "sobrenome", "last name", "last_name", "nachname"),
    "given_name": ("given name", "given_name", "first name", "first_name", "vorname"),
    "rating": ("rtg", "rating", "elo", "rtgi", "rtg int", "rtg_int", "rtgnat", "rtg nat"),
    "federation": ("fed", "federation", "federacao", "federação", "país", "pais", "country"),
    "fide_id": ("fideid", "fide id", "fide-id", "fide_id", "id fide", "id-fide", "id no", "id-number", "id number", "no"),
    "cbx_id": ("cbx", "cbx id", "cbx_id", "id cbx"),
    "title": ("title", "titulo", "título", "tit", "titel"),
    "sex": ("sex", "s", "sexo", "geschlecht", "type", "tipo"),
    "club": ("club", "clube", "club/city", "club/cidade", "cidade", "city", "verein", "club/ciudad"),
    "birth_date": ("byear", "b-year", "b year", "year", "ano", "nascimento", "birthday", "birth", "geb", "gj"),
}


def _normalize_header(header: str) -> str:
    return (header or "").strip().lower().replace(".", "").replace("º", "").strip()


def _pick(row: dict[str, str], field: str) -> str:
    for alias in _ENTRY_ALIASES.get(field, ()):  # ordem = prioridade
        if alias in row and str(row[alias]).strip():
            return str(row[alias]).strip()
    return ""


def _parse_rating(value: str) -> int:
    text = (value or "").strip()
    if not text:
        return 0
    try:
        return int(float(text))
    except ValueError:
        return 0


def parse_entries_csv(content: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Converte um CSV de inscrições/lista do Chess-Results em payloads de jogador.

    Devolve ``(payloads, erros)``. Cada payload usa as chaves aceitas por
    ``Database.create_player`` (name, surname, rating, federation_id, fide_id,
    sex, title, club, birth_date...). Linhas sem nome são reportadas como erro.
    """
    text = content or ""
    if not text.strip():
        return [], ["Arquivo vazio."]

    sample = text[:4096]
    try:
        dialect: Any = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        return [], ["CSV sem cabeçalho."]

    payloads: list[dict[str, Any]] = []
    errors: list[str] = []
    for line_number, raw_row in enumerate(reader, start=2):
        row = {_normalize_header(key): (value or "") for key, value in raw_row.items() if key}
        name = _pick(row, "name")
        surname = _pick(row, "surname")
        given_name = _pick(row, "given_name")
        if not name and (surname or given_name):
            name = " ".join(part for part in [given_name, surname] if part).strip()
        if not name and "," in (surname or ""):
            # Suporta "Sobrenome, Nome" numa só coluna.
            surname, name = [part.strip() for part in surname.split(",", maxsplit=1)]
        if not name:
            errors.append(f"Linha {line_number}: nome vazio.")
            continue

        rating = _parse_rating(_pick(row, "rating"))
        payloads.append(
            {
                "name": name,
                "surname": surname,
                "given_name": given_name,
                "rating": rating,
                "international_rating": rating,
                "federation_id": _pick(row, "federation"),
                "fide_id": _pick(row, "fide_id"),
                "cbx_id": _pick(row, "cbx_id"),
                "title": _pick(row, "title"),
                "sex": _pick(row, "sex")[:1].upper(),
                "club": _pick(row, "club"),
                "birth_date": _pick(row, "birth_date"),
            }
        )

    if not payloads and not errors:
        errors.append("Nenhuma inscrição reconhecida no arquivo.")
    return payloads, errors
