"""Estado da tela de Árbitros — dado puro, sem Tk e sem banco.

Piloto da F1.5 (achados P0-2 e P0-3). O que existia antes era um
``{"value": None}`` guardando o id selecionado e um punhado de widgets como
única fonte de verdade: para saber o que a tela "tinha", era preciso perguntar
aos widgets. Aqui o estado é um ``dataclass`` congelado — dá para montar,
comparar e testar sem abrir janela.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping

# Ordem dos campos de texto no formulário. Mora aqui, e não na view, porque é
# a mesma ordem que define o payload enviado ao serviço.
CAMPOS_TEXTO: tuple[tuple[str, str], ...] = (
    ("name", "Nome"),
    ("federation_id", "ID Federação"),
    ("fide_id", "FIDE ID"),
    ("cbx_id", "CBX ID"),
    ("phone", "Telefone"),
    ("email", "E-mail"),
    ("notes", "Observações"),
)

CATEGORIAS: tuple[str, ...] = ("AN", "AR", "AF", "AI", "Outro")
CATEGORIA_PADRAO = CATEGORIAS[0]


@dataclass(frozen=True)
class RefereeForm:
    """Conteúdo do formulário. ``selected_id`` vazio significa cadastro novo."""

    selected_id: int | None = None
    name: str = ""
    federation_id: str = ""
    fide_id: str = ""
    cbx_id: str = ""
    phone: str = ""
    email: str = ""
    notes: str = ""
    category: str = CATEGORIA_PADRAO
    active: bool = True

    @property
    def is_new(self) -> bool:
        return not self.selected_id

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> RefereeForm:
        """Monta o formulário a partir de um registro do banco.

        Campo ausente ou ``None`` vira string vazia — o formulário mostra vazio,
        nunca a palavra "None", que era o que acontecia com ``str(valor)``.
        """
        texto = {chave: str(record.get(chave) or "") for chave, _rotulo in CAMPOS_TEXTO}
        return cls(
            selected_id=int(record["id"]) if record.get("id") is not None else None,
            category=str(record.get("category") or CATEGORIA_PADRAO),
            active=bool(record.get("active")),
            **texto,
        )

    def to_payload(self) -> dict[str, Any]:
        """Payload para o serviço. ``active`` vai como 0/1, como o banco espera."""
        payload: dict[str, Any] = {chave: getattr(self, chave) for chave, _ in CAMPOS_TEXTO}
        payload["category"] = self.category
        payload["active"] = 1 if self.active else 0
        return payload

    def cleared(self) -> RefereeForm:
        """Formulário zerado, pronto para um cadastro novo."""
        return RefereeForm()

    def with_values(self, **valores: Any) -> RefereeForm:
        return replace(self, **valores)


@dataclass(frozen=True)
class RefereeRow:
    """Uma linha da tabela. Separada do formulário: a tabela mostra menos."""

    id: int
    name: str
    category: str
    fide_id: str
    cbx_id: str
    active: bool

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> RefereeRow:
        return cls(
            id=int(record["id"]),
            name=str(record.get("name") or ""),
            category=str(record.get("category") or ""),
            fide_id=str(record.get("fide_id") or ""),
            cbx_id=str(record.get("cbx_id") or ""),
            active=bool(record.get("active")),
        )

    def as_values(self) -> tuple[Any, ...]:
        """Valores na ordem das colunas, já com o "Sim"/"Não" legível."""
        return (self.id, self.name, self.category, self.fide_id, self.cbx_id,
                "Sim" if self.active else "Não")
