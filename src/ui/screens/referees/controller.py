"""Controlador da tela de Árbitros — decide, sem desenhar.

Conversa com o serviço e devolve estado (``state.py``). **Não importa Tk**: é o
que permite testar a regra da tela sem abrir janela, que é o aceite da F1.5.

    controller = RefereesController(app.referee_service, app.db)
    linhas = controller.rows()
    form = controller.load(7)
    controller.save(form.with_values(name="Novo nome"))
"""
from __future__ import annotations

from typing import Any, Protocol

from .state import RefereeForm, RefereeRow


class RefereeService(Protocol):
    """O pedaço do serviço que esta tela usa — declarado para o teste poder
    entregar um dublê sem arrastar banco junto."""

    def list_referees(self, active_only: bool = True) -> list[dict[str, Any]]: ...
    def create_referee(self, data: dict[str, Any]) -> int: ...
    def update_referee(self, referee_id: int, data: dict[str, Any]) -> None: ...


class RefereeReader(Protocol):
    def get_referee(self, referee_id: int) -> dict[str, Any] | None: ...


class RefereesController:
    def __init__(self, service: RefereeService, reader: RefereeReader) -> None:
        self._service = service
        self._reader = reader

    def rows(self) -> list[RefereeRow]:
        """Todos os árbitros, inclusive inativos — a tela mostra os dois."""
        return [RefereeRow.from_record(item) for item in self._service.list_referees(active_only=False)]

    def load(self, referee_id: int) -> RefereeForm | None:
        """Formulário preenchido com um árbitro, ou ``None`` se ele sumiu."""
        registro = self._reader.get_referee(int(referee_id))
        if not registro:
            return None
        return RefereeForm.from_record(registro)

    def save(self, form: RefereeForm) -> int:
        """Cria ou atualiza, conforme o formulário tenha id. Devolve o id.

        A validação (nome obrigatório) fica no serviço: a tela não repete regra
        de negócio, só deixa o erro subir para virar feedback.
        """
        payload = form.to_payload()
        if form.is_new:
            return int(self._service.create_referee(payload))
        self._service.update_referee(int(form.selected_id), payload)
        return int(form.selected_id)
