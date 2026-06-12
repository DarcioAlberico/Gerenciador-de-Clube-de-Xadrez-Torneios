"""Galeria de modelos de diploma prontos (dados puros, sem I/O).

Combina os presets de estilo × paletas recomendadas × tipos de certificado em
uma lista de modelos nomeados e **distribuídos** (round-robin entre presets,
para variedade). É a base tanto do preview quanto do seed da galeria no banco
(Fase 3). Determinístico e testável isolado.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .palettes import PALETTES, PALETTES_BY_PRESET, DEFAULT_PALETTE_BY_PRESET
from .styles import STYLE_PRESETS

_TOURNAMENT_TYPES = ("overall_award", "category_award", "participation")

# Texto padrão (título, corpo) por tipo de certificado — com variáveis {...}.
TYPE_TEXT: dict[str, tuple[str, str]] = {
    "overall_award": ("Certificado de Premiacao",
                      "conquistou a {posicao} colocacao geral no {torneio}, com {pontos} ponto(s)."),
    "category_award": ("Certificado de Premiacao",
                       "conquistou a {posicao_categoria} colocacao na categoria {categoria} do {torneio}."),
    "participation": ("Certificado de Participacao",
                      "participou do {torneio}, classificando-se na {posicao} colocacao geral."),
    "training_participation": ("Certificado de Conclusao",
                               "concluiu com dedicacao a atividade {aula}."),
    "event_participation": ("Certificado de Participacao",
                            "participou do evento {evento}."),
}
TYPE_LABEL: dict[str, str] = {
    "overall_award": "Premiacao geral",
    "category_award": "Premiacao por categoria",
    "participation": "Participacao",
    "training_participation": "Aula/turma",
    "event_participation": "Evento",
}
_TYPE_CYCLE = ("overall_award", "participation", "category_award", "training_participation", "event_participation")


@dataclass(frozen=True)
class GalleryModel:
    name: str
    style_preset: str
    palette_key: str
    certificate_type: str
    title_template: str
    body_template: str

    @property
    def is_award(self) -> bool:
        return self.certificate_type in ("overall_award", "category_award")


def _preset_combos(preset_key: str) -> list[tuple[str, str]]:
    """Para um preset, pareia cada tipo de certificado com uma paleta (ciclada)."""
    palettes = PALETTES_BY_PRESET.get(preset_key) or (DEFAULT_PALETTE_BY_PRESET[preset_key],)
    return [(palettes[i % len(palettes)], cert_type) for i, cert_type in enumerate(_TYPE_CYCLE)]


def build_gallery(limit: int = 50) -> list[GalleryModel]:
    """Devolve até ``limit`` modelos distribuídos pelos 10 presets.

    Round-robin por profundidade: na rodada N, cada preset contribui com o seu
    N-ésimo par (paleta, tipo). Como cada preset oferece um par por tipo, os 10
    presets × 5 tipos dão 50 modelos únicos (preset×paleta×tipo).
    """
    presets = list(STYLE_PRESETS)
    combos = {preset_key: _preset_combos(preset_key) for preset_key in presets}
    max_depth = max((len(c) for c in combos.values()), default=0)
    models: list[GalleryModel] = []
    for depth in range(max_depth):
        for preset_key in presets:
            preset_combos = combos[preset_key]
            if depth >= len(preset_combos):
                continue
            palette_key, cert_type = preset_combos[depth]
            title, body = TYPE_TEXT[cert_type]
            models.append(GalleryModel(
                name=f"{STYLE_PRESETS[preset_key].name} · {PALETTES[palette_key].name} · {TYPE_LABEL[cert_type]}",
                style_preset=preset_key,
                palette_key=palette_key,
                certificate_type=cert_type,
                title_template=title,
                body_template=body,
            ))
            if len(models) >= limit:
                return models
    return models


def model_to_template(model: GalleryModel) -> dict[str, Any]:
    """Converte um modelo da galeria no payload de um ``certificate_template``."""
    footer = "{local} - {periodo}" if model.certificate_type in _TOURNAMENT_TYPES else "{clube} - {data}"
    return {
        "name": model.name,
        "certificate_type": model.certificate_type,
        "title_template": model.title_template,
        "body_template": model.body_template,
        "footer_template": footer,
        "orientation": "landscape",
        "signature_left": "Organizacao",
        "signature_right": "Arbitragem / Direcao",
        "style_preset": model.style_preset,
        "palette_key": model.palette_key,
        "seal_enabled": 1,
        "watermark_enabled": 1,
        "medal_by_placement": 1,
        "active": 1,
    }
