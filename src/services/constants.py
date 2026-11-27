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
# O que um resultado E (pontos, se foi jogada, se e ratavel, letras TRF) mora no
# registro (ARB-02); daqui saem os nomes de sempre, agora derivados dele.
from src.services.results_registry import (
    RESULT_CODES,
    RESULT_LABELS,
    RESULT_POINTS,
    RESULT_VALUES as RESULTS,
    UNRATED_RESULTS,
    WALKOVER_RESULTS,
    code_from_trf_letter,
    is_played_result,
    is_rated_result,
    trf_letters,
)

logger = logging.getLogger(__name__)

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
# Resultado final = qualquer código de mesa do registro (ver
# `results_registry.py`) mais os de bye. Derivado, e não repetido: um código novo
# entra no registro e chega aqui sozinho.
FINAL_RESULTS = set(RESULT_POINTS) | {"BYE", "F", "H", "Z"}
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
    "inactive": "Não emparceirado",
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
# Rótulo do motor próprio de pareamento (RGS-18). Tudo que não é `gacrux_swiss`
# pareia o Suíço individual pelo motor próprio (`fide_dutch.py`), que é reserva:
# não segue o holandês completo (C.04.3) e não é homologado pela FIDE.
RESERVE_ENGINE_LABEL = "motor reserva — não homologado FIDE"
PAIRING_SYSTEMS = {
    "fide_dutch": f"FIDE Dutch ({RESERVE_ENGINE_LABEL})",
    "dubov": f"Dubov ({RESERVE_ENGINE_LABEL})",
    "burstein": f"Burstein ({RESERVE_ENGINE_LABEL})",
    "lim": f"Lim ({RESERVE_ENGINE_LABEL})",
    "team_swiss": "Suíço por equipes",
    "custom_authorized": f"Customizado/autorizado ({RESERVE_ENGINE_LABEL})",
    "gacrux_swiss": "Suíço (Gacrux)",
}
# Sistemas que pareiam pelo motor reserva: escolhê-los exige confirmação (RGS-18).
RESERVE_PAIRING_SYSTEMS = frozenset(
    sistema for sistema, rotulo in PAIRING_SYSTEMS.items() if RESERVE_ENGINE_LABEL in rotulo
)
# Motor de cálculo dos desempates/classificacao. 'gacrux' usa o motor FIDE
# oficial (tiebreakchecker.py); 'albericus' usa o cálculo próprio (histórico).
TIEBREAK_ENGINES = {
    "gacrux": "FIDE (Gacrux)",
    "albericus": "Albericus (próprio)",
}
ACCELERATION_METHODS = {
    "none": "Sem aceleração",
    "accelerated": "Clássica (Haley)",
    "custom": "Personalizada (parametrizável)",
    "baku": "Baku (FIDE C.04.7)",
}
TEAM_PAIRING_METHODS = {"swiss": "Suíço", "round_robin": "Schuring (Todos contra todos)"}
CERTIFICATE_TYPES = {
    "participation": "Participação",
    "overall_award": "Premiação geral",
    "category_award": "Premiação por categoria",
    "member_certificate": "Membro/aluno",
    "training_participation": "Aula/turma",
    "event_participation": "Evento",
    "internal_ranking": "Ranking interno",
}
CERTIFICATE_ORIENTATIONS = {"landscape": "Paisagem", "portrait": "Retrato"}
TEAM_PLAYER_ROLES = {"starter": "Titular", "reserve": "Reserva"}
# NÃO redefina TEAM_PAIRING_METHODS aqui. Havia uma segunda definição nesta
# linha (só "swiss") que sobrescrevia em silêncio a de cima e tornava o
# round-robin por equipes inalcancavel: a validação recusava e o menu só
# oferecia Suíço (PAR-04).
TEAM_STANDING_CRITERIA = {
    "match_points": "Match points",
    "game_points": "Game points",
    "wins": "Vitórias",
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
    "easy": "Fácil",
    "basic": "Básico",
    "intermediate": "Intermediário",
    "advanced": "Avançado",
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
    "skipped": "Não resolvido",
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
    "meeting": "Reunião",
    "simultaneous": "Simultânea",
    "travel": "Viagem",
    "social": "Encontro",
    "other": "Outro",
}
EVENT_STATUSES = {
    "planned": "Planejado",
    "confirmed": "Confirmado",
    "done": "Concluído",
    "canceled": "Cancelado",
}
INVENTORY_ITEM_TYPES = {
    "pieces": "Peças",
    "boards": "Tabuleiros",
    "clocks": "Relógios",
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
    "done": "Concluída",
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
# ORG-04: uma opção visível que não faz nada é pior do que opção nenhuma — o
# árbitro marca e acredita. Saíram daqui (e da tela) `accelerated_system` (a
# aceleração de verdade e `acceleration_method`), `allow_public_registration` e
# `allow_player_result_edit` (não existe inscrição publica nem edição direta:
# o envio por QR passa pela fila de aprovação), `hide_color_names`,
# `show_opponents_in_standings` e `calculate_performance` (a performance sempre
# foi calculada). As COLUNAS ficam no banco: bases antigas as tem, e derrubar
# coluna no SQLite custa reescrever a tabela para apagar o que ninguém lê.
TOURNAMENT_FLAG_FIELDS = {
    "allow_dangerous_changes",
    "disable_bye",
    # Returno do rodízio (PAR-01). Não vale para o Suíço: lá o número de rodadas
    # e escolhido, e não derivado do calendário.
    "round_robin_double",
    # Disputa de 3o lugar no mata-mata (PAR-03).
    "knockout_third_place",
    "hide_standings",
    "tiebreak_strict",
    # Excluir desistentes da premiação (ORG-02).
    "prize_exclude_withdrawn",
    "archived",
}


class AppError(Exception):
    """Erro esperado de regra de negócio, seguro para mostrar ao usuário.

    ``suggestion`` e a ação sugerida (RGS-26): a tela mostra a recusa numa faixa
    fixa, com o que fazer em seguida — recusa sem saída ensina o árbitro a
    procurar o atalho errado (foi assim que "mudancas perigosas" virou rotina).
    """

    def __init__(self, *args: object, suggestion: str = "") -> None:
        super().__init__(*args)
        self.suggestion = " ".join(str(suggestion or "").split())

