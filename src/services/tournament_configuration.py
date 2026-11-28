"""Plano de confirmações para salvar as configurações do torneio (RGS-09).

Antes, cada confirmação era descoberta por uma recusa do serviço: a tela
salvava, o serviço recusava com "Confirme para apagar essas datas", a tela
perguntava e salvava de novo, o serviço recusava com "Informe o motivo", e
assim por diante. Cada volta já tinha gravado a auditoria da anterior, e
reduzir rodadas junto com uma mudança de ordem inicial nunca saía do laço.

Aqui o plano é uma função PURA: recebe o estado atual e o pedido já validado,
e devolve TODAS as confirmações de uma vez. Quem lê o banco e grava é o
``TournamentService``; a tela mostra um diálogo só com a lista.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from src.services.constants import RESERVE_ENGINE_LABEL, RESERVE_PAIRING_SYSTEMS

# Tipos de confirmação. São estáveis: a tela devolve ao serviço os tipos que o
# árbitro confirmou, e o serviço recusa se faltar algum.
TIPO_AGENDA_PERDIDA = "schedule_loss"
TIPO_MUDANCA_ESTRUTURAL = "structural_change"
TIPO_MUDANCAS_PERIGOSAS = "dangerous_changes"
TIPO_MOTOR_RESERVA = "reserve_engine"
TIPO_RECALCULO_CATEGORIAS = "category_recalculation"

# Configurações que mudam o SIGNIFICADO do torneio (ORG-04): trocar qualquer
# uma no meio do caminho reescreve como as rodadas já jogadas deveriam ter
# sido ordenadas ou pareadas.
STRUCTURAL_SETTINGS: tuple[str, ...] = (
    "initial_order",
    "acceleration_method",
    "tiebreak_sequence",
    "team_tiebreak_sequence",
)

_ROTULOS_ESTRUTURAIS = {
    "initial_order": "ordem inicial",
    "acceleration_method": "aceleração",
    "tiebreak_sequence": "sequência de desempates",
    "team_tiebreak_sequence": "sequência de desempates por equipe",
}


@dataclass(frozen=True)
class Confirmacao:
    """Uma decisão que o árbitro precisa tomar antes de salvar."""

    tipo: str
    mensagem: str
    exige_motivo: bool = False


@dataclass(frozen=True)
class PerfilTorneio:
    """O que a aba Geral/Regras/Agenda manda salvar, ainda sem validar."""

    torneio: Mapping[str, Any]
    ajustes: Mapping[str, Any]
    agenda: Sequence[Mapping[str, Any]] = field(default_factory=tuple)


def agenda_perdida(agenda: Sequence[Mapping[str, Any]], total_rodadas: int) -> list[dict[str, Any]]:
    """Linhas da agenda, acima do novo total, que têm data ou hora marcada (ORG-03)."""
    perdidas: list[dict[str, Any]] = []
    for item in agenda:
        try:
            numero = int(item.get("round_number") or 0)
        except (TypeError, ValueError):
            continue
        if numero > int(total_rodadas) and (
            str(item.get("date", "")).strip() or str(item.get("time", "")).strip()
        ):
            perdidas.append(dict(item))
    return perdidas


def mudancas_estruturais(
    ajustes_atuais: Mapping[str, Any],
    ajustes_pedidos: Mapping[str, Any],
    ajustes_validados: Mapping[str, Any],
) -> dict[str, tuple[Any, Any]]:
    """Campo estrutural -> (antes, depois), só para o que a tela enviou e mudou."""
    return {
        campo: (ajustes_atuais.get(campo), ajustes_validados.get(campo))
        for campo in STRUCTURAL_SETTINGS
        if campo in ajustes_pedidos
        and str(ajustes_atuais.get(campo) or "") != str(ajustes_validados.get(campo) or "")
    }


def liga_mudancas_perigosas(
    ajustes_atuais: Mapping[str, Any],
    ajustes_pedidos: Mapping[str, Any],
    ajustes_validados: Mapping[str, Any],
) -> bool:
    return (
        "allow_dangerous_changes" in ajustes_pedidos
        and not int(ajustes_atuais.get("allow_dangerous_changes") or 0)
        and bool(int(ajustes_validados.get("allow_dangerous_changes") or 0))
    )


def escolhe_motor_reserva(
    ajustes_atuais: Mapping[str, Any],
    ajustes_pedidos: Mapping[str, Any],
    ajustes_validados: Mapping[str, Any],
) -> tuple[str, str] | None:
    """(antes, depois) quando o pedido TROCA o sistema para um do motor reserva."""
    if "pairing_system" not in ajustes_pedidos:
        return None
    antes = str(ajustes_atuais.get("pairing_system") or "")
    depois = str(ajustes_validados.get("pairing_system") or "")
    if depois == antes or depois not in RESERVE_PAIRING_SYSTEMS:
        return None
    return antes, depois


def plan_tournament_configuration(
    *,
    rodadas_geradas: int,
    ajustes_atuais: Mapping[str, Any],
    ajustes_pedidos: Mapping[str, Any],
    ajustes_validados: Mapping[str, Any],
    total_rodadas: int,
    agenda: Sequence[Mapping[str, Any]],
) -> list[Confirmacao]:
    """Todas as confirmações que salvar este pedido exige, na ordem de leitura.

    ``rodadas_geradas`` é o número da maior rodada já gerada (0 = nenhuma);
    ``ajustes_pedidos`` é o que a tela enviou (para saber o que ela de fato
    mexeu) e ``ajustes_validados`` o mesmo pedido depois da validação.
    """
    confirmacoes: list[Confirmacao] = []

    perdidas = agenda_perdida(agenda, total_rodadas)
    if perdidas:
        numeros = ", ".join(
            str(numero) for numero in sorted({int(item["round_number"]) for item in perdidas})
        )
        confirmacoes.append(
            Confirmacao(
                tipo=TIPO_AGENDA_PERDIDA,
                mensagem=(
                    f"A agenda tem data marcada para a(s) rodada(s) {numeros}, acima do total "
                    f"configurado ({int(total_rodadas)}). Confirme para apagar essas datas, "
                    "aumente o total de rodadas ou limpe a agenda dessas rodadas."
                ),
            )
        )

    if escolhe_motor_reserva(ajustes_atuais, ajustes_pedidos, ajustes_validados):
        # RGS-18: vale antes da R1 também — é a escolha que decide quem pareia.
        confirmacoes.append(
            Confirmacao(
                tipo=TIPO_MOTOR_RESERVA,
                mensagem=(
                    f"O sistema escolhido pareia pelo {RESERVE_ENGINE_LABEL}: ele não segue o "
                    "holandês completo (C.04.3) e o emparceiramento não é o do motor FIDE "
                    "(Gacrux). Confirme apenas se o regulamento autoriza; a escolha fica na "
                    "auditoria."
                ),
            )
        )

    if rodadas_geradas > 0:
        mudancas = mudancas_estruturais(ajustes_atuais, ajustes_pedidos, ajustes_validados)
        if mudancas:
            campos = ", ".join(_ROTULOS_ESTRUTURAIS.get(campo, campo) for campo in mudancas)
            confirmacoes.append(
                Confirmacao(
                    tipo=TIPO_MUDANCA_ESTRUTURAL,
                    mensagem=(
                        f"O torneio já tem rodada gerada e você está mudando: {campos}. "
                        "Isso muda a classificação já publicada. Informe o motivo da mudança "
                        "para registrar na auditoria."
                    ),
                    exige_motivo=True,
                )
            )
        if liga_mudancas_perigosas(ajustes_atuais, ajustes_pedidos, ajustes_validados):
            confirmacoes.append(
                Confirmacao(
                    tipo=TIPO_MUDANCAS_PERIGOSAS,
                    mensagem=(
                        "Permitir mudanças perigosas libera a edição de rodadas já fechadas em "
                        "todo o torneio, sem prazo. Para corrigir um resultado, prefira "
                        "“Corrigir resultado…” na mesa, em Rodadas ou no Painel (clique direito ou Ctrl+E): o motivo "
                        "desbloqueia só aquela rodada, por 15 min, e registra a correção."
                    ),
                )
            )

    return confirmacoes


def confirmacao_recalculo_categorias(rodadas_fechadas: int) -> Confirmacao:
    """Mudar edital ou datas depois de rodada fechada recalcula as categorias (RG2-15, D3)."""
    rodadas = "a 1ª rodada" if rodadas_fechadas == 1 else f"{rodadas_fechadas} rodadas"
    return Confirmacao(
        tipo=TIPO_RECALCULO_CATEGORIAS,
        mensagem=(
            f"O torneio já tem {rodadas} fechada(s) e você está mudando as categorias ou as datas "
            "que as definem. As categorias dos jogadores serão recalculadas — a classificação por "
            "categoria e a premiação mudam a partir de agora. Os retratos das rodadas fechadas "
            "ficam com a categoria da época, e a mudança fica na auditoria."
        ),
    )


def confirmacoes_pendentes(
    confirmacoes: Sequence[Confirmacao], confirmadas: Sequence[str] | set[str], motivo: str
) -> list[Confirmacao]:
    """As que o árbitro não confirmou — ou confirmou sem dar o motivo exigido."""
    aceitas = set(confirmadas)
    tem_motivo = bool(str(motivo or "").strip())
    return [
        item
        for item in confirmacoes
        if item.tipo not in aceitas or (item.exige_motivo and not tem_motivo)
    ]
