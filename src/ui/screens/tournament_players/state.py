"""Estado da tela de Jogadores — dado puro (B-6, molde da F1.5).

Sem Tk, sem banco. Aqui moram as regras do formulário de inscrição, a forma de
uma linha da tabela, a contagem do resumo, o texto que a busca varre e o
preenchimento automático a partir das bases oficiais.

Três dessas cinco coisas viviam dentro de closures de `show_players` — 1.613
linhas em que a única forma de exercitar "o que acontece quando o rating vem
'abc'" era digitar na janela. Aqui elas são função, e o teste roda em
milissegundos.

O texto vem do catálogo (**B-3**): este módulo é puro, e
[`i18n`](../../i18n.py) também é — importar um do outro não fura camada nenhuma.
"""
from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from typing import Any

from src.services.constants import player_full_name

from ...i18n import t

# Campos do cadastro, na ordem em que a tela os desenha. O rótulo **não** está
# aqui: mora no catálogo, sob `players.field.<chave>`.
PLAYER_FIELDS: tuple[str, ...] = (
    "name",
    "surname",
    "given_name",
    "title",
    "sex",
    "rating",
    "national_rating",
    "international_rating",
    "fide_id",
    "cbx_id",
    "lbx_id",
    "club",
    "category",
    "birth_date",
)

# Campos numéricos: o formulário guarda texto, o banco guarda inteiro.
RATING_FIELDS: tuple[str, ...] = ("rating", "national_rating", "international_rating")

# Campos que disparam a busca na base oficial ao perder o foco.
OFFICIAL_ID_FIELDS: tuple[str, ...] = ("fide_id", "cbx_id", "lbx_id")

# Grupos do sistema Scheveningen. Código vazio = jogador sem grupo.
SCHEVENINGEN_GROUPS: tuple[str, ...] = ("", "A", "B")


def field_labels() -> dict[str, str]:
    """Chave do campo → rótulo do catálogo.

    Escrito à mão, campo a campo, e **não** por ``t(f"players.field.{chave}")``:
    chave montada em f-string é invisível para o teste que cobra que toda chave
    usada exista no catálogo (`test_ui_i18n`). Uma chave que só aparece quando o
    usuário abre a tela é exatamente o que esse teste existe para evitar.
    """
    return {
        "name": t("players.field.name"),
        "surname": t("players.field.surname"),
        "given_name": t("players.field.given_name"),
        "title": t("players.field.title"),
        "sex": t("players.field.sex"),
        "rating": t("players.field.rating"),
        "national_rating": t("players.field.national_rating"),
        "international_rating": t("players.field.international_rating"),
        "fide_id": t("players.field.fide_id"),
        "cbx_id": t("players.field.cbx_id"),
        "lbx_id": t("players.field.lbx_id"),
        "club": t("players.field.club"),
        "category": t("players.field.category"),
        "birth_date": t("players.field.birth_date"),
    }


def scheveningen_labels() -> dict[str, str]:
    """Código → rótulo, resolvido no catálogo a cada chamada.

    Função e não constante de módulo: constante congelaria o texto no idioma
    carregado durante o *import*, e a promessa da B-3 é que trocar o catálogo
    troque a tela.
    """
    return {
        "": t("players.scheveningen.none"),
        "A": t("players.scheveningen.a"),
        "B": t("players.scheveningen.b"),
    }


def normalize_scheveningen_group(value: Any) -> str:
    """Código do grupo vindo do banco, saneado. Desconhecido vira "sem grupo"."""
    codigo = str(value or "").strip().upper()
    return codigo if codigo in SCHEVENINGEN_GROUPS else ""


def parse_rating(text: str) -> int | None:
    """Texto do formulário → inteiro. ``None`` quando não é número.

    Vazio é zero (o cadastro sem rating é legítimo); "abc" é ``None``, e quem
    chama transforma isso em recado. Antes, `int("abc")` subia como `ValueError`
    e a tela dizia "Erro inesperado" com código de log — para um erro de
    digitação previsível.
    """
    limpo = (text or "").strip()
    if not limpo:
        return 0
    try:
        return int(limpo)
    except ValueError:
        return None


