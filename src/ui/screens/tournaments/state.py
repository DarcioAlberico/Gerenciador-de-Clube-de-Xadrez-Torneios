"""Estado da tela de Torneios — dado puro (B-6, molde da F1.5).

Sem Tk, sem banco. Aqui moram as **regras do formulário** de criação e a forma
de uma linha da lista; quem fala com o serviço é o `controller`, quem monta
widget é a `view`.

A regra que justifica o módulo é o **escopo**: um torneio avulso não tem clube
nem turma, um de clube exige clube, e um de turma exige os dois. Isso estava
espalhado entre três closures que liam `OptionMenu` — impossível de testar sem
abrir janela, e fácil de divergir entre "o que a tela desabilita" e "o que a
criação valida".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Escopos, na ordem em que restringem: avulso não pede nada; clube pede clube;
# turma pede clube e turma.
SCOPE_STANDALONE = "standalone"
SCOPE_CLUB = "club"
SCOPE_CLASS = "class"

# Valores padrão do formulário (o que a tela já preenchia à mão).
DEFAULT_ROUNDS = "5"
DEFAULT_BYE_POINTS = "1.0"


@dataclass(frozen=True)
class TournamentForm:
    """Retrato do formulário de criação. Congelado: a view guarda a versão
    corrente por ``nonlocal``, como no piloto de Árbitros."""

    name: str = ""
    scope: str = SCOPE_STANDALONE
    competition_type: str = "individual"
    club_id: int | None = None
    class_id: int | None = None
    location: str = ""
    rounds_count: str = DEFAULT_ROUNDS
    time_control: str = ""
    start_date: str = ""
    end_date: str = ""
    bye_points: str = DEFAULT_BYE_POINTS

    def requires_club(self) -> bool:
        return self.scope in {SCOPE_CLUB, SCOPE_CLASS}

    def requires_class(self) -> bool:
        return self.scope == SCOPE_CLASS

    def validation_error(self) -> str | None:
        """Primeiro impedimento, ou ``None``. Ordem = ordem de leitura da tela.

        Devolver texto em vez de levantar deixa a decisão de *como* reclamar com
        a view (toast, diálogo, rótulo) — a regra não precisa saber disso.
        """
        if not self.name.strip():
            return "Informe o nome do torneio."
        if self.requires_club() and not self.club_id:
            return "Selecione o clube/escola do torneio."
        if self.requires_class() and not self.class_id:
            return "Selecione a turma do torneio."
        return None

    def payload(self) -> dict[str, Any]:
        """O que vai para o serviço.

        Clube e turma saem **nulos** quando o escopo não os pede: sem isto, um
        torneio avulso guardaria o clube que estava selecionado no menu quando
        o usuário mudou de ideia — e ninguém veria, porque a tela desabilita o
        campo, mas não o esvazia.
        """
        return {
            "name": self.name.strip(),
            "scope": self.scope,
            "competition_type": self.competition_type,
            "club_id": self.club_id if self.requires_club() else None,
            "class_id": self.class_id if self.requires_class() else None,
            "location": self.location,
            "rounds_count": self.rounds_count,
            "time_control": self.time_control,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "bye_points": self.bye_points,
        }


@dataclass(frozen=True)
class ScopeFieldState:
    """Quais campos a tela habilita para um escopo."""

    club_enabled: bool
    class_enabled: bool

    @property
    def club_widget_state(self) -> str:
        return "normal" if self.club_enabled else "disabled"

    @property
    def class_widget_state(self) -> str:
        return "normal" if self.class_enabled else "disabled"


def scope_fields(scope: str) -> ScopeFieldState:
    """O que habilitar, dado o escopo. Mesma fonte que ``validation_error``
    consulta — é o que impede a tela de pedir um campo que ela desabilitou."""
    return ScopeFieldState(
        club_enabled=scope in {SCOPE_CLUB, SCOPE_CLASS},
        class_enabled=scope == SCOPE_CLASS,
    )


@dataclass(frozen=True)
class TournamentRow:
    """Uma linha da lista, já formatada para a tabela."""

    tournament_id: int
    name: str
    competition: str
    scope: str
    club: str
    klass: str
    location: str
    rounds: str
    status: str

    def as_values(self) -> tuple[Any, ...]:
        return (
            self.tournament_id,
            self.name,
            self.competition,
            self.scope,
            self.club,
            self.klass,
            self.location,
            self.rounds,
            self.status,
        )


@dataclass
class TournamentListState:
    """Estado vivo da tela: o que está selecionado e as linhas carregadas."""

    rows: list[TournamentRow] = field(default_factory=list)
    selected_id: int | None = None

    def row(self, tournament_id: int) -> TournamentRow | None:
        return next((r for r in self.rows if r.tournament_id == tournament_id), None)

    @property
    def selected(self) -> TournamentRow | None:
        return self.row(self.selected_id) if self.selected_id is not None else None
