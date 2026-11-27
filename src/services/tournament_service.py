from __future__ import annotations
import csv
import html
import json
import logging
import math
import secrets
import shutil
import sqlite3
import unicodedata
from datetime import date, datetime, time, timedelta
from pathlib import Path
from dataclasses import dataclass, field as dataclass_field
from typing import Any, Mapping, Sequence, TYPE_CHECKING

from src.core.database import BASE_DIR, DEFAULT_CERTIFICATE_TEMPLATES, Database
from src.core.database_tournament_core import default_pairing_system
from src.domain.dates import Data, DateError, normalize_date, parse_date
from src.services.constants import *
from src.services.pairing import (
    acceleration_spec,
    parse_player_tiebreak_sequence,
    parse_team_tiebreak_sequence,
    serialize_tiebreak_sequence,
)
from src.services.pairing.constraints import seeding_order
from src.services.pairing.pairing_check import tpn_correction_reason_error
from src.services.pairing.initial_color import normalize_initial_color, resolve_initial_color
from src.services import friendly_mode
from src.services.prizes import PRIZE_POLICIES, PRIZE_TIE_SPLITS
from src.services.categories import from_row as category_from_row, normalize as normalize_category
from src.services.rating import SPEED_CHOICES, serialize_regulation_overrides
from src.services.list_layout_service import validated_columns
from src.services.prize_service import validated_prizes
from src.services.tournament_configuration import (
    STRUCTURAL_SETTINGS,
    TIPO_AGENDA_PERDIDA,
    TIPO_MUDANCA_ESTRUTURAL,
    TIPO_MUDANCAS_PERIGOSAS,
    TIPO_MOTOR_RESERVA,
    Confirmacao,
    PerfilTorneio,
    agenda_perdida,
    confirmacoes_pendentes,
    escolhe_motor_reserva,
    liga_mudancas_perigosas,
    mudancas_estruturais,
    plan_tournament_configuration,
)

if TYPE_CHECKING:
    from src.services.club_service import ClubService
    from src.services.member_service import MemberService, GuardianService
    from src.services.tournament_service import TournamentService, RefereeService, TeamService
    from src.services.pairing_service import PairingService
    from src.services.finance_service import FinanceService
    from src.services.event_service import EventService, CalendarService
    from src.services.education_service import TrainingService, ExerciseService, LibraryService, LearningLevelService
    from src.services.inventory_service import InventoryService
    from src.services.security_service import SecurityService
    from src.services.export_service import ExportService, ImportService, CertificateService
    from src.services.rating_service import OfficialRatingService, InternalRatingService
    from src.services.dashboard_service import DashboardService, CommunicationService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _PerfilPreparado:
    """Perfil ja validado, pronto para gravar, e o que o plano pede (RGS-08/09)."""

    torneio: dict[str, Any]
    ajustes: dict[str, Any]
    agenda: list[dict[str, Any]]
    confirmacoes: tuple[Confirmacao, ...] = ()
    agenda_perdida: list[dict[str, Any]] = dataclass_field(default_factory=list)
    mudancas_estruturais: dict[str, tuple[Any, Any]] = dataclass_field(default_factory=dict)
    liga_perigosas: bool = False
    # (antes, depois) quando o pedido escolhe o motor reserva (RGS-18).
    motor_reserva: tuple[str, str] | None = None


class RefereeService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def list_referees(self, active_only: bool = True) -> list[dict[str, Any]]:
        return self.db.list_referees(active_only)

    def create_referee(self, data: dict[str, Any]) -> int:
        if not data.get("name"):
            raise AppError("Nome do árbitro é obrigatório.")
        return self.db.insert_referee(data)

    def update_referee(self, referee_id: int, data: dict[str, Any]) -> None:
        if not data.get("name"):
            raise AppError("Nome do árbitro é obrigatório.")
        self.db.update_referee(referee_id, data)

    def toggle_referee_active(self, referee_id: int) -> None:
        referee = self.db.get_referee(referee_id)
        if not referee:
            raise AppError("Árbitro não encontrado.")
        data = dict(referee)
        data["active"] = 0 if referee["active"] else 1
        self.db.update_referee(referee_id, data)

    def list_tournament_referees(self, tournament_id: int) -> list[dict[str, Any]]:
        return self.db.list_tournament_referees(tournament_id)

    def assign_tournament_referee(self, tournament_id: int, referee_id: int, role: str) -> None:
        self.db.assign_tournament_referee(tournament_id, referee_id, role)

    def remove_tournament_referee(self, tournament_id: int, referee_id: int) -> None:
        self.db.remove_tournament_referee(tournament_id, referee_id)

