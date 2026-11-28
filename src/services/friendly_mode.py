"""Modo Amistoso — a regra do modo escolar mora aqui (MA-01).

No app o modo se chama **Modo Livre** (menu "Torneio | Livre", marca
``tournament_settings.free_mode``). O nome visível sai de
``FRIENDLY_MODE_LABEL``: trocar para "Modo Amistoso" (decisão D1 da
``ESPEC_REVISAO_MODO_AMISTOSO.md``) é mudar uma linha.

Aqui fica só o que é DECISÃO do modo: rótulo, predicado, preset de criação,
conflito com o perfil FIDE e a linha de atraso da súmula. Os textos de cada
tela continuam na tela.

O modo flexibiliza a CONDUÇÃO do torneio (entrada, rodada refeita, atraso),
não o motor: o emparceiramento continua o holandês, e cada exceção fica na
auditoria.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

from src.services.constants import AppError
from src.services.permissions import requires

FRIENDLY_MODE_LABEL = "Modo Livre"
OFFICIAL_MODE_LABEL = "Modo Oficial"

# O que o aviso do modo promete (MA-11): só o que existe de verdade.
NOTICE_ITEMS = (
    "Alunos entram a qualquer momento, já na rodada em andamento ou na próxima.",
    "Refaça a rodada com quem está presente e ajuste mesas à mão.",
    "Súmula sem W.O. automático por atraso.",
    "Mais uma rodada quando sobrar tempo.",
    "Não vale rating FIDE nem CBX.",
)

# Meio ponto pedagógico por rodada perdida (MA-14.1). ½ é valor que o TRF
# registra (bye H), então o torneio continua exportável para o Gacrux.
FRIENDLY_LATE_ENTRY_POINTS = 0.5
DEFAULT_ROUNDS = 5
MAX_ROUNDS = 30


def is_friendly(settings: Mapping[str, Any] | None) -> bool:
    """True se os ajustes do torneio têm a marca do modo."""
    return bool((settings or {}).get("free_mode"))


def mode_label(free_mode: bool) -> str:
    return FRIENDLY_MODE_LABEL if free_mode else OFFICIAL_MODE_LABEL


def friendly_preset() -> dict[str, Any]:
    """Ajustes gravados quando o torneio nasce no modo."""
    return {"late_entry_points": FRIENDLY_LATE_ENTRY_POINTS}


def default_name(today: date | None = None) -> str:
    return f"Torneio Amistoso {(today or date.today()).strftime('%d/%m/%Y')}"


def rounds_count_error(rounds_count: Any) -> str:
    """Por que este número de rodadas não serve. ``""`` quando serve."""
    try:
        valor = int(str(rounds_count).strip())
    except (TypeError, ValueError):
        valor = 0
    if 1 <= valor <= MAX_ROUNDS:
        return ""
    return f"Informe um número de rodadas de 1 a {MAX_ROUNDS}."


RATING_REFUSAL = (
    f"Torneio no {FRIENDLY_MODE_LABEL}: não vale rating FIDE nem CBX. "
    f"Para submeter, desligue o {FRIENDLY_MODE_LABEL} em Configurações do torneio "
    "e confira o regulamento."
)


INTERNAL_RATING_YES = "Contar no rating"
INTERNAL_RATING_NO = "Não contar"


def internal_rating_question(settings: Mapping[str, Any] | None) -> str:
    """A pergunta antes de o amistoso contar para o rating interno (decisão D2).

    Vazia no torneio oficial, que conta sem perguntar. No amistoso, o serviço
    recusa aplicar sem a resposta (`friendly_confirmed=True`), e a tela pergunta.
    """
    if not is_friendly(settings):
        return ""
    return (
        f"Este torneio está no {FRIENDLY_MODE_LABEL}: entrada tardia com pontos "
        "dados e rodadas refeitas. Ele deve contar para o rating interno do clube?"
    )


def profile_conflict(free_mode: bool, profile: Any) -> str:
    """Por que o modo e o perfil não convivem. ``""`` quando convivem (MA-02).

    O torneio amistoso flexibiliza entrada, rodada e atraso: não cumpre o
    regulamento de rating da FIDE. Uma função só decide, nos dois sentidos —
    salvar o perfil FIDE num torneio amistoso e ligar o modo num torneio FIDE.
    """
    if free_mode and str(profile or "").strip() == "fide":
        return (
            f"O {FRIENDLY_MODE_LABEL} não combina com o perfil FIDE-rated: o modo "
            "flexibiliza entrada, rodada e atraso, e o torneio não vale rating. "
            f"Desligue o {FRIENDLY_MODE_LABEL} antes de escolher o perfil FIDE."
        )
    return ""


def late_tolerance_line(free_mode: bool, minutes: int) -> str:
    """Linha de atraso da súmula no modo (MA-05). ``""`` = o texto oficial de sempre.

    O aviso do modo promete súmula sem W.O. automático por atraso; com
    tolerância 0 (o padrão de todo torneio) a súmula dizia "perde a hora
    marcada". Tolerância configurada vale igual no oficial e no amistoso.
    """
    if free_mode and int(minutes or 0) <= 0:
        return f"Atraso: sem W.O. automático ({FRIENDLY_MODE_LABEL})"
    return ""


def is_round_limit_error(
    tournament: Mapping[str, Any] | None, latest_round: Mapping[str, Any] | None
) -> bool:
    """True quando a próxima geração esbarraria no total de rodadas (MA-09).

    A tela pergunta antes de gerar, em vez de ler o texto do erro.
    """
    if not tournament or not latest_round:
        return False
    return str(latest_round.get("status")) == "closed" and int(latest_round.get("number") or 0) >= int(
        tournament.get("rounds_count") or 0
    )


def require_friendly(settings: Mapping[str, Any] | None, action: str) -> None:
    """Recusa a ação do modo num torneio oficial, dizendo por quê."""
    if not is_friendly(settings):
        raise AppError(
            f"{action}: disponível apenas no {FRIENDLY_MODE_LABEL}.",
            suggestion=(
                f"Ligue o {FRIENDLY_MODE_LABEL} em Configurações do torneio, "
                "ou use as ferramentas de arbitragem do Modo Oficial."
            ),
        )


def _details_with_rounds(torneio: Mapping[str, Any], rounds_count: int) -> dict[str, Any]:
    """Os dados do torneio como ``update_tournament_details`` pede, com outro total de rodadas."""
    texto = {campo: str(torneio.get(campo) or "") for campo in ("name", "location", "time_control", "start_date", "end_date")}
    return {
        **texto,
        "club_id": torneio.get("club_id"),
        "rounds_count": int(rounds_count),
        "bye_points": float(torneio.get("bye_points") or 0.0),
        "class_id": torneio.get("class_id"),
        "competition_type": str(torneio.get("competition_type") or "individual"),
    }


class FriendlyModeService:
    """Casos de uso do modo: criar, ligar/desligar, mais uma rodada, entrada tardia."""

    def __init__(self, db: Any) -> None:
        self.db = db

    @requires("tournament_write")
    def create(
        self,
        name: str,
        rounds_count: Any = DEFAULT_ROUNDS,
        *,
        class_id: int | None = None,
    ) -> dict[str, Any]:
        """Cria o torneio já no modo, com o preset (MA-01, MA-14.1)."""
        from src.services.tournament_service import TournamentService

        erro = rounds_count_error(rounds_count)
        if erro:
            raise AppError(erro)
        nome = " ".join(str(name or "").split()) or default_name()
        dados: dict[str, Any] = {
            "name": nome,
            "rounds_count": str(int(str(rounds_count).strip())),
            "bye_points": "1",
        }
        if class_id:
            # MA-08: a turma do cadastro vira o torneio (escopo "class").
            dados.update({"scope": "class", "class_id": int(class_id)})
        inscritos = 0
        with self.db.transaction():
            tournament_id = int(TournamentService(self.db).create_tournament(dados))
            self.db.set_free_mode(tournament_id, True)
            self.db.save_tournament_settings(tournament_id, friendly_preset())
            if class_id:
                from src.services.member_service import MemberService

                feito = MemberService(self.db).register_active_members_in_tournament(tournament_id)
                inscritos = int(feito.get("registered") or 0)
        return {"tournament_id": tournament_id, "name": nome, "registered": inscritos}

    def school_classes(self) -> list[dict[str, Any]]:
        """Turmas ativas para a lista da criação (MA-08): id, nome e escola."""
        turmas = []
        for turma in self.db.list_classes(active_only=True):
            escola = str(turma.get("club_name") or "").strip()
            nome = str(turma.get("name") or "").strip()
            alunos = int(turma.get("active_members_count") or 0)
            contagem = "1 aluno" if alunos == 1 else f"{alunos} alunos"
            rotulo = f"{nome} – {escola} ({contagem})" if escola else f"{nome} ({contagem})"
            turmas.append({"id": int(turma["id"]), "label": rotulo})
        return turmas

    def _settings(self, tournament_id: int) -> dict[str, Any]:
        return dict(self.db.get_tournament_settings(int(tournament_id)) or {})

    @requires("tournament_write")
    def set_enabled(self, tournament_id: int, enabled: bool, actor: str = "") -> bool:
        """Liga ou desliga o modo num torneio que já existe (MA-07), com auditoria.

        Ligar num torneio de perfil FIDE é recusado (MA-02). Devolve ``True``
        quando a marca mudou; pedir o estado que já vale não grava nada.
        """
        if not self.db.get_tournament(int(tournament_id)):
            raise AppError("Selecione um torneio válido.")
        ajustes = self._settings(tournament_id)
        antes = is_friendly(ajustes)
        if antes == bool(enabled):
            return False
        conflito = profile_conflict(bool(enabled), ajustes.get("tournament_profile"))
        if conflito:
            raise AppError(conflito)
        with self.db.transaction():
            self.db.set_free_mode(int(tournament_id), bool(enabled))
            self.db.create_audit_event(
                action="free_mode_changed",
                tournament_id=int(tournament_id),
                entity_type="tournament",
                entity_id=int(tournament_id),
                actor=actor,
                before={"free_mode": int(antes)},
                after={"free_mode": int(bool(enabled))},
            )
        return True

    @requires("tournament_write")
    def add_round(self, tournament_id: int, actor: str = "") -> int:
        """Mais uma rodada no torneio amistoso (MA-09). Devolve o novo total."""
        require_friendly(self._settings(tournament_id), "Mais uma rodada")
        torneio = self.db.get_tournament(int(tournament_id))
        if not torneio:
            raise AppError("Selecione um torneio válido.")
        antes = int(torneio.get("rounds_count") or 0)
        if antes >= MAX_ROUNDS:
            raise AppError(f"O {FRIENDLY_MODE_LABEL} vai até {MAX_ROUNDS} rodadas.")
        total = antes + 1
        with self.db.transaction():
            self.db.update_tournament_details(int(tournament_id), **_details_with_rounds(torneio, total))
            self.db.create_audit_event(
                action="friendly_round_added",
                tournament_id=int(tournament_id),
                entity_type="tournament",
                entity_id=int(tournament_id),
                actor=actor,
                before={"rounds_count": antes},
                after={"rounds_count": total},
            )
        return total

    @requires("tournament_write")
    def late_entry(
        self,
        tournament_id: int,
        data: Mapping[str, Any],
        *,
        per_round_points: float = FRIENDLY_LATE_ENTRY_POINTS,
        join_open_round: bool = False,
        reason: str = "",
        reserve_engine: bool = False,
        actor: str = "",
    ) -> dict[str, Any]:
        """Aluno que chega depois: o MESMO plano do assistente (MA-04).

        "Esperar a próxima": ``register_late_entry`` como no oficial, com 0 ou
        ½ por rodada perdida. "Jogar já nesta rodada" (``join_open_round``): a
        rodada aberta é a de entrada e é refeita com o aluno. Inscrição e
        re-emparceiramento correm numa transação: se refazer falha, o aluno
        também não fica inscrito.
        """
        from src.services.pairing_service import PairingService

        require_friendly(self._settings(tournament_id), "Entrada tardia")
        pairing = PairingService(self.db)
        ultima = self.db.get_latest_round(int(tournament_id)) or {}
        aberta = bool(ultima) and str(ultima.get("status")) != "closed"
        with self.db.transaction():
            feito = pairing.register_late_entry(
                int(tournament_id),
                data,
                per_round_points,
                actor,
                join_open_round=join_open_round and aberta,
            )
            if join_open_round and aberta:
                pairing.repair_open_round(
                    int(tournament_id),
                    int(ultima["id"]),
                    # Sem padrão: com resultado anotado, o motivo é do professor.
                    reason,
                    reserve_engine=reserve_engine,
                )
        return feito
