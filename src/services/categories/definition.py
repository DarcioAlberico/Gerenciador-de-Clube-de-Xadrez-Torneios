"""A categoria de um torneio como DADO (ORG-01).

As faixas viviam como constantes em `core/categories.py`: Sub-08 a Sub-20,
S50+/S65+ e cortes de 1400/1800/2200. Um edital com Sub-07/09/11/13, Veterano
60+ ou cortes de 1600/2000 não tinha onde caber, e "Feminino" era tag de prêmio
— não categoria, então não havia classificação feminina.

Aqui a categoria é um registro: nome, tipo, faixa e data de referência. Quem
decide se um jogador pertence a ela está em `matching`; o conjunto que
reproduz o comportamento histórico está em `defaults`.
"""

from __future__ import annotations

from dataclasses import dataclass

# Tipos de categoria.
AGE = "age"
RATING = "rating"
SEX = "sex"
TAG = "tag"
OPEN = "open"

KIND_LABELS = {
    AGE: "Faixa etária",
    RATING: "Faixa de rating",
    SEX: "Sexo",
    TAG: "Marca (sócio, local...)",
    OPEN: "Aberta (todos)",
}

KINDS = tuple(KIND_LABELS)


@dataclass(frozen=True)
class CategoryDefinition:
    """Uma categoria configurada de um torneio.

    **Faixa etária**: `max_value` é INCLUSIVO — "Sub-12" é `max_value=12`, e o
    jogador de 12 anos entra. **Faixa de rating**: `max_value` é EXCLUSIVO —
    "Sub-1400" é `max_value=1400`, e o jogador de 1400 fica fora.

    A assimetria não é descuido: é como o edital é escrito e como o programa já
    se comportava (`age <= limite`, `rating < limite`). Fazer os dois iguais
    obrigaria o árbitro a digitar 1399, que é onde o erro de digitação mora.

    `0` em `min_value`/`max_value` significa "sem limite desse lado".
    """

    name: str
    kind: str = OPEN
    min_value: int = 0
    max_value: int = 0
    sex: str = ""
    tag: str = ""
    reference_date: str = ""
    awards: bool = True
    position: int = 0

    @property
    def is_valid(self) -> bool:
        return bool(str(self.name).strip()) and self.kind in KINDS

    def describe(self) -> str:
        """Como a categoria aparece para o árbitro conferir o edital."""
        if self.kind == AGE:
            return _range_text(self.min_value, self.max_value, "ano(s)", inclusive_max=True)
        if self.kind == RATING:
            return _range_text(self.min_value, self.max_value, "de rating", inclusive_max=False)
        if self.kind == SEX:
            return {"F": "Feminino", "M": "Masculino"}.get(
                str(self.sex).strip().upper(), str(self.sex)
            )
        if self.kind == TAG:
            return f"Marca: {self.tag}"
        return "Todos os inscritos"


def _range_text(minimum: int, maximum: int, unit: str, *, inclusive_max: bool) -> str:
    low, high = int(minimum or 0), int(maximum or 0)
    if low and high:
        return f"{low} a {high if inclusive_max else high - 1} {unit}"
    if high:
        return f"até {high if inclusive_max else high - 1} {unit}"
    if low:
        return f"{low} {unit} ou mais"
    return f"sem limite de {unit}"


def normalize(definition: CategoryDefinition) -> CategoryDefinition:
    """Forma canônica: nome sem espaço sobrando, tipo conhecido, sexo em maiúscula."""
    from dataclasses import replace

    kind = str(definition.kind or OPEN).strip().lower()
    return replace(
        definition,
        name=str(definition.name or "").strip(),
        kind=kind if kind in KINDS else OPEN,
        min_value=max(int(definition.min_value or 0), 0),
        max_value=max(int(definition.max_value or 0), 0),
        sex=str(definition.sex or "").strip().upper()[:1],
        tag=str(definition.tag or "").strip(),
        reference_date=str(definition.reference_date or "").strip(),
    )


def from_row(row: object) -> CategoryDefinition:
    """Constrói a definição a partir de uma linha do banco (ou de um dicionário)."""
    data = dict(row) if not isinstance(row, dict) else row  # type: ignore[arg-type]
    return normalize(
        CategoryDefinition(
            name=str(data.get("name") or ""),
            kind=str(data.get("kind") or OPEN),
            min_value=int(data.get("min_value") or 0),
            max_value=int(data.get("max_value") or 0),
            sex=str(data.get("sex") or ""),
            tag=str(data.get("tag") or ""),
            reference_date=str(data.get("reference_date") or ""),
            awards=bool(data.get("awards", True)),
            position=int(data.get("position") or 0),
        )
    )
