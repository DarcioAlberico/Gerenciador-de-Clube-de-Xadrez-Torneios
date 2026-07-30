"""Estado da tela de Rodadas — dado puro (B-6, molde da F1.5).

Sem Tk, sem banco. Aqui moram as decisões que a tela tomava dentro de métodos
de 1.850 linhas: em que estado está um resultado, qual resultado o campo aceita
para a mesa selecionada, quantas rodadas o torneio deveria ter, como se lê a
prévia do emparceiramento e como o Modo Projetor divide as mesas em páginas.

**Por que isso é dado puro e não detalhe de tela:** "esta mesa foi corrigida",
"este resultado veio do QR e ainda não foi aprovado" e "a rodada está fechada"
são fatos do torneio, não de widget. A tela só os pinta. Separá-los deu teste
em milissegundos para a parte que mais dói errar — a que decide se o árbitro
pode ou não mexer num resultado.

O texto vem do catálogo quando a chave existe; o que ainda é literal aqui migra
na continuação da **B-3**, junto com o resto da tela.
"""
from __future__ import annotations

from typing import Any, Iterable, Sequence

from src.services.constants import RESULTS

# Estados possíveis de um resultado, na ordem de precedência em que são
# testados. A ordem **é** a regra: uma mesa corrigida por auditoria continua
# corrigida mesmo que tenha vindo do QR, e uma rodada fechada bloqueia o que
# ainda estiver vazio.
STATE_CORRECTED = "corrigido"
STATE_SUBMITTED = "submetido QR"
STATE_APPROVED = "aprovado QR"
STATE_REJECTED = "rejeitado QR"
STATE_LOCKED = "bloqueado"
STATE_EMPTY = "vazio"
STATE_RECORDED = "registrado"

_QR_STATUS_STATE = {
    "submitted": STATE_SUBMITTED,
    "approved": STATE_APPROVED,
    "rejected": STATE_REJECTED,
}

# Resultados extras que **só** um bye aceita: ausência (F), meio ponto (H) e
# zero sem partida (Z). Fora do bye eles não são oferecidos — é o que impede
# lançar "H" numa mesa com dois jogadores presentes.
BYE_RESULTS = ("BYE", "F", "H", "Z")

# Teclas de lançamento rápido → resultado. Tabela, não `if` encadeado: o
# teclado numérico manda `<KP_1>` e não `1`, e um `if` esconderia essa dobra.
RESULT_SHORTCUTS: dict[str, str] = {
    "1": "1-0",
    "<KP_1>": "1-0",
    "0": "0-1",
    "<KP_0>": "0-1",
    "-": "1/2-1/2",
    "<KP_Subtract>": "1/2-1/2",
    "<BackSpace>": "",
    "<Delete>": "",
}

# Índice da coluna "resultado" na tabela, por modo. Por equipes a linha carrega
# match e tabuleiro antes do resultado, e é essa diferença que fazia a busca
# pela primeira mesa pendente olhar a coluna errada no modo equipes.
RESULT_COLUMN_INDEX = {"individual": 3, "team": 6}


def individual_result_state(
    pairing: dict[str, Any],
    submissions_by_pairing: dict[int, dict[str, Any]],
    corrected_pairing_ids: Iterable[int],
) -> str:
    """Estado do resultado de uma mesa individual."""
    pairing_id = int(pairing["id"])
    if pairing_id in set(corrected_pairing_ids):
        return STATE_CORRECTED
    submissao = submissions_by_pairing.get(pairing_id)
    if submissao:
        estado = _QR_STATUS_STATE.get(str(submissao.get("status") or ""))
        if estado:
            return estado
    if pairing.get("round_status") == "closed":
        return STATE_LOCKED
    if not pairing.get("result"):
        return STATE_EMPTY
    return STATE_RECORDED


def team_board_result_state(
    board: dict[str, Any],
    corrected_team_board_ids: Iterable[int],
    round_status: str = "",
) -> str:
    """Estado do resultado de um tabuleiro de equipes.

    Não passa por QR: o envio por celular é individual, e um tabuleiro de
    equipes só é lançado pelo árbitro.
    """
    if int(board["id"]) in set(corrected_team_board_ids):
        return STATE_CORRECTED
    if round_status == "closed":
        return STATE_LOCKED
    if not board.get("result"):
        return STATE_EMPTY
    return STATE_RECORDED


def result_state_tag(state: str) -> str:
    """Nome da tag do ``Treeview`` para um estado ("submetido QR" → tag)."""
    return f"result_state_{str(state or '').replace(' ', '_').lower()}"


def allowed_results(pairing: dict[str, Any] | None) -> set[str]:
    """Resultados que o campo aceita para a mesa selecionada."""
    permitidos = set(RESULTS)
    if (
        pairing
        and pairing.get("row_type") == "individual_pairing"
        and pairing.get("is_bye")
    ):
        permitidos.update(BYE_RESULTS)
    return permitidos


def first_pending_index(rows: Sequence[Sequence[Any]], result_index: int) -> int:
    """Índice da primeira linha **sem** resultado; 0 quando todas têm.

    Devolver 0 e não ``None`` é decisão de UX: abrir a rodada já com a primeira
    mesa selecionada poupa um clique, e quando não há pendência a primeira mesa
    é o lugar mais útil para o cursor estar.
    """
    for indice, valores in enumerate(rows):
        resultado = valores[result_index] if len(valores) > result_index else ""
        if not resultado:
            return indice
    return 0


