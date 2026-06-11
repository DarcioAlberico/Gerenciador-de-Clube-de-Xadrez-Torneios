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
from typing import Any, Mapping

from src.core.database import BASE_DIR, DEFAULT_CERTIFICATE_TEMPLATES, Database

logger = logging.getLogger(__name__)

RESULTS = ["", "1-0", "0-1", "1/2-1/2", "1F-0F", "0F-1F", "0F-0F"]

# Ciclo de vida do resultado por mesa, derivado de result + round.status +
# submissões QR + auditoria. Inspirado pelo spec §6.4/§7.3:
#   empty      -> sem resultado registrado
#   submitted  -> submissão QR aguardando aprovação do árbitro
#   published  -> resultado aplicado e visível
#   corrected  -> resultado foi alterado após primeira aplicação (com auditoria)
#   locked    -> rodada fechada; alterações exigem reabertura
# (approved/rejected ficam no submission-level, em result_submissions.status)
RESULT_STATES = ("empty", "submitted", "published", "corrected", "locked")
RESULT_STATE_LABELS = {
    "empty": "Sem resultado",
    "submitted": "Aguardando aprovação",
    "published": "Publicado",
    "corrected": "Corrigido",
    "locked": "Bloqueado (rodada fechada)",
}
FINAL_RESULTS = {"1-0", "0-1", "1/2-1/2", "1F-0F", "0F-1F", "0F-0F", "BYE", "F", "H", "Z"}
RESULT_POINTS = {
    "1-0": (1.0, 0.0),
    "0-1": (0.0, 1.0),
    "1/2-1/2": (0.5, 0.5),
    "1F-0F": (1.0, 0.0),
    "0F-1F": (0.0, 1.0),
    "0F-0F": (0.0, 0.0),
}
# Pontuação fixa do bye solicitado por tipo FIDE (independe de bye_points):
# F = full-point-bye, H = half-point-bye, Z = zero-point-bye.
REQUESTED_BYE_POINTS = {"F": 1.0, "H": 0.5, "Z": 0.0}
REQUESTED_BYE_TYPES = {
    "F": "Bye com ponto inteiro (F)",
    "H": "Bye com meio ponto (H)",
    "Z": "Bye com zero ponto (Z)",
}
MEMBER_TYPES = {"socio", "aluno", "convidado", "visitante"}
MEMBER_STATUSES = {"active", "inactive", "visitor", "guest", "withdrawn"}
PLAYER_STATUSES = {
    "active": "Ativo",
    "withdrawn": "Desistente",
    "absent": "Ausente",
    "inactive": "Nao emparceirado",
}
INITIAL_ORDER_OPTIONS = {
    "rating": "Rating principal",
    "national_rating": "Rating nacional",
    "international_rating": "Rating internacional",
    "international_then_national": "Rating internacional depois nacional",
    "max_rating": "Maior rating",
    "manual": "Manual",
}
TOURNAMENT_TYPES = {"real": "Real", "test": "Teste"}
TOURNAMENT_PROFILES = {
    "free": "Livre/Escolar",
    "club": "Clube/Semi-formal",
    "fide": "FIDE-rated",
}
COMPETITION_TYPES = {"individual": "Individual", "team": "Equipes"}
PAIRING_METHODS = {
    "swiss": "Suíço",
    "round_robin": "Schuring (Todos contra todos)",
    "knockout": "Mata-mata",
    "scheveningen": "Scheveningen (A x B)",
}
PAIRING_SYSTEMS = {
    "fide_dutch": "FIDE Dutch",
    "dubov": "Dubov",
    "burstein": "Burstein",
    "lim": "Lim",
    "team_swiss": "Suico por equipes",
    "custom_authorized": "Customizado/autorizado",
    "gacrux_swiss": "Suico (Gacrux)",
}
ACCELERATION_METHODS = {
    "none": "Sem aceleracao",
    "accelerated": "Classica (Haley)",
    "custom": "Personalizada (parametrizavel)",
    "baku": "Baku (sem formula oficial - nao emite 250)",
}
TEAM_PAIRING_METHODS = {"swiss": "Suico", "round_robin": "Schuring (Todos contra todos)"}
CERTIFICATE_TYPES = {
    "participation": "Participacao",
    "overall_award": "Premiacao geral",
    "category_award": "Premiacao por categoria",
    "member_certificate": "Membro/aluno",
    "training_participation": "Aula/turma",
    "event_participation": "Evento",
    "internal_ranking": "Ranking interno",
}
CERTIFICATE_ORIENTATIONS = {"landscape": "Paisagem", "portrait": "Retrato"}
TEAM_PLAYER_ROLES = {"starter": "Titular", "reserve": "Reserva"}
TEAM_PAIRING_METHODS = {"swiss": "Suico por equipes"}
TEAM_STANDING_CRITERIA = {
    "match_points": "Match points",
    "game_points": "Game points",
    "wins": "Vitorias",
}
TOURNAMENT_SCOPES = {
    "standalone": "Avulso",
    "club": "Clube/Escola",
    "class": "Turma",
}