class TournamentService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create_tournament(self, tournament_data: dict[str, Any]) -> int:
        payload = self._validated_tournament_payload(tournament_data, {})
        tournament_id = self.db.create_tournament(**payload)
        logger.info("Torneio criado: %s", tournament_id)
        return tournament_id

    def create_tournament_from_profile(
        self,
        tournament_data: dict[str, Any],
        settings_data: dict[str, Any],
        schedule: list[dict[str, Any]],
    ) -> int:
        tournament_payload = self._validated_tournament_payload(tournament_data, {})
        settings_payload = self._validated_settings(settings_data)
        schedule_payload = self._validated_schedule(schedule, tournament_payload["rounds_count"])
        # Torneio, ajustes e agenda entram juntos: falha no meio não deixa
        # torneio sem ajustes nem agenda (RGS-08).
        with self.db.transaction():
            tournament_id = self.db.create_tournament(**tournament_payload)
            self.db.save_tournament_settings(tournament_id, settings_payload)
            self.db.save_round_schedule(tournament_id, schedule_payload)
        logger.info("Torneio criado a partir de modelo: %s", tournament_id)
        return tournament_id

    def duplicate_tournament(self, source_tournament_id: int, new_name: str) -> int:
        source = self.db.get_tournament(source_tournament_id)
        if not source:
            raise AppError("Selecione um torneio válido para duplicar.")
        clean_name = str(new_name or "").strip()
        if not clean_name:
            raise AppError("Informe o nome do novo torneio.")
        tournament_id = self.db.duplicate_tournament(source_tournament_id, clean_name)
        logger.info("Torneio %s duplicado como %s", source_tournament_id, tournament_id)
        return tournament_id

    def list_categories(self, tournament_id: int) -> list[dict[str, Any]]:
        """Categorias cadastradas do torneio (vazio = faixas padrão)."""
        return self.db.list_tournament_categories(tournament_id)

    def replace_categories(
        self, tournament_id: int, categories: list[dict[str, Any]]
    ) -> None:
        """Regrava as categorias do torneio, normalizadas (ORG-01).

        Reprova nome repetido antes de gravar: a tabela tem `UNIQUE` e o erro
        do SQLite chegaria à tela como texto de banco. Duas linhas com o mesmo
        nome também não teriam significado — a segunda nunca seria alcançada.
        """
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio válido.")
        limpos = self._validated_categories(categories)
        self.db.replace_tournament_categories(tournament_id, limpos)
        logger.info("Categorias do torneio %s regravadas (%d)", tournament_id, len(limpos))

    @staticmethod
    def _validated_categories(categories: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Categorias normalizadas, sem gravar; recusa nome repetido (ORG-01)."""
        limpos: list[dict[str, Any]] = []
        vistos: set[str] = set()
        for posicao, item in enumerate(categories or []):
            definicao = normalize_category(category_from_row(item))
            if not definicao.is_valid:
                if str(item.get("name") or "").strip():
                    raise AppError(f"Tipo de categoria inválido em '{definicao.name}'.")
                continue
            chave = definicao.name.casefold()
            if chave in vistos:
                raise AppError(f"Categoria repetida: '{definicao.name}'.")
            vistos.add(chave)
            limpos.append(
                {
                    "name": definicao.name,
                    "kind": definicao.kind,
                    "min_value": definicao.min_value,
                    "max_value": definicao.max_value,
                    "sex": definicao.sex,
                    "tag": definicao.tag,
                    "reference_date": definicao.reference_date,
                    "awards": definicao.awards,
                    "position": posicao,
                }
            )
        return limpos

    def delete_tournament(self, tournament_id: int) -> None:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio válido para excluir.")
        self.db.delete_tournament(tournament_id)
        logger.info("Torneio excluido: %s", tournament_id)

    def save_profile(
        self,
        tournament_id: int,
        tournament_data: dict[str, Any],
        settings_data: dict[str, Any],
        schedule: list[dict[str, Any]],
        confirm_schedule_loss: bool = False,
        structural_change_reason: str = "",
    ) -> None:
        """Grava só o perfil (torneio, ajustes e agenda), numa transação.

        API antiga, sem diálogo: as confirmações vem pelos argumentos. Ligar
        "mudancas perigosas" e escolher o motor reserva (RGS-18) não tem
        argumento próprio e valem como confirmados pelo próprio pedido — a
        auditoria registra igual. A tela usa ``save_tournament_configuration``.
        """
        preparo = self._prepare_profile(
            tournament_id, PerfilTorneio(tournament_data, settings_data, schedule)
        )
        confirmadas = {TIPO_MUDANCAS_PERIGOSAS, TIPO_MOTOR_RESERVA}
        if confirm_schedule_loss:
            confirmadas.add(TIPO_AGENDA_PERDIDA)
        if str(structural_change_reason or "").strip():
            confirmadas.add(TIPO_MUDANCA_ESTRUTURAL)
        self._require_confirmations(preparo.confirmacoes, confirmadas, structural_change_reason)
        with self.db.transaction():
            self._write_profile(tournament_id, preparo, structural_change_reason)
        logger.info("Configuracoes do torneio %s atualizadas", tournament_id)

    def plan_configuration(
        self,
        tournament_id: int,
        perfil: PerfilTorneio,
        premios: list[dict[str, Any]],
        categorias: list[dict[str, Any]],
        colunas: list[Any],
    ) -> list[Confirmacao]:
        """Valida TUDO (sem gravar) e devolve as confirmações a pedir (RGS-09).

        Recusa (``AppError``) o que não tem confirmação que resolva: prêmio sem
        nome, data inválida, rodadas abaixo das já geradas. Assim o árbitro não
        confirma e digita um motivo para só depois ouvir que o prêmio é em
        branco.
        """
        preparo = self._prepare_profile(tournament_id, perfil)
        self._prepare_extras(premios, categorias, colunas)
        return list(preparo.confirmacoes)

    def save_tournament_configuration(
        self,
        tournament_id: int,
        perfil: PerfilTorneio,
        premios: list[dict[str, Any]],
        categorias: list[dict[str, Any]],
        colunas: list[Any],
        *,
        confirmadas: Sequence[str] = (),
        motivo: str = "",
    ) -> None:
        """Salva a tela de Configurações inteira, ou nada (RGS-08).

        1. Valida perfil, prêmios, categorias e colunas sem tocar no banco.
        2. Confere que o árbitro confirmou tudo o que o plano pede (RGS-09).
        3. Backup antes, e então tudo numa transação: perfil, auditoria,
           prêmios, categorias e colunas. Uma falha em qualquer gravação
           desfaz as outras; só o evento ``backup_created`` fica.
        """
        preparo = self._prepare_profile(tournament_id, perfil)
        premios_limpos, categorias_limpas, colunas_limpas = self._prepare_extras(
            premios, categorias, colunas
        )
        self._require_confirmations(preparo.confirmacoes, set(confirmadas), motivo)

        self.db.backup_before("tournament_configuration", tournament_id)
        with self.db.transaction():
            self._write_profile(tournament_id, preparo, motivo)
            self.db.replace_tournament_prizes(tournament_id, premios_limpos)
            self.db.replace_tournament_categories(tournament_id, categorias_limpas)
            self.db.save_report_layout(tournament_id, "standings", colunas_limpas)
        logger.info("Configuracoes completas do torneio %s salvas", tournament_id)

    # -- "Avançado": mudanças perigosas gravando sozinha (RGS-20) ------------ #

    def plan_dangerous_changes(self, tournament_id: int, enabled: bool) -> list[Confirmacao]:
        """Confirmacoes para ligar/desligar "mudanças perigosas" — o MESMO plano.

        A opção saiu da aba Regras e grava sozinha: o pedido e só ela, então o
        planner das Configurações devolve só a confirmação dela (ligar com
        rodada gerada). Desligar não pede nada.
        """
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio válido.")
        pedido = {"allow_dangerous_changes": 1 if enabled else 0}
        return plan_tournament_configuration(
            rodadas_geradas=max(
                (int(item["number"]) for item in self.db.list_rounds(tournament_id)), default=0
            ),
            ajustes_atuais=self.db.get_tournament_settings(tournament_id) or {},
            ajustes_pedidos=pedido,
            ajustes_validados=pedido,
            total_rodadas=int(tournament.get("rounds_count") or 0),
            agenda=[],
        )

    def save_dangerous_changes(
        self,
        tournament_id: int,
        enabled: bool,
        *,
        confirmadas: Sequence[str] = (),
        motivo: str = "",
    ) -> None:
        """Grava SÓ a opção, com backup, auditoria e as confirmações do plano.

        Gravar sozinha (RGS-08) e o ponto: no incidente, ligar a opção ia junto
        com o formulário inteiro, e a recusa de um prêmio em branco deixava a
        flag gravada pela metade. Aqui nada mais e lido nem validado.
        """
        confirmacoes = self.plan_dangerous_changes(tournament_id, enabled)
        self._require_confirmations(confirmacoes, set(confirmadas), motivo)
        atual = bool(int((self.db.get_tournament_settings(tournament_id) or {}).get("allow_dangerous_changes") or 0))
        if atual == bool(enabled):
            return
        self.db.backup_before("dangerous_changes", tournament_id)
        with self.db.transaction():
            self.db.save_tournament_settings(
                tournament_id, {"allow_dangerous_changes": 1 if enabled else 0}
            )
            self.db.create_audit_event(
                action="dangerous_changes_enabled" if enabled else "dangerous_changes_disabled",
                tournament_id=tournament_id,
                entity_type="tournament_settings",
                reason=str(motivo or "").strip(),
                before={"allow_dangerous_changes": int(atual)},
                after={"allow_dangerous_changes": 1 if enabled else 0},
            )
        logger.info(
            "Mudancas perigosas %s no torneio %s", "ligadas" if enabled else "desligadas", tournament_id
        )

    def _prepare_profile(self, tournament_id: int, perfil: PerfilTorneio) -> "_PerfilPreparado":
        """Toda a validacao do perfil, so com leituras. Nada aqui grava."""
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio válido.")
        tournament_data = dict(perfil.torneio)
        settings_data = dict(perfil.ajustes)
        schedule = [dict(item) for item in perfil.agenda]

        tournament_payload = self._validated_tournament_payload(tournament_data, tournament)
        generated_rounds = self.db.list_rounds(tournament_id)
        highest_generated_round = max((int(item["number"]) for item in generated_rounds), default=0)
        if int(tournament_payload["rounds_count"]) < highest_generated_round:
            raise AppError(
                f"O torneio já possui rodadas geradas até a rodada {highest_generated_round}. "
                "Exclua as rodadas geradas antes de reduzir o total."
            )
        self._validate_competition_type_change(
            tournament_id,
            tournament,
            tournament_payload,
            generated_rounds,
        )
        current_settings = self.db.get_tournament_settings(tournament_id) or {}
        settings_for_validation = {**current_settings, **settings_data}
        # Data gravada que a tela não envia (ex.: prazo de escalação, sem campo
        # na tela) e inválida desde antes da regra única não pode travar todo
        # salvamento: fica como esta e aparece em "Datas a revisar" (RGS-06).
        settings_payload = self._validated_settings(
            settings_for_validation,
            untouched_dates=frozenset(
                campo for campo in self.SETTINGS_DATE_FIELDS if campo not in settings_data
            ),
        )
        # A perda de agenda não é mais recusa aqui: vira confirmação do plano.
        schedule_payload = self._validated_schedule(
            schedule,
            tournament_payload["rounds_count"],
            confirm_schedule_loss=True,
        )
        self._validate_team_settings_compatibility(tournament_id, tournament_payload, settings_payload)
        # MA-02: o modo amistoso não convive com o perfil FIDE-rated.
        conflito = friendly_mode.profile_conflict(
            friendly_mode.is_friendly(current_settings), settings_payload.get("tournament_profile", "")
        )
        if conflito:
            raise AppError(conflito)

        requested_method = str(settings_payload.get("pairing_method") or "").strip()
        if (
            requested_method
            and requested_method != str(current_settings.get("pairing_method", "swiss"))
            and generated_rounds
        ):
            raise AppError(
                "Não é possível mudar o método de pareamento depois de gerar a primeira rodada."
            )
        self._validate_initial_color_change(tournament_id, current_settings, settings_data, generated_rounds)

        confirmacoes = plan_tournament_configuration(
            rodadas_geradas=highest_generated_round,
            ajustes_atuais=current_settings,
            ajustes_pedidos=settings_data,
            ajustes_validados=settings_payload,
            total_rodadas=int(tournament_payload["rounds_count"]),
            agenda=schedule,
        )
        return _PerfilPreparado(
            torneio=tournament_payload,
            ajustes=settings_payload,
            agenda=schedule_payload,
            confirmacoes=tuple(confirmacoes),
            agenda_perdida=agenda_perdida(schedule, int(tournament_payload["rounds_count"])),
            mudancas_estruturais=(
                mudancas_estruturais(current_settings, settings_data, settings_payload)
                if generated_rounds
                else {}
            ),
            liga_perigosas=bool(generated_rounds)
            and liga_mudancas_perigosas(current_settings, settings_data, settings_payload),
            motor_reserva=escolhe_motor_reserva(current_settings, settings_data, settings_payload),
        )

    def _validate_initial_color_change(
        self,
        tournament_id: int,
        current_settings: dict[str, Any],
        settings_data: dict[str, Any],
        generated_rounds: list[dict[str, Any]],
    ) -> None:
        """A cor inicial vale até a R1 (RGS-14): depois dela, já é fato do tabuleiro.

        A comparação e com a cor EFETIVA, não só a gravada: torneio anterior a
        v57 tem a coluna vazia e a cor lida da R1, e a tela reenvia essa cor.
        """
        pedida = normalize_initial_color(settings_data.get("initial_color"))
        if not pedida or not generated_rounds:
            return
        if pedida != resolve_initial_color(self.db, tournament_id, current_settings):
            raise AppError(
                "A cor inicial não pode mudar depois de gerar a primeira rodada: "
                "ela já foi usada no tabuleiro 1 da rodada 1."
            )

    def _prepare_extras(
        self,
        premios: list[dict[str, Any]],
        categorias: list[dict[str, Any]],
        colunas: list[Any],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        return (
            validated_prizes(premios),
            self._validated_categories(categorias),
            validated_columns(colunas, "standings"),
        )

    @staticmethod
    def _require_confirmations(
        confirmacoes: Sequence[Confirmacao], confirmadas: set[str], motivo: str
    ) -> None:
        pendentes = confirmacoes_pendentes(confirmacoes, confirmadas, motivo)
        if pendentes:
            raise AppError("\n\n".join(item.mensagem for item in pendentes))

    def _write_profile(self, tournament_id: int, preparo: "_PerfilPreparado", motivo: str) -> None:
        """Grava o perfil e a auditoria dele. Chamar DENTRO de uma transação.

        A auditoria vem depois de todas as validações (RGS-09): antes, o evento
        de agenda era gravado e só então vinha a recusa por falta de motivo.
        """
        self.db.update_tournament_details(tournament_id=tournament_id, **preparo.torneio)
        self.db.save_tournament_settings(tournament_id, preparo.ajustes)
        self.db.save_round_schedule(tournament_id, preparo.agenda)

        if preparo.agenda_perdida:
            # O evento existe para que "a data da rodada 5 sumiu" tenha resposta depois.
            self.db.create_audit_event(
                action="schedule_rounds_reduced",
                tournament_id=tournament_id,
                entity_type="round_schedule",
                reason=f"Total de rodadas reduzido para {preparo.torneio['rounds_count']}",
                before=preparo.agenda_perdida,
            )
        if preparo.mudancas_estruturais:
            self.db.create_audit_event(
                action="tournament_structural_change",
                tournament_id=tournament_id,
                entity_type="tournament_settings",
                reason=str(motivo or "").strip(),
                before={campo: antes for campo, (antes, _d) in preparo.mudancas_estruturais.items()},
                after={campo: depois for campo, (_a, depois) in preparo.mudancas_estruturais.items()},
            )
        if preparo.liga_perigosas:
            # Foi a rota do incidente (ESPEC §1.2): quem ligou e quando passa a
            # ter resposta.
            self.db.create_audit_event(
                action="dangerous_changes_enabled",
                tournament_id=tournament_id,
                entity_type="tournament_settings",
                reason=str(motivo or "").strip(),
                before={"allow_dangerous_changes": 0},
                after={"allow_dangerous_changes": 1},
            )
        if preparo.motor_reserva:
            antes, depois = preparo.motor_reserva
            self.db.create_audit_event(
                action="reserve_engine_selected",
                tournament_id=tournament_id,
                entity_type="tournament_settings",
                reason=str(motivo or "").strip() or f"Escolhido o {RESERVE_ENGINE_LABEL}.",
                before={"pairing_system": antes},
                after={"pairing_system": depois},
            )

    def change_tournament_type(self, tournament_id: int, pairing_method: str) -> None:
        """Muda o metodo de pareamento (RR <-> Suico <-> ...), bloqueado apos a R1."""
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio válido.")
        method = str(pairing_method or "").strip()
        if method not in PAIRING_METHODS:
            raise AppError("Método de pareamento inválido.")
        if self.db.list_rounds(tournament_id):
            raise AppError(
                "Não é possível mudar o método de pareamento depois de gerar a primeira rodada."
            )
        self.db.update_pairing_method(tournament_id, method)
        logger.info("Torneio %s teve o pareamento alterado para %s", tournament_id, method)

    def split_tournament(self, tournament_id: int, group_count: int) -> list[int]:
        """Divide os jogadores em N torneios-filho por ranking inicial (A=mais forte)."""
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio válido.")
        if tournament.get("competition_type") == "team":
            raise AppError("A divisão está disponível apenas para torneios individuais.")
        try:
            groups = int(group_count)
        except (TypeError, ValueError) as exc:
            raise AppError("Quantidade de grupos inválida.") from exc
        if groups < 2:
            raise AppError("Divida em pelo menos 2 grupos.")
        if self.db.list_rounds(tournament_id):
            raise AppError("Divida o torneio antes de gerar a primeira rodada.")

        players = self.db.list_players(tournament_id, active_only=False)
        if len(players) < groups:
            raise AppError("Jogadores insuficientes para a quantidade de grupos.")

        source_settings = self.db.get_tournament_settings(tournament_id) or {}
        # Mesma ordem inicial do TRF e do pareamento (RGS-13): rating, título, nome.
        ordered = seeding_order(players, source_settings)
        source_schedule = self.db.list_round_schedule(tournament_id)
        source_prizes = self.db.list_tournament_prizes(tournament_id)
        source_standings_layout = self.db.get_report_layout_columns(tournament_id, "standings")
        base_size, remainder = divmod(len(ordered), groups)

        child_ids: list[int] = []
        index = 0
        for group_index in range(groups):
            size = base_size + (1 if group_index < remainder else 0)
            chunk = ordered[index:index + size]
            index += size
            label = chr(ord("A") + group_index)
            child_id = self.db.create_tournament(
                name=f"{tournament['name']} - {label}",
                club_id=tournament.get("club_id"),
                location=str(tournament.get("location") or ""),
                rounds_count=int(tournament.get("rounds_count") or 5),
                time_control=str(tournament.get("time_control") or ""),
                start_date=str(tournament.get("start_date") or ""),
                end_date=str(tournament.get("end_date") or ""),
                bye_points=float(tournament.get("bye_points") or 1.0),
                class_id=tournament.get("class_id"),
                competition_type="individual",
            )
            self.db.set_tournament_parent(child_id, tournament_id)
            self.db.save_tournament_settings(child_id, source_settings)
            self.db.save_round_schedule(child_id, source_schedule)
            if source_prizes:
                self.db.replace_tournament_prizes(child_id, source_prizes)
            if source_standings_layout:
                self.db.save_report_layout(child_id, "standings", source_standings_layout)
            for player in chunk:
                self.db.create_player(
                    tournament_id=child_id,
                    name=str(player.get("name") or ""),
                    surname=str(player.get("surname") or ""),
                    given_name=str(player.get("given_name") or ""),
                    title=str(player.get("title") or ""),
                    sex=str(player.get("sex") or ""),
                    club=str(player.get("club") or ""),
                    rating=int(player.get("rating") or 0),
                    national_rating=int(player.get("national_rating") or 0),
                    international_rating=int(player.get("international_rating") or 0),
                    category=str(player.get("category") or ""),
                    federation_id=str(player.get("federation_id") or ""),
                    fide_id=str(player.get("fide_id") or ""),
                    cbx_id=str(player.get("cbx_id") or ""),
                    lbx_id=str(player.get("lbx_id") or ""),
                    birth_date=str(player.get("birth_date") or ""),
                    member_id=player.get("member_id"),
                    player_status=str(player.get("player_status") or "active"),
                    starting_points=float(player.get("starting_points") or 0.0),
                )
            child_ids.append(child_id)

        logger.info("Torneio %s dividido em %s grupos: %s", tournament_id, groups, child_ids)
        return child_ids

    def _validate_competition_type_change(
        self,
        tournament_id: int,
        tournament: dict[str, Any],
        tournament_payload: dict[str, Any],
        generated_rounds: list[dict[str, Any]],
    ) -> None:
        current_type = str(tournament.get("competition_type") or "individual")
        requested_type = str(tournament_payload.get("competition_type") or current_type)
        if requested_type == current_type:
            return
        if generated_rounds:
            raise AppError("Não é possível mudar o formato do torneio depois de gerar rodadas.")
        if current_type == "team" and self.db.list_teams(tournament_id, active_only=False):
            raise AppError("Não é possível mudar o formato do torneio enquanto houver equipes cadastradas.")

    def _validate_team_settings_compatibility(
        self,
        tournament_id: int,
        tournament_payload: dict[str, Any],
        settings_payload: dict[str, Any],
    ) -> None:
        if tournament_payload.get("competition_type") != "team":
            return
        boards_count = int(settings_payload.get("team_boards_count") or 4)
        highest_board = 0
        for team in self.db.list_teams(tournament_id, active_only=False):
            for assignment in self.db.list_team_players(int(team["id"]), active_only=False):
                if assignment.get("board_number"):
                    highest_board = max(highest_board, int(assignment["board_number"]))
        if highest_board > boards_count:
            raise AppError(
                f"Já existe jogador escalado no tabuleiro {highest_board}. "
                f"Aumente ou mantenha a quantidade de tabuleiros por equipe."
            )

    def _validated_tournament_payload(
        self,
        data: dict[str, Any],
        tournament: dict[str, Any],
    ) -> dict[str, Any]:
        name = str(data.get("name", "")).strip()
        if not name:
            raise AppError("Informe o nome do torneio.")

        try:
            rounds_count = int(data.get("rounds_count") or 1)
        except ValueError as exc:
            raise AppError("Número de rodadas inválido.") from exc
        if rounds_count < 1:
            raise AppError("O torneio precisa ter pelo menos uma rodada.")

        try:
            bye_points = float(str(data.get("bye_points") or "0").replace(",", "."))
        except ValueError as exc:
            raise AppError("Pontuação do bye inválida.") from exc
        if bye_points < 0:
            raise AppError("Pontuação do bye não pode ser negativa.")

        start_date = self._normalize_optional_date(data.get("start_date", ""), "Data inicial inválida.")
        end_date = self._normalize_optional_date(data.get("end_date", ""), "Data final inválida.")
        if start_date and end_date and start_date > end_date:
            raise AppError("Data final não pode ser anterior a data inicial.")

        competition_type = str(
            data.get("competition_type") or tournament.get("competition_type") or "individual"
        ).strip() or "individual"
        if competition_type not in COMPETITION_TYPES:
            raise AppError("Formato do torneio inválido.")

        _scope, club_id, class_id = self._validated_tournament_scope(data, tournament)
        return {
            "name": name,
            "club_id": club_id,
            "class_id": class_id,
            "competition_type": competition_type,
            "location": str(data.get("location", "")),
            "rounds_count": rounds_count,
            "time_control": str(data.get("time_control", "")),
            "start_date": start_date,
            "end_date": end_date,
            "bye_points": bye_points,
        }

    def _validated_tournament_scope(
        self,
        data: dict[str, Any],
        tournament: dict[str, Any],
    ) -> tuple[str, int | None, int | None]:
        scope = str(data.get("scope") or "").strip()
        if not scope:
            if data.get("class_id") or tournament.get("class_id"):
                scope = "class"
            elif "club_id" in data:
                scope = "club" if data.get("club_id") else "standalone"
            elif tournament.get("club_id"):
                scope = "club"
            else:
                scope = "standalone"
        if scope not in TOURNAMENT_SCOPES:
            raise AppError("Escopo do torneio inválido.")

        if scope == "standalone":
            return scope, None, None

        class_id: int | None = None
        class_data: dict[str, Any] | None = None
        try:
            if scope == "class":
                class_id = int(data.get("class_id") or tournament.get("class_id") or 0)
        except ValueError as exc:
            raise AppError("Turma do torneio inválida.") from exc
        if scope == "class":
            class_data = self.db.get_class(class_id or 0)
            if not class_data:
                raise AppError("Turma do torneio não encontrada.")

        if data.get("club_id"):
            club_source = data.get("club_id")
        elif class_data:
            club_source = class_data["club_id"]
        else:
            club_source = tournament.get("club_id")
        try:
            club_id = int(club_source or 0)
        except ValueError as exc:
            raise AppError("Clube/escola do torneio inválido.") from exc
        if not club_id or not self.db.get_club(club_id):
            raise AppError("Clube/escola do torneio não encontrado.")

        if scope == "club":
            return scope, club_id, None

        if class_data and int(class_data["club_id"]) != club_id:
            raise AppError("A turma selecionada não pertence ao clube/escola do torneio.")
        return scope, club_id, class_id

    # Campos de data das configurações (RGS-07) -> (mensagem, aceita só o ano).
    SETTINGS_DATE_FIELDS: dict[str, tuple[str, bool]] = {
        "cutoff_date": ("Data de corte inválida.", False),
        "team_lineup_deadline": ("Prazo de escalação inválido.", False),
        "category_reference_date": ("Data de referência da idade inválida.", True),
    }

    def _settings_date(self, data: dict[str, Any], campo: str, untouched_dates: frozenset[str]) -> str:
        mensagem, permite_ano = self.SETTINGS_DATE_FIELDS[campo]
        try:
            return self._normalize_optional_date(data.get(campo, ""), mensagem, permite_ano=permite_ano)
        except AppError:
            if campo in untouched_dates:
                return str(data.get(campo) or "")
            raise

    def _validated_settings(
        self, data: dict[str, Any], *, untouched_dates: frozenset[str] = frozenset()
    ) -> dict[str, Any]:
        initial_order = str(data.get("initial_order", "rating")).strip() or "rating"
        if initial_order not in INITIAL_ORDER_OPTIONS:
            raise AppError("Ordem inicial inválida.")

        tournament_type = str(data.get("tournament_type", "real")).strip() or "real"
        if tournament_type not in TOURNAMENT_TYPES:
            raise AppError("Tipo de torneio inválido.")

        tournament_profile = str(data.get("tournament_profile", "free")).strip() or "free"
        if tournament_profile not in TOURNAMENT_PROFILES:
            raise AppError("Perfil do torneio inválido.")

        pairing_system = str(data.get("pairing_system", default_pairing_system())).strip() or default_pairing_system()
        if pairing_system not in PAIRING_SYSTEMS:
            raise AppError("Sistema de emparceiramento normativo inválido.")

        initial_color = str(data.get("initial_color") or "").strip().upper()
        if initial_color not in ("", "W", "B"):
            raise AppError("Cor inicial inválida: use brancas ou pretas.")

        pairing_method = None
        if "pairing_method" in data:
            pairing_method = str(data.get("pairing_method") or "swiss").strip() or "swiss"
            if pairing_method not in PAIRING_METHODS:
                raise AppError("Método de pareamento inválido.")

        acceleration_method = str(data.get("acceleration_method", "none")).strip() or "none"
        acceleration_head = acceleration_method.partition(":")[0]
        if acceleration_head not in ACCELERATION_METHODS:
            raise AppError("Método de aceleração inválido.")
        if acceleration_head == "custom":
            spec = acceleration_spec(acceleration_method)
            if (
                spec.get("scheme") != "custom"
                or int(spec.get("round_count") or 0) < 1
                or float(spec.get("bonus") or 0.0) <= 0.0
                or not 0.0 < float(spec.get("upper_fraction") or 0.0) <= 1.0
            ):
                raise AppError("Método de aceleração inválido.")

        try:
            late_entry_points = float(str(data.get("late_entry_points") or "0").replace(",", "."))
        except ValueError as exc:
            raise AppError("Pontos por adesão tardia inválidos.") from exc
        try:
            team_boards_count = int(data.get("team_boards_count") or 4)
        except ValueError as exc:
            raise AppError("Quantidade de tabuleiros por equipe inválida.") from exc
        if team_boards_count < 1:
            raise AppError("Use pelo menos um tabuleiro por equipe.")

        try:
            team_rating_tolerance = int(data.get("team_rating_tolerance") or 0)
        except ValueError as exc:
            raise AppError("Tolerância de rating por equipe inválida.") from exc
        if team_rating_tolerance < 0:
            raise AppError("Tolerância de rating por equipe não pode ser negativa.")

        try:
            team_max_substitutions = int(data.get("team_max_substitutions") or 0)
        except ValueError as exc:
            raise AppError("Limite de substituições por equipe inválido.") from exc
        if team_max_substitutions < 0:
            team_max_substitutions = 0

        team_point_fields = {
            "team_match_win_points": "Pontos por vitória da equipe inválidos.",
            "team_match_draw_points": "Pontos por empate da equipe inválidos.",
            "team_match_loss_points": "Pontos por derrota da equipe inválidos.",
        }
        team_point_defaults = {
            "team_match_win_points": "2",
            "team_match_draw_points": "1",
            "team_match_loss_points": "0",
        }
        team_points: dict[str, float] = {}
        for field, message in team_point_fields.items():
            raw_value = data.get(field)
            if raw_value in (None, ""):
                raw_value = team_point_defaults[field]
            try:
                value = float(str(raw_value).replace(",", "."))
            except ValueError as exc:
                raise AppError(message) from exc
            if value < 0:
                raise AppError(message)
            team_points[field] = value

        rating_fees: dict[str, float] = {}
        for field, label in (
            ("rating_fee_fide", "FIDE"),
            ("rating_fee_cbx", "CBX"),
            ("rating_fee_lbx", "LBX"),
        ):
            try:
                value = float(str(data.get(field) or "0").replace(",", "."))
            except ValueError as exc:
                raise AppError(f"Taxa de rating {label} inválida.") from exc
            if value < 0:
                raise AppError(f"Taxa de rating {label} não pode ser negativa.")
            rating_fees[field] = value

        team_pairing_method = str(data.get("team_pairing_method", "swiss")).strip() or "swiss"
        if team_pairing_method not in TEAM_PAIRING_METHODS:
            raise AppError("Método de emparceiramento por equipes inválido.")
        team_standing_primary = str(data.get("team_standing_primary", "match_points")).strip() or "match_points"
        team_standing_secondary = str(data.get("team_standing_secondary", "game_points")).strip() or "game_points"
        if team_standing_primary not in TEAM_STANDING_CRITERIA:
            raise AppError("Critério principal por equipes inválido.")
        if team_standing_secondary not in TEAM_STANDING_CRITERIA:
            raise AppError("Critério secundário por equipes inválido.")
        if team_standing_primary == team_standing_secondary:
            raise AppError("Use critérios diferentes para classificação por equipes.")

        tiebreak_sequence = serialize_tiebreak_sequence(
            parse_player_tiebreak_sequence(data.get("tiebreak_sequence"))
        )
        team_tiebreak_sequence = serialize_tiebreak_sequence(
            parse_team_tiebreak_sequence(data.get("team_tiebreak_sequence"))
        )

        rating_speed = str(data.get("rating_speed", "")).strip().lower()
        if rating_speed not in SPEED_CHOICES:
            raise AppError("Ritmo para rating inválido.")
        rating_regulation = serialize_regulation_overrides(data.get("rating_regulation"))

        prize_tie_split = str(data.get("prize_tie_split", "equal")).strip() or "equal"
        if prize_tie_split not in PRIZE_TIE_SPLITS:
            raise AppError("Forma de rateio entre empatados inválida.")
        try:
            late_tolerance_minutes = int(data.get("late_tolerance_minutes") or 0)
        except (TypeError, ValueError) as exc:
            raise AppError("Tolerância de atraso inválida.") from exc
        if late_tolerance_minutes < 0:
            raise AppError("Tolerância de atraso não pode ser negativa.")

        prize_policy = str(data.get("prize_policy", "best_only")).strip() or "best_only"
        if prize_policy not in PRIZE_POLICIES:
            raise AppError("Política de premiação inválida.")
        try:
            prize_tax_percent = float(str(data.get("prize_tax_percent") or "0").replace(",", "."))
        except ValueError as exc:
            raise AppError("Imposto de premiação inválido.") from exc
        if not 0.0 <= prize_tax_percent <= 100.0:
            raise AppError("Imposto de premiação deve estar entre 0 e 100%.")

        payload = {
            "fide_event_id": str(data.get("fide_event_id", "")),
            "organizer": str(data.get("organizer", "")),
            "website": str(data.get("website", "")),
            "contact_email": str(data.get("contact_email", "")),
            "director": str(data.get("director", "")),
            "chief_arbiter": str(data.get("chief_arbiter", "")),
            "arbiters": str(data.get("arbiters", "")),
            "federation": str(data.get("federation", "")),
            "state": str(data.get("state", "")),
            "categories": str(data.get("categories", "")),
            "cutoff_date": self._settings_date(data, "cutoff_date", untouched_dates),
            "comments": str(data.get("comments", "")),
            "prizes": str(data.get("prizes", "")),
            "initial_order": initial_order,
            "tournament_type": tournament_type,
            "tournament_profile": tournament_profile,
            "pairing_system": pairing_system,
            "acceleration_method": acceleration_method,
            "late_entry_points": late_entry_points,
            "team_boards_count": team_boards_count,
            "team_match_win_points": team_points["team_match_win_points"],
            "team_match_draw_points": team_points["team_match_draw_points"],
            "team_match_loss_points": team_points["team_match_loss_points"],
            "team_pairing_method": team_pairing_method,
            "team_standing_primary": team_standing_primary,
            "team_standing_secondary": team_standing_secondary,
            "tiebreak_sequence": tiebreak_sequence,
            "team_tiebreak_sequence": team_tiebreak_sequence,
            "prize_policy": prize_policy,
            "prize_tax_percent": prize_tax_percent,
            "team_fixed_board_order": 1 if data.get("team_fixed_board_order", 1) else 0,
            "team_board_order_policy": str(data.get("team_board_order_policy", "fixed")).strip() or "fixed",
            "team_reserve_policy": str(data.get("team_reserve_policy", "same_team")).strip() or "same_team",
            "team_lineup_deadline": self._settings_date(data, "team_lineup_deadline", untouched_dates),
            "team_rating_tolerance": team_rating_tolerance,
            "team_max_substitutions": team_max_substitutions,
            "rating_speed": rating_speed,
            "rating_regulation": rating_regulation,
            "prize_tie_split": prize_tie_split,
            "late_tolerance_minutes": late_tolerance_minutes,
            **rating_fees,
        }
        if pairing_method is not None:
            payload["pairing_method"] = pairing_method
        if initial_color:
            # Sem cor no pedido, fica a gravada (o sorteio da criação, RGS-14).
            payload["initial_color"] = initial_color
        if "category_reference_date" in data:
            # Data ou só o ano (RGS-07). Antes ficava fora do payload: o campo
            # da tela era lido e descartado, e o banco guardava o valor antigo.
            payload["category_reference_date"] = self._settings_date(
                data, "category_reference_date", untouched_dates
            )
        for field in TOURNAMENT_FLAG_FIELDS:
            payload[field] = 1 if data.get(field) else 0
        return payload

    @staticmethod
    def _validate_optional_date(value: str, message: str) -> None:
        TournamentService._normalize_optional_date(value, message)

    @staticmethod
    def _normalize_optional_date(value: Any, message: str, *, permite_ano: bool = False) -> str:
        """Data opcional pela regra unica (RGS-07): ISO, o ano, ou vazio."""
        try:
            return normalize_date(value, permite_ano=permite_ano)
        except DateError as exc:
            raise AppError(message) from exc

    # Configurações que mudam o SIGNIFICADO do torneio (ORG-04). A lista mora
    # no plano (RGS-09), que é quem decide o que pede motivo.
    STRUCTURAL_SETTINGS = STRUCTURAL_SETTINGS

    @staticmethod
    def _validated_schedule(
        schedule: list[dict[str, Any]],
        rounds_count: int,
        *,
        confirm_schedule_loss: bool = False,
    ) -> list[dict[str, Any]]:
        rows = []
        seen: set[int] = set()
        dropped: list[int] = []
        for item in schedule:
            try:
                round_number = int(item.get("round_number") or 0)
            except ValueError as exc:
                raise AppError("Número de rodada inválido na agenda.") from exc
            if round_number < 1:
                raise AppError("Agenda contem rodada fora do total configurado.")
            if round_number > rounds_count:
                # ORG-03: descartar em silêncio apagava data já publicada. Quem
                # reduz rodadas com agenda preenchida tem de saber o que perde.
                if str(item.get("date", "")).strip() or str(item.get("time", "")).strip():
                    dropped.append(round_number)
                continue
            if round_number in seen:
                raise AppError("Agenda contem rodada repetida.")
            # A agenda aceita o mesmo que as datas do torneio e grava ISO (RGS-07):
            # antes, `13/11/2026` valia no cabeçalho e era recusado aqui.
            round_date = TournamentService._normalize_optional_date(
                item.get("date", ""), f"Data inválida na agenda de rodadas (rodada {round_number})."
            )
            seen.add(round_number)
            rows.append(
                {
                    "round_number": round_number,
                    "date": round_date,
                    "time": str(item.get("time", "")).strip(),
                    "venue": str(item.get("venue", "")).strip(),
                    "time_control": str(item.get("time_control", "")).strip(),
                    "rest_day": 1 if item.get("rest_day") else 0,
                }
            )

        for round_number in range(1, rounds_count + 1):
            if round_number not in seen:
                rows.append(
                    {
                        "round_number": round_number,
                        "date": "",
                        "time": "",
                        "venue": "",
                        "time_control": "",
                        "rest_day": 0,
                    }
                )

        if dropped and not confirm_schedule_loss:
            # ORG-03: confirmação, não descarte calado. Quem reduziu o total de
            # rodadas esta prestes a perder datas que já podem ter sido
            # publicadas — e o programa apagava sem dizer nada.
            perdidas = ", ".join(str(numero) for numero in sorted(dropped))
            raise AppError(
                f"A agenda tem data marcada para a(s) rodada(s) {perdidas}, acima do total "
                f"configurado ({rounds_count}). Confirme para apagar essas datas, aumente o "
                "total de rodadas ou limpe a agenda dessas rodadas."
            )

        return sorted(rows, key=lambda item: item["round_number"])

    @staticmethod
    def generate_round_schedule(
        rounds_count: Any,
        start_date: Any,
        first_time: Any,
        round_duration_minutes: Any,
        break_minutes: Any,
        rounds_per_day: Any,
    ) -> list[dict[str, Any]]:
        try:
            total_rounds = int(rounds_count)
        except (TypeError, ValueError) as exc:
            raise AppError("Número de rodadas inválido para gerar agenda.") from exc
        if total_rounds < 1:
            raise AppError("O torneio precisa ter pelo menos uma rodada para gerar agenda.")

        start_date_text = TournamentService._normalize_optional_date(
            start_date,
            "Data inicial da agenda inválida.",
        )
        if not start_date_text:
            raise AppError("Informe a data inicial da agenda.")
        inicio = parse_date(start_date_text)
        if not isinstance(inicio, Data):
            raise AppError("Data inicial da agenda inválida.")
        start_day = inicio.valor

        try:
            start_time = time.fromisoformat(str(first_time or "").strip())
        except ValueError as exc:
            raise AppError("Hora inicial da agenda inválida. Use HH:MM.") from exc

        try:
            duration_minutes = int(round_duration_minutes)
        except (TypeError, ValueError) as exc:
            raise AppError("Duração da rodada inválida.") from exc
        if duration_minutes < 1:
            raise AppError("Duração da rodada deve ser maior que zero.")

        try:
            interval_minutes = int(break_minutes)
        except (TypeError, ValueError) as exc:
            raise AppError("Intervalo entre rodadas inválido.") from exc
        if interval_minutes < 0:
            raise AppError("Intervalo entre rodadas não pode ser negativo.")

        try:
            per_day = int(rounds_per_day)
        except (TypeError, ValueError) as exc:
            raise AppError("Rodadas por dia inválidas.") from exc
        if per_day < 1 or per_day > total_rounds:
            per_day = total_rounds

        step = timedelta(minutes=duration_minutes + interval_minutes)
        rows = []
        for index in range(total_rounds):
            day_offset = index // per_day
            slot = index % per_day
            day_start = datetime.combine(start_day + timedelta(days=day_offset), start_time)
            scheduled_at = day_start + (step * slot)
            rows.append(
                {
                    "round_number": index + 1,
                    "date": scheduled_at.date().isoformat(),
                    "time": scheduled_at.strftime("%H:%M"),
                }
            )
        return rows

class TeamService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create_team(self, tournament_id: int, data: dict[str, Any]) -> int:
        self._require_team_tournament(tournament_id)
        payload = self._validated_team_payload(data)
        try:
            team_id = self.db.create_team(tournament_id, **payload)
        except sqlite3.IntegrityError as exc:
            raise AppError("Já existe uma equipe com este nome no torneio.") from exc
        logger.info("Equipe criada no torneio %s: %s", tournament_id, team_id)
        return team_id

    def update_team(self, team_id: int, data: dict[str, Any]) -> None:
        team = self.db.get_team(team_id)
        if not team:
            raise AppError("Equipe não encontrada.")
        self._require_team_tournament(int(team["tournament_id"]))
        payload = self._validated_team_payload(data)
        try:
            self.db.update_team(team_id, **payload)
        except sqlite3.IntegrityError as exc:
            raise AppError("Já existe uma equipe com este nome no torneio.") from exc
        logger.info("Equipe atualizada: %s", team_id)

    def add_player(
        self,
        team_id: int,
        player_id: int,
        board_number: Any = None,
        role: str = "starter",
    ) -> int:
        team = self.db.get_team(team_id)
        if not team:
            raise AppError("Equipe não encontrada.")
        self._require_team_tournament(int(team["tournament_id"]))

        player = self.db.get_player(player_id)
        if not player or int(player["tournament_id"]) != int(team["tournament_id"]):
            raise AppError("Jogador não pertence ao torneio da equipe.")

        existing = self.db.get_team_player_by_player(player_id)
        if existing:
            raise AppError(f"Jogador já está na equipe {existing['team_name']}.")

        payload = self._validated_assignment_payload(
            int(team["tournament_id"]),
            board_number,
            role,
        )
        self._ensure_board_available(team_id, payload["board_number"])
        try:
            team_player_id = self.db.add_player_to_team(team_id, player_id, **payload)
        except sqlite3.IntegrityError as exc:
            raise AppError("Jogador ou tabuleiro já cadastrado em uma equipe.") from exc
        logger.info("Jogador %s adicionado a equipe %s", player_id, team_id)
        return team_player_id

    def update_player_assignment(
        self,
        team_player_id: int,
        board_number: Any = None,
        role: str = "starter",
    ) -> None:
        assignment = self.db.get_team_player(team_player_id)
        if not assignment:
            raise AppError("Jogador da equipe não encontrado.")
        self._require_team_tournament(int(assignment["tournament_id"]))
        payload = self._validated_assignment_payload(
            int(assignment["tournament_id"]),
            board_number,
            role,
        )
        self._ensure_board_available(
            int(assignment["team_id"]),
            payload["board_number"],
            ignore_team_player_id=team_player_id,
        )
        try:
            self.db.update_team_player(team_player_id, **payload)
        except sqlite3.IntegrityError as exc:
            raise AppError("Tabuleiro já ocupado nesta equipe.") from exc
        logger.info("Escalacao da equipe atualizada: %s", team_player_id)

    def remove_player(self, team_player_id: int) -> None:
        if not self.db.get_team_player(team_player_id):
            raise AppError("Jogador da equipe não encontrado.")
        self.db.remove_player_from_team(team_player_id)
        logger.info("Jogador removido da equipe: %s", team_player_id)

    def swap_pairing_numbers(self, team_a_id: int, team_b_id: int, *, reason: str = "") -> None:
        """Corrige o TPN trocando o número de duas equipes (EQ-01.5).

        O TPN não muda depois de definido, salvo decisão do árbitro-chefe
        (C.04.6, art. 1.1.3) — por isso o motivo é obrigatório e a troca fica
        na auditoria (`team_pairing_number_corrected`). Trocar, e não digitar um
        número, mantém a numeração de 1 a N sem buraco nem repetição.

        Só entre rodadas: a rodada aberta foi pareada com os números atuais, e
        corrigir no meio dela deixaria o gravado diferente do que o motor usou.
        No todos-contra-todos o calendário saiu dos TPN da R1: trocar depois
        repetiria confrontos.
        """
        motivo = " ".join(str(reason or "").split())
        erro_motivo = tpn_correction_reason_error(motivo)
        if erro_motivo:
            raise AppError(erro_motivo)
        if int(team_a_id) == int(team_b_id):
            raise AppError("Escolha duas equipes diferentes para trocar o TPN.")
        team_a = self.db.get_team(team_a_id)
        team_b = self.db.get_team(team_b_id)
        if not team_a or not team_b or int(team_a["tournament_id"]) != int(team_b["tournament_id"]):
            raise AppError("Equipe não encontrada no torneio.")
        tournament_id = int(team_a["tournament_id"])
        self._require_team_tournament(tournament_id)
        if not team_a.get("pairing_number") or not team_b.get("pairing_number"):
            raise AppError(
                "O TPN é atribuído na geração da 1ª rodada; antes dela, a ordem "
                "segue a semente e não há número a corrigir."
            )
        latest_round = self.db.get_latest_round(tournament_id)
        if latest_round and latest_round["status"] != "closed":
            raise AppError(
                f"Feche a rodada {latest_round['number']} antes de corrigir o TPN: "
                "ela foi pareada com os números atuais."
            )
        settings = self.db.get_tournament_settings(tournament_id) or {}
        if str(settings.get("team_pairing_method") or "swiss") == "round_robin":
            raise AppError(
                "No todos-contra-todos por equipes o calendário saiu dos TPN da 1ª "
                "rodada: trocar os números agora repetiria confrontos."
            )

        antes = {
            int(team_a["id"]): int(team_a["pairing_number"]),
            int(team_b["id"]): int(team_b["pairing_number"]),
        }
        with self.db.transaction():
            self.db.swap_team_pairing_numbers(int(team_a["id"]), int(team_b["id"]))
            self.db.create_audit_event(
                action="team_pairing_number_corrected",
                tournament_id=tournament_id,
                entity_type="team",
                entity_id=int(team_a["id"]),
                reason=motivo,
                before={"pairing_numbers": {str(k): v for k, v in antes.items()}},
                after={
                    "pairing_numbers": {
                        str(int(team_a["id"])): antes[int(team_b["id"])],
                        str(int(team_b["id"])): antes[int(team_a["id"])],
                    }
                },
                metadata={
                    "after_round": int(latest_round["number"]) if latest_round else 0,
                    "rule": "FIDE C.04.6 1.1.3",
                },
            )
        logger.info("TPN trocado entre as equipes %s e %s", team_a["id"], team_b["id"])

    def delete_team(self, team_id: int) -> None:
        team = self.db.get_team(team_id)
        if not team:
            raise AppError("Equipe não encontrada.")
        if self.db.count_team_matches(team_id) > 0:
            raise AppError(
                "Equipe já apareceu em rodadas. Para preservar o histórico, desmarque Ativa e atualize a equipe."
            )
        self.db.delete_team(team_id)
        logger.info("Equipe excluida: %s", team_id)

    def validate_roster_policy(
        self,
        tournament_id: int,
        round_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Avalia escalações e substituições contra a policy do torneio (spec §6.2).

        Retorna lista de avisos não-bloqueantes:
          - board_order_broken: tabuleiro com rating maior que o anterior
            (respeitando team_rating_tolerance)
          - substitution_limit_exceeded: equipe ultrapassou team_max_substitutions

        Quando round_id é dado, filtra avisos para aquela rodada.
        """
        issues: list[dict[str, Any]] = []
        settings = self.db.get_tournament_settings(tournament_id) or {}
        enforce_order = bool(int(settings.get("team_fixed_board_order", 1) or 0)) and (
            str(settings.get("team_board_order_policy", "fixed")) == "fixed"
        )
        tolerance = int(settings.get("team_rating_tolerance", 0) or 0)
        max_subs = int(settings.get("team_max_substitutions", 0) or 0)

        lineups = self.db.list_team_lineups(tournament_id, round_id=round_id)
        issues.extend(self._incomplete_lineup_issues(tournament_id, lineups, settings))
        if enforce_order:
            for lineup in lineups:
                boards = self.db.list_team_lineup_boards(int(lineup["id"]))
                previous_rating: int | None = None
                previous_board: int | None = None
                for board in boards:
                    rating = int(board.get("player_rating") or 0)
                    board_number = int(board.get("board_number") or 0)
                    if previous_rating is not None and rating > previous_rating + tolerance:
                        issues.append({
                            "severity": "warning",
                            "kind": "board_order_broken",
                            "tournament_id": tournament_id,
                            "team_id": lineup.get("team_id"),
                            "team_name": lineup.get("team_name"),
                            "round_id": lineup.get("round_id"),
                            "round_number": lineup.get("round_number"),
                            "board_number": board_number,
                            "message": (
                                f"{lineup.get('team_name', 'Equipe')} R{lineup.get('round_number')}: "
                                f"tabuleiro {board_number} rating {rating} > "
                                f"tabuleiro {previous_board} ({previous_rating}) "
                                f"além da tolerância ({tolerance})."
                            ),
                        })
                    previous_rating = rating
                    previous_board = board_number

        if max_subs > 0:
            subs_by_team: dict[int, dict[str, Any]] = {}
            for event in self.db.list_team_substitution_events(tournament_id, round_id=round_id):
                team_id = int(event.get("team_id") or 0)
                bucket = subs_by_team.setdefault(team_id, {"count": 0, "team_name": None})
                bucket["count"] += 1
                bucket["team_name"] = event.get("team_name") or bucket["team_name"]
            for team_id, bucket in subs_by_team.items():
                if bucket["count"] > max_subs:
                    issues.append({
                        "severity": "warning",
                        "kind": "substitution_limit_exceeded",
                        "tournament_id": tournament_id,
                        "team_id": team_id,
                        "team_name": bucket["team_name"],
                        "round_id": None,
                        "round_number": None,
                        "message": (
                            f"{bucket['team_name'] or 'Equipe'}: "
                            f"{bucket['count']} substituição(ões) excede o limite "
                            f"de {max_subs}."
                        ),
                    })

        return issues

    def _incomplete_lineup_issues(
        self,
        tournament_id: int,
        lineups: list[dict[str, Any]],
        settings: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Escalação com tabuleiro vazio (W.O.) — aviso do painel do árbitro (EQ-02.5)."""
        boards_count = int(settings.get("team_boards_count") or 4)
        byes = {
            int(match["id"])
            for match in self.db.list_team_matches_for_tournament(tournament_id)
            if match.get("is_bye")
        }
        issues: list[dict[str, Any]] = []
        for lineup in lineups:
            if int(lineup.get("team_match_id") or 0) in byes:
                continue
            ocupados = {
                int(board.get("board_number") or 0)
                for board in self.db.list_team_lineup_boards(int(lineup["id"]))
            }
            vagas = [board for board in range(1, boards_count + 1) if board not in ocupados]
            if not vagas:
                continue
            issues.append({
                "severity": "warning",
                "kind": "lineup_incomplete",
                "tournament_id": tournament_id,
                "team_id": lineup.get("team_id"),
                "team_name": lineup.get("team_name"),
                "round_id": lineup.get("round_id"),
                "round_number": lineup.get("round_number"),
                "board_number": vagas[0],
                "message": (
                    f"{lineup.get('team_name', 'Equipe')} R{lineup.get('round_number')}: "
                    f"escalação incompleta, tabuleiro {', '.join(map(str, vagas))} "
                    "sem jogador (W.O.)."
                ),
            })
        return issues

    def _require_team_tournament(self, tournament_id: int) -> dict[str, Any]:
        tournament = self.db.get_tournament(tournament_id)
        if not tournament:
            raise AppError("Selecione um torneio válido.")
        if tournament.get("competition_type") != "team":
            raise AppError("Esta tela exige um torneio no formato Equipes.")
        return tournament

    @staticmethod
    def _validated_team_payload(data: dict[str, Any]) -> dict[str, Any]:
        name = str(data.get("name", "")).strip()
        if not name:
            raise AppError("Informe o nome da equipe.")
        return {
            "name": name,
            "club": str(data.get("club", "")),
            "captain": str(data.get("captain", "")),
            "notes": str(data.get("notes", "")),
            "active": 1 if data.get("active", 1) else 0,
        }

    def _validated_assignment_payload(
        self,
        tournament_id: int,
        board_number: Any,
        role: str,
    ) -> dict[str, Any]:
        role_value = str(role or "starter").strip() or "starter"
        if role_value not in TEAM_PLAYER_ROLES:
            raise AppError("Função do jogador na equipe inválida.")

        board_value: int | None = None
        if role_value == "starter":
            try:
                board_value = int(board_number or 0)
            except ValueError as exc:
                raise AppError("Número do tabuleiro inválido.") from exc
            if board_value < 1:
                raise AppError("Informe o tabuleiro do titular.")
            settings = self.db.get_tournament_settings(tournament_id) or {}
            boards_count = int(settings.get("team_boards_count") or 4)
            if board_value > boards_count:
                raise AppError(f"O torneio está configurado para {boards_count} tabuleiros por equipe.")

        return {
            "board_number": board_value,
            "role": role_value,
            "active": 1,
        }

    def _ensure_board_available(
        self,
        team_id: int,
        board_number: int | None,
        ignore_team_player_id: int | None = None,
    ) -> None:
        if board_number is None:
            return
        for assignment in self.db.list_team_players(team_id, active_only=False):
            if ignore_team_player_id and int(assignment["id"]) == ignore_team_player_id:
                continue
            if assignment.get("board_number") and int(assignment["board_number"]) == board_number:
                raise AppError("Já existe jogador neste tabuleiro da equipe.")
