"""Galeria de modelos de diploma prontos (dados puros, sem I/O).

Combina os presets de estilo × paletas recomendadas × tipos de certificado em
uma lista de modelos nomeados e **distribuídos** (round-robin entre presets,
para variedade). É a base tanto do preview quanto do seed da galeria no banco
(Fase 3). Determinístico e testável isolado.
"""
from __future__ import annotations

from dataclasses import dataclass

from .palettes import PALETTES, PALETTES_BY_PRESET, DEFAULT_PALETTE_BY_PRESET
from .styles import STYLE_PRESETS

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


def build_gallery(limit: int = 50) -> list[GalleryModel]:
    """Devolve até ``limit`` modelos distribuídos pelos 10 presets (sem repetir
    a combinação preset×paleta×tipo)."""
    presets = list(STYLE_PRESETS)
    pal_cursor = {p: 0 for p in presets}
    seen: set[tuple[str, str, str]] = set()
    models: list[GalleryModel] = []
    type_i = 0
    while len(models) < limit:
        added = False
        for preset_key in presets:
            if len(models) >= limit:
                break
            palettes = PALETTES_BY_PRESET.get(preset_key) or (DEFAULT_PALETTE_BY_PRESET[preset_key],)
            palette_key = palettes[pal_cursor[preset_key] % len(palettes)]
            pal_cursor[preset_key] += 1
            cert_type = _TYPE_CYCLE[type_i % len(_TYPE_CYCLE)]
            type_i += 1
            key = (preset_key, palette_key, cert_type)
            if key in seen:
                continue
            seen.add(key)
            title, body = TYPE_TEXT[cert_type]
            models.append(GalleryModel(
                name=f"{STYLE_PRESETS[preset_key].name} · {PALETTES[palette_key].name} · {TYPE_LABEL[cert_type]}",
                style_preset=preset_key,
                palette_key=palette_key,
                certificate_type=cert_type,
                title_template=title,
                body_template=body,
            ))
            added = True
        if not added:
            break
    return models