def _player_name_parts(player: Mapping[str, Any]) -> tuple[str, str]:
    name = str(player.get("name") or "").strip()
    surname = str(player.get("surname") or "").strip()
    given_name = str(player.get("given_name") or "").strip()
    if given_name:
        return given_name, surname
    if surname and "," in name:
        left, right = name.split(",", maxsplit=1)
        if left.strip().casefold() == surname.casefold():
            return right.strip(), surname
    if surname:
        name_casefold = name.casefold()
        surname_casefold = surname.casefold()
        if name_casefold.endswith(f" {surname_casefold}"):
            return name[: -len(surname)].strip(), surname
        if name_casefold == surname_casefold:
            return "", surname
    return name, surname


def player_full_name(player: Mapping[str, Any]) -> str:
    given_name, surname = _player_name_parts(player)
    if given_name and surname:
        return f"{given_name} {surname}"
    return given_name or surname


def player_pairing_name(player: Mapping[str, Any]) -> str:
    given_name, surname = _player_name_parts(player)
    if given_name and surname:
        return f"{surname}, {given_name}"
    return given_name or surname


def pairing_player_name(pairing: Mapping[str, Any], color: str) -> str:
    return player_pairing_name(
        {
            "name": pairing.get(f"{color}_name"),
            "surname": pairing.get(f"{color}_surname"),
            "given_name": pairing.get(f"{color}_given_name"),
        }
    )
CLUB_KINDS = {"club", "school", "project", "partner"}
TRAINING_SESSION_TYPES = {"aula": "Aula", "treino": "Treino", "evento": "Evento"}
TRAINING_SESSION_STATUSES = {"planned": "Planejada", "done": "Realizada", "canceled": "Cancelada"}
ATTENDANCE_STATUSES = {"present": "Presente", "absent": "Falta", "justified": "Justificada"}
EXERCISE_DIFFICULTIES = {
    "easy": "Facil",
    "basic": "Basico",
    "intermediate": "Intermediario",
    "advanced": "Avancado",
    "competition": "Competitivo",
}
TRAINING_LIST_STATUSES = {
    "draft": "Rascunho",
    "ready": "Pronta",
    "used": "Aplicada",
    "archived": "Arquivada",
}
EXERCISE_ATTEMPT_RESULTS = {
    "correct": "Correto",
    "partial": "Parcial",
    "incorrect": "Incorreto",
    "skipped": "Nao resolvido",
}
BILLING_CYCLES = {
    "monthly": "Mensal",
    "single": "Avulso",
    "annual": "Anual",
    "custom": "Personalizado",
}
PAYMENT_STATUSES = {
    "pending": "Pendente",
    "paid": "Pago",
    "late": "Atrasado",
    "exempt": "Isento",
    "canceled": "Cancelado",
}
EVENT_TYPES = {
    "tournament": "Torneio",
    "class": "Aula/Treino",
    "meeting": "Reuniao",
    "simultaneous": "Simultanea",
    "travel": "Viagem",
    "social": "Encontro",
    "other": "Outro",
}
EVENT_STATUSES = {
    "planned": "Planejado",
    "confirmed": "Confirmado",
    "done": "Concluido",
    "canceled": "Cancelado",
}
INVENTORY_ITEM_TYPES = {
    "pieces": "Pecas",
    "boards": "Tabuleiros",
    "clocks": "Relogios",
    "books": "Livros",
    "sets": "Kits",
    "digital": "Digital",
    "other": "Outro",
}
INVENTORY_CONDITIONS = {
    "new": "Novo",
    "good": "Bom",
    "worn": "Uso intenso",
    "damaged": "Danificado",
    "lost": "Perdido",
}
INVENTORY_LOAN_STATUSES = {
    "open": "Emprestado",
    "returned": "Devolvido",
    "lost": "Perdido",
}
INVENTORY_MAINTENANCE_STATUSES = {
    "open": "Aberta",
    "in_progress": "Em andamento",
    "done": "Concluida",
    "canceled": "Cancelada",
}
OPERATOR_ROLES = {
    "admin": "Administrador",
    "arbiter": "Arbitragem",
    "teacher": "Professor",
    "assistant": "Assistente",
    "viewer": "Consulta",
    # Spec §14.1 — perfis específicos de torneio
    "capitao": "Capitão de equipe",
    "jogador": "Jogador",
    # "publico" não é login role: o portal público é servido por rotas
    # anônimas (export_site / LocalResultServer), não por sessão autenticada.
}
TOURNAMENT_FLAG_FIELDS = {
    "allow_public_registration",
    "allow_player_result_edit",
    "allow_dangerous_changes",
    "disable_bye",
    "accelerated_system",
    "hide_standings",
    "calculate_performance",
    "hide_color_names",
    "show_opponents_in_standings",
    "archived",
}


class AppError(Exception):
    """Erro esperado de regra de negocio, seguro para mostrar ao usuario."""