def recommended_rounds_for_players(players_count: int) -> int:
    """Mínimo de rodadas para separar os jogadores — ``ceil(log2(n))``.

    ``(n - 1).bit_length()`` é o mesmo número sem ponto flutuante: com 8
    jogadores dá 3, com 9 dá 4. É o piso do sistema suíço para que o campeão
    tenha enfrentado gente o bastante.
    """
    if players_count <= 1:
        return 1
    return (players_count - 1).bit_length()


def needs_round_count_warning(
    *,
    players_count: int,
    configured_rounds: int,
    has_rounds: bool,
    team_mode: bool,
) -> bool:
    """Se vale avisar que o torneio tem rodadas abaixo do recomendado.

    Não avisa depois da primeira rodada gerada (mudar o total ali é outra
    conversa), nem em torneio por equipes, nem com dois jogadores — onde o
    "recomendado" não diz nada.
    """
    if team_mode or has_rounds or players_count <= 2:
        return False
    return configured_rounds < recommended_rounds_for_players(players_count)


def format_pairing_preview(preview: dict[str, Any], *, limit: int = 12) -> str:
    """Texto da pré-visualização da próxima rodada.

    Corta em ``limit`` linhas e diz quantas sobraram: a prévia serve para
    conferir o topo do emparceiramento, não para ler 60 mesas num toast.
    """
    cabecalho = [
        f"Previa da rodada {preview['round_number']}",
        f"Sistema: {preview.get('pairing_system', '')}",
        f"Alertas: {preview.get('alerts_count', 0)}",
        "",
    ]
    if preview.get("competition_type") == "team":
        itens = list(preview.get("matches", []))
        linhas = [
            f"Match {match['match_number']}: "
            f"{match['white_team_name']} x {match['black_team_name']}"
            f"{_alertas(match)}"
            for match in itens[:limit]
        ]
    else:
        itens = list(preview.get("pairings", []))
        linhas = [
            f"Mesa {pairing['board_number']}: "
            f"{pairing['white_name']} x {pairing['black_name']}"
            f"{_alertas(pairing)}"
            for pairing in itens[:limit]
        ]
    if len(itens) > len(linhas):
        linhas.append(f"... mais {len(itens) - len(linhas)} item(ns)")
    if not linhas:
        linhas.append("Nenhuma mesa prevista.")
    linhas.append("")
    linhas.append("Esta pre-visualizacao nao gravou rodada no banco.")
    return "\n".join(cabecalho + linhas)


def _alertas(item: dict[str, Any]) -> str:
    alertas = item.get("alerts")
    return f" [{'; '.join(alertas)}]" if alertas else ""


# ---------------------------------------------------------------------------
# Modo Projetor: paginação
#
# A conta vivia em três closures dentro de um método de 290 linhas
# (`get_capacity`, `get_total_pages`, o fatiamento no `draw_page`), e é ela que
# decide se a última mesa aparece na parede ou não.
# ---------------------------------------------------------------------------
def projector_capacity(columns: int, rows_per_column: int) -> int:
    return max(1, columns * rows_per_column)


def projector_total_pages(total_items: int, capacity: int) -> int:
    """Sempre ao menos uma página — tela vazia também é uma página."""
    if capacity <= 0:
        return 1
    return max(1, -(-total_items // capacity))  # ceil sem float


def projector_page_items(
    items: Sequence[Any], page: int, capacity: int
) -> list[Any]:
    """Fatia da página ``page`` (base 0), presa ao intervalo existente."""
    total = projector_total_pages(len(items), capacity)
    pagina = page % total if total else 0
    inicio = pagina * capacity
    return list(items[inicio : inicio + capacity])


def projector_column_items(
    page_items: Sequence[Any], column: int, rows_per_column: int
) -> list[Any]:
    """Fatia de uma coluna dentro da página — a projeção enche coluna a coluna."""
    inicio = column * rows_per_column
    return list(page_items[inicio : inicio + rows_per_column])


def is_bye_row(row: dict[str, str]) -> bool:
    """Linha de bye na projeção: um dos lados é o próprio "BYE"."""
    return "BYE" in (row.get("white"), row.get("black"))


# ---------------------------------------------------------------------------
# Chamada inicial (a lista de presença antes da primeira rodada)
# ---------------------------------------------------------------------------
def initial_call_summary(players: Iterable[dict[str, Any]]) -> tuple[int, int, int]:
    """``(presentes, ausentes, total)`` — o resumo do topo da chamada."""
    lista = list(players)
    presentes = sum(1 for player in lista if player.get("player_status") == "active")
    return presentes, len(lista) - presentes, len(lista)


def initial_call_searchable(player: dict[str, Any], full_name: str) -> str:
    """Texto que a busca da chamada varre — nome, clube, categoria e rating.

    O nome chega pronto (``full_name``) porque montá-lo é regra de serviço, e
    este módulo não conhece serviço.
    """
    return " ".join(
        [
            full_name,
            str(player.get("club") or ""),
            str(player.get("category") or ""),
            str(player.get("rating") or ""),
        ]
    ).casefold()


def matches_initial_query(searchable: str, query: str) -> bool:
    termo = (query or "").strip().casefold()
    return not termo or termo in searchable


def next_presence_status(players: Iterable[dict[str, Any]]) -> str:
    """Status que a alternância de presença deve aplicar ao grupo.

    Regra: se **alguém** da seleção está ausente, o gesto marca todos como
    presentes; só quando todos já estão presentes é que ele marca ausência.
    Sem isso, alternar um grupo misto deixaria metade em cada estado e o
    árbitro teria de conferir linha por linha o que o próprio clique fez.
    """
    if any(player and player.get("player_status") != "active" for player in players):
        return "active"
    return "absent"
