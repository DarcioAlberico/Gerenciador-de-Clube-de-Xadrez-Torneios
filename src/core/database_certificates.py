"""Mixin do dominio de certificados (modelos e emissoes) da Database.

Extraido de ``src.core.database`` na decomposicao da God Class em mixins por
dominio. Comportamento preservado; a fachada ``Database`` herda deste mixin.
Ver ``_database_base._DatabaseInfra``.
"""
from __future__ import annotations

from typing import Any

from ._database_base import _DatabaseInfra


class CertificateMixin(_DatabaseInfra):
    def list_certificate_templates(self, active_only: bool = False) -> list[dict[str, Any]]:
        active_filter = "WHERE active = 1" if active_only else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM certificate_templates
                {active_filter}
                ORDER BY active DESC, certificate_type ASC, name COLLATE NOCASE ASC
                """
            ).fetchall()
            return self.rows_to_dicts(rows)

    def get_certificate_template(self, template_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM certificate_templates
                WHERE id = ?
                """,
                (template_id,),
            ).fetchone()
            return dict(row) if row else None

    def create_certificate_template(self, **data: Any) -> int:
        now = self.now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO certificate_templates (
                    name, certificate_type, title_template, body_template, footer_template,
                    orientation, signature_left, signature_right, logo_path,
                    background_image_path, background_opacity, secondary_logo_path,
                    primary_color, accent_color, title_font_size, body_font_size, footer_font_size,
                    style_preset, template_kind, palette_key, seal_enabled, watermark_enabled,
                    watermark_kind, watermark_piece, watermark_image_path, watermark_opacity,
                    medal_by_placement, field_layout_json,
                    active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(data.get("name", "")).strip(),
                    str(data.get("certificate_type", "participation")).strip() or "participation",
                    str(data.get("title_template", "")).strip(),
                    str(data.get("body_template", "")).strip(),
                    str(data.get("footer_template", "")).strip(),
                    str(data.get("orientation", "landscape")).strip() or "landscape",
                    str(data.get("signature_left", "")).strip(),
                    str(data.get("signature_right", "")).strip(),
                    str(data.get("logo_path", "")).strip(),
                    str(data.get("background_image_path", "")).strip(),
                    float(data.get("background_opacity", 0.18) or 0.18),
                    str(data.get("secondary_logo_path", "")).strip(),
                    str(data.get("primary_color", "#1E3A8A")).strip() or "#1E3A8A",
                    str(data.get("accent_color", "#93C5FD")).strip() or "#93C5FD",
                    int(data.get("title_font_size", 32) or 32),
                    int(data.get("body_font_size", 18) or 18),
                    int(data.get("footer_font_size", 10) or 10),
                    str(data.get("style_preset", "classic")).strip() or "classic",
                    str(data.get("template_kind", "generated")).strip() or "generated",
                    str(data.get("palette_key", "")).strip(),
                    int(data.get("seal_enabled", 1) or 0),
                    int(data.get("watermark_enabled", 1) or 0),
                    str(data.get("watermark_kind", "")).strip(),
                    str(data.get("watermark_piece", "")).strip(),
                    str(data.get("watermark_image_path", "")).strip(),
                    float(data.get("watermark_opacity", 0.08) or 0.0),
                    int(data.get("medal_by_placement", 1) or 0),
                    str(data.get("field_layout_json", "")).strip(),
                    int(data.get("active", 1) or 0),
                    now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def update_certificate_template(self, template_id: int, **data: Any) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE certificate_templates
                SET name = ?, certificate_type = ?, title_template = ?, body_template = ?,
                    footer_template = ?, orientation = ?, signature_left = ?,
                    signature_right = ?, logo_path = ?, background_image_path = ?,
                    background_opacity = ?, secondary_logo_path = ?,
                    primary_color = ?, accent_color = ?,
                    title_font_size = ?, body_font_size = ?, footer_font_size = ?,
                    style_preset = ?, template_kind = ?, palette_key = ?,
                    seal_enabled = ?, watermark_enabled = ?, watermark_kind = ?,
                    watermark_piece = ?, watermark_image_path = ?, watermark_opacity = ?,
                    medal_by_placement = ?, field_layout_json = ?,
                    active = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    str(data.get("name", "")).strip(),
                    str(data.get("certificate_type", "participation")).strip() or "participation",
                    str(data.get("title_template", "")).strip(),
                    str(data.get("body_template", "")).strip(),
                    str(data.get("footer_template", "")).strip(),
                    str(data.get("orientation", "landscape")).strip() or "landscape",
                    str(data.get("signature_left", "")).strip(),
                    str(data.get("signature_right", "")).strip(),
                    str(data.get("logo_path", "")).strip(),
                    str(data.get("background_image_path", "")).strip(),
                    float(data.get("background_opacity", 0.18) or 0.18),
                    str(data.get("secondary_logo_path", "")).strip(),
                    str(data.get("primary_color", "#1E3A8A")).strip() or "#1E3A8A",
                    str(data.get("accent_color", "#93C5FD")).strip() or "#93C5FD",
                    int(data.get("title_font_size", 32) or 32),
                    int(data.get("body_font_size", 18) or 18),
                    int(data.get("footer_font_size", 10) or 10),
                    str(data.get("style_preset", "classic")).strip() or "classic",
                    str(data.get("template_kind", "generated")).strip() or "generated",
                    str(data.get("palette_key", "")).strip(),
                    int(data.get("seal_enabled", 1) or 0),
                    int(data.get("watermark_enabled", 1) or 0),
                    str(data.get("watermark_kind", "")).strip(),
                    str(data.get("watermark_piece", "")).strip(),
                    str(data.get("watermark_image_path", "")).strip(),
                    float(data.get("watermark_opacity", 0.08) or 0.0),
                    int(data.get("medal_by_placement", 1) or 0),
                    str(data.get("field_layout_json", "")).strip(),
                    int(data.get("active", 1) or 0),
                    self.now(),
                    template_id,
                ),
            )

    def create_certificate_issuances(self, rows: list[dict[str, Any]]) -> list[int]:
        if not rows:
            return []
        now = self.now()
        inserted_ids: list[int] = []
        with self.connect() as connection:
            for row in rows:
                cursor = connection.execute(
                    """
                    INSERT INTO certificate_issuances (
                        verification_code, context_type, source_id, source_title,
                        recipient_id, recipient_name, recipient_category,
                        certificate_type, template_id, template_name, file_path,
                        issued_at, revoked, revoked_at, notes, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(row.get("verification_code", "")).strip(),
                        str(row.get("context_type", "")).strip(),
                        row.get("source_id"),
                        str(row.get("source_title", "")).strip(),
                        row.get("recipient_id"),
                        str(row.get("recipient_name", "")).strip(),
                        str(row.get("recipient_category", "")).strip(),
                        str(row.get("certificate_type", "")).strip(),
                        row.get("template_id"),
                        str(row.get("template_name", "")).strip(),
                        str(row.get("file_path", "")).strip(),
                        str(row.get("issued_at") or now),
                        int(row.get("revoked", 0) or 0),
                        str(row.get("revoked_at", "")).strip(),
                        str(row.get("notes", "")).strip(),
                        str(row.get("payload_json", "")).strip(),
                    ),
                )
                inserted_ids.append(int(cursor.lastrowid))
        return inserted_ids

    def list_certificate_issuances(
        self,
        limit: int = 50,
        context_type: str = "",
        verification_code: str = "",
        recipient_name: str = "",
        include_revoked: bool = True,
    ) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if context_type:
            conditions.append("context_type = ?")
            params.append(context_type.strip())
        if verification_code:
            conditions.append("verification_code = ?")
            params.append(verification_code.strip().upper())
        if recipient_name:
            conditions.append("recipient_name LIKE ?")
            params.append(f"%{recipient_name.strip()}%")
        if not include_revoked:
            conditions.append("revoked = 0")
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        safe_limit = max(1, min(int(limit or 50), 5000))
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM certificate_issuances
                {where}
                ORDER BY issued_at DESC, id DESC
                LIMIT ?
                """,
                [*params, safe_limit],
            ).fetchall()
            return self.rows_to_dicts(rows)

    def get_certificate_issuance_by_code(self, verification_code: str) -> dict[str, Any] | None:
        code = verification_code.strip().upper()
        if not code:
            return None
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM certificate_issuances
                WHERE verification_code = ?
                """,
                (code,),
            ).fetchone()
            return dict(row) if row else None

    def revoke_certificate_issuance(self, issuance_id: int, notes: str = "") -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE certificate_issuances
                SET revoked = 1,
                    revoked_at = ?,
                    notes = ?
                WHERE id = ?
                """,
                (self.now(), notes.strip(), issuance_id),
            )

    def delete_certificate_issuances(self, issuance_ids: list[int]) -> None:
        if not issuance_ids:
            return
        placeholders = ", ".join("?" for _ in issuance_ids)
        with self.connect() as connection:
            connection.execute(
                f"""
                DELETE FROM certificate_issuances
                WHERE id IN ({placeholders})
                """,
                [int(issuance_id) for issuance_id in issuance_ids],
            )
