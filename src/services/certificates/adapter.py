"""Ponte entre o modelo persistido (certificate_templates) + destinatário e o
que o ``renderer`` consome (preset, paleta, conteúdo, opções).

Sem I/O nem ReportLab: só monta objetos. O ``CertificateService`` (fachada)
usa isto para delegar o desenho ao pacote. A marca d'água por imagem é deixada
para a fachada carregar (precisa de ImageReader); aqui tudo é puro.
"""
from __future__ import annotations

from typing import Any, Mapping

from . import text as ctext
from .palettes import Palette, palette_from_colors, resolve_palette
from .renderer import CertificateContent, RenderOptions
from .styles import StylePreset, resolve_preset

def resolve_palette_for(template: Mapping[str, Any], preset: StylePreset) -> Palette:
    """Paleta nomeada do modelo; se vazia, deriva das cores escolhidas pelo usuário."""
    key = str(template.get("palette_key") or "").strip()
    if key:
        return resolve_palette(key, preset.key)
    return palette_from_colors(
        str(template.get("primary_color") or ""),
        str(template.get("accent_color") or ""),
    )


def _position(recipient: Mapping[str, Any], certificate_type: str) -> int:
    raw = recipient.get("category_position") if certificate_type == "category_award" else recipient.get("position")
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        return 0


def _flag(template: Mapping[str, Any], key: str, default: int = 1) -> bool:
    try:
        return bool(int(template.get(key, default) or 0))
    except (TypeError, ValueError):
        return bool(default)


def build_inputs(
    template: Mapping[str, Any], recipient: Mapping[str, Any]
) -> tuple[StylePreset, Palette, CertificateContent, RenderOptions]:
    preset = resolve_preset(str(template.get("style_preset") or ""))
    palette = resolve_palette_for(template, preset)
    variables = ctext.build_variables(recipient)
    cert_type = str(template.get("certificate_type") or "participation")
    position = _position(recipient, cert_type)
    seal_label = (
        recipient.get("category_position_label")
        if cert_type == "category_award"
        else recipient.get("position_label")
    )

    content = CertificateContent(
        title=ctext.render_plain(str(template.get("title_template") or ""), variables),
        intro="Certificamos que",
        name=str(recipient.get("name") or ""),
        body=ctext.render_plain(str(template.get("body_template") or ""), variables),
        footer=ctext.render_plain(str(template.get("footer_template") or ""), variables),
        signature_left=ctext.render_plain(str(template.get("signature_left") or ""), variables),
        signature_right=ctext.render_plain(str(template.get("signature_right") or ""), variables),
        source_title=str(recipient.get("tournament") or ""),
        verification_code=str(recipient.get("verification_code") or ""),
        position=position if position in (1, 2, 3) else 0,
        seal_label=str(seal_label or ""),
    )

    try:
        opacity = float(template.get("watermark_opacity") or 0.0)
    except (TypeError, ValueError):
        opacity = 0.0
    options = RenderOptions(
        seal_enabled=_flag(template, "seal_enabled"),
        watermark_enabled=_flag(template, "watermark_enabled"),
        medal_by_placement=_flag(template, "medal_by_placement"),
        watermark_kind=str(template.get("watermark_kind") or ""),
        watermark_piece=str(template.get("watermark_piece") or ""),
        watermark_opacity=opacity,
    )
    return preset, palette, content, options