@dataclass(frozen=True)
class PlayerForm:
    """Retrato do formulário de jogador. Congelado, como no piloto de Árbitros."""

    name: str = ""
    surname: str = ""
    given_name: str = ""
    title: str = ""
    sex: str = ""
    rating: str = ""
    national_rating: str = ""
    international_rating: str = ""
    fide_id: str = ""
    cbx_id: str = ""
    lbx_id: str = ""
    club: str = ""
    category: str = ""
    birth_date: str = ""
    status: str = "active"

    def validation_error(self) -> str | None:
        """Primeiro impedimento, ou ``None``. Ordem = ordem de leitura da tela."""
        if not self.name.strip():
            return t("players.error.name_required")
        rotulos = field_labels()
        for campo in RATING_FIELDS:
            if parse_rating(getattr(self, campo)) is None:
                return t("players.error.rating_not_a_number", campo=rotulos[campo])
        return None

    def rating_value(self, field: str) -> int:
        """Inteiro de um campo de rating. Só chame depois de ``validation_error``."""
        return parse_rating(getattr(self, field)) or 0

    def _common_payload(self) -> dict[str, Any]:
        return {
            "name": self.name.strip(),
            "club": self.club,
            "rating": self.rating_value("rating"),
            "category": self.category,
            "fide_id": self.fide_id,
            "birth_date": self.birth_date,
            "surname": self.surname,
            "given_name": self.given_name,
            "title": self.title,
            "sex": self.sex,
            "cbx_id": self.cbx_id,
            "lbx_id": self.lbx_id,
            "national_rating": self.rating_value("national_rating"),
            "international_rating": self.rating_value("international_rating"),
            "player_status": self.status,
        }

    def create_payload(self, starting_points: float | None = None) -> dict[str, Any]:
        """O que vai para ``create_player``. Federação nasce vazia, como antes."""
        payload = self._common_payload()
        payload["federation_id"] = ""
        payload["starting_points"] = starting_points
        return payload

    def update_payload(self, current: Mapping[str, Any]) -> dict[str, Any]:
        """O que vai para ``update_player``.

        ``active`` e ``federation_id`` vêm do registro atual: são dados que a
        tela não mostra, e sobrescrevê-los com o padrão apagaria escolha feita
        em outro lugar.
        """
        payload = self._common_payload()
        payload["active"] = int(current["active"])
        payload["federation_id"] = current.get("federation_id", "")
        return payload


def form_from_player(player: Mapping[str, Any], status: str = "") -> PlayerForm:
    """Preenche o formulário a partir de um jogador do banco."""
    valores = {campo: str(player.get(campo, "") or "") for campo in PLAYER_FIELDS}
    return PlayerForm(
        **valores,
        status=status or str(player.get("player_status") or "active"),
    )


def autofill_updates(
    official: Mapping[str, Any],
    source_key: str,
    empty_fields: Collection[str],
) -> dict[str, str]:
    """Campos a preencher a partir da base oficial, dado o ID digitado.

    Só preenche o que está **vazio**: o que o operador digitou vence o que a
    base diz. Valor falso (0, "") não é oferecido — zerar um rating por causa de
    um registro incompleto seria pior que não preencher.
    """
    atualizacoes: dict[str, str] = {}

    def oferecer(campo: str, valor: Any) -> None:
        if campo in empty_fields and valor:
            atualizacoes[campo] = str(valor)

    for campo in (
        "name",
        "surname",
        "given_name",
        "title",
        "sex",
        "birth_date",
        "international_rating",
        "national_rating",
    ):
        oferecer(campo, official.get(campo))
    oferecer(
        "rating",
        official.get("standard_rating")
        or official.get("international_rating")
        or official.get("national_rating"),
    )
    if source_key == "fide_id":
        oferecer("cbx_id", official.get("cbx_id"))
        oferecer("lbx_id", official.get("lbx_id"))
    elif source_key == "cbx_id":
        oferecer("fide_id", official.get("fide_id"))
    return atualizacoes


def searchable_text(player: Mapping[str, Any]) -> str:
    """Tudo que a busca da tela varre, em minúsculas e sem quebra."""
    partes = [
        player_full_name(player),
        player.get("name"),
        player.get("surname"),
        player.get("given_name"),
        player.get("club"),
        player.get("active_class_name"),
        player.get("category"),
        player.get("age_category"),
        player.get("rating_category"),
        player.get("prize_tags"),
        player.get("rating"),
        player.get("fide_id"),
        player.get("cbx_id"),
        player.get("lbx_id"),
        player.get("national_rating"),
        player.get("international_rating"),
    ]
    return " ".join(str(parte or "") for parte in partes).casefold()


def matches(query: str, player: Mapping[str, Any]) -> bool:
    """Busca vazia mostra tudo — é o estado inicial da tela."""
    consulta = (query or "").strip().casefold()
    return not consulta or consulta in searchable_text(player)


@dataclass(frozen=True)
class PlayerRow:
    """Uma linha da tabela, já formatada."""

    player_id: int
    name: str
    source: str
    rating: Any
    fide_id: str
    cbx_id: str
    lbx_id: str
    club: str
    klass: str
    category: str
    age_category: str
    rating_category: str
    tags: str
    status: str

    def as_values(self) -> tuple[Any, ...]:
        return (
            self.player_id,
            self.name,
            self.source,
            self.rating,
            self.fide_id,
            self.cbx_id,
            self.lbx_id,
            self.club,
            self.klass,
            self.category,
            self.age_category,
            self.rating_category,
            self.tags,
            self.status,
        )


@dataclass(frozen=True)
class PlayersSummary:
    """Contagem do cabeçalho da tabela."""

    total: int = 0
    visible: int = 0
    present: int = 0
    members: int = 0

    @property
    def absent(self) -> int:
        return self.total - self.present

    @property
    def guests(self) -> int:
        return self.total - self.members

    def as_text(self) -> str:
        return t(
            "players.summary",
            total=self.total,
            visiveis=self.visible,
            presentes=self.present,
            ausentes=self.absent,
            membros=self.members,
            convidados=self.guests,
        )


def summarize(players: list[Mapping[str, Any]], visible: int) -> PlayersSummary:
    """Contagens do resumo. ``visible`` é quantas linhas a busca deixou passar."""
    return PlayersSummary(
        total=len(players),
        visible=visible,
        present=sum(1 for jogador in players if jogador.get("player_status") == "active"),
        members=sum(1 for jogador in players if jogador.get("member_id")),
    )
