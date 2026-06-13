"""Substituição de variáveis e escape de texto dos diplomas (puro).

Isola a transformação ``"{nome} ... {posicao}"`` + dados do destinatário em
texto pronto para o ReportLab. Sem desenho, sem I/O — só strings. O dicionário
de variáveis é o contrato com os modelos (as chaves ``{...}`` documentadas).
"""
from __future__ import annotations

import html
from typing import Any, Mapping

# Chaves de variável aceitas nos modelos, na ordem de documentação.
VARIABLE_KEYS = (
    "nome", "torneio", "local", "periodo", "data", "posicao", "posicao_numero",
    "categoria", "posicao_categoria", "posicao_categoria_numero", "pontos",
    "rating", "clube", "turma", "aula", "evento", "instrutor", "professor",
    "tipo", "status", "nivel", "delta", "jogos", "desempenho", "aproveitamento",
    "vitorias", "empates", "derrotas", "ultimo_torneio", "codigo",
    "codigo_verificacao", "emissao", "emitido_em",
)


def escape_pdf(value: str) -> str:
    """Escapa o texto para os mini-marcadores do ReportLab Paragraph (sem aspas)."""
    return html.escape(value, quote=False)


def build_variables(recipient: Mapping[str, Any]) -> dict[str, str]:
    """Mapeia o destinatário no dicionário de variáveis ``{chave}`` dos modelos."""
    def text(key: str, default: str = "") -> str:
        return str(recipient.get(key) or default)

    return {
        "nome": text("name"),
        "torneio": text("tournament"),
        "local": text("location"),
        "periodo": text("date_range"),
        "data": text("date_range"),
        "posicao": text("position_label"),
        "posicao_numero": text("position"),
        "categoria": text("category"),
        "posicao_categoria": text("category_position_label"),
        "posicao_categoria_numero": text("category_position"),
        "pontos": text("points", "0"),
        "rating": text("rating"),
        "clube": text("club"),
        "turma": text("class_name"),
        "aula": text("session"),
        "evento": text("event"),
        "instrutor": text("instructor"),
        "professor": text("instructor"),
        "tipo": str(recipient.get("type_label") or recipient.get("member_type") or ""),
        "status": text("status"),
        "nivel": text("learning_level"),
        "delta": text("last_delta"),
        "jogos": text("games"),
        "desempenho": text("last_performance"),
        "aproveitamento": text("score_rate"),
        "vitorias": text("wins"),
        "empates": text("draws"),
        "derrotas": text("losses"),
        "ultimo_torneio": text("last_tournament"),
        "codigo": text("verification_code"),
        "codigo_verificacao": text("verification_code"),
        "emissao": text("issued_at_label"),
        "emitido_em": text("issued_at_label"),
    }


def render_rich(template: str, variables: Mapping[str, str]) -> str:
    """Renderiza preservando quebras (``\\n`` -> ``<br/>``) e marcadores do modelo."""
    if not template:
        return ""
    rendered = escape_pdf(template).replace("\n", "<br/>")
    for key, value in variables.items():
        rendered = rendered.replace(f"{{{key}}}", escape_pdf(value))
    return rendered


def render_plain(template: str, variables: Mapping[str, str]) -> str:
    """Versão em texto plano (para drawString simples — sem marcadores)."""
    rendered = render_rich(template, variables)
    return html.unescape(rendered.replace("<br/>", " "))
