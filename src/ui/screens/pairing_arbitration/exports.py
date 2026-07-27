"""As publicações que o painel dispara: pacote, boletim, pódio, ata, site, live.

São seis ações com a mesma anatomia — escolher onde salvar, chamar o
`export_service` em background, contar o que saiu. Ficam num módulo próprio
porque escolher arquivo é conversa com o usuário (fica na view) e gerar PDF é
trabalho longo (vai para o `_run_background` da F2.3): juntá-las ao painel foi
parte do que fez o arquivo original crescer para 1.527 linhas.

O erro em background já cai no `_show_error` unificado da F2.2 — ou seja, vira
toast, e não modal por cima de quem está lançando resultado.
"""
from __future__ import annotations

from typing import Any

from tkinter import filedialog

from src.core.services import LocalResultServer

from ...i18n import t

PDF_ONLY = (("PDF", "*.pdf"),)
PDF_SHEET = (("PDF", "*.pdf"), ("XLSX", "*.xlsx"), ("CSV", "*.csv"))


class ArbitrationExportActions:
    """As ações de publicação do painel, sobre o host (a ``AlbericusApp``)."""

    def __init__(self, host: Any, controller: Any) -> None:
        self.host = host
        self.controller = controller

    @property
    def tournament_id(self) -> int:
        return int(self.host.current_tournament_id)

    # ---- Documentos da rodada --------------------------------------------- #

    def export_round_package(self) -> None:
        host = self.host
        try:
            self._require_tournament()
            round_id = self.controller.latest_round_id(self.tournament_id)
            pasta = filedialog.askdirectory(
                title=t("arbitration.export.package.title"),
                initialdir=str(host._default_export_dir()),
            )
            if not pasta:
                return

            def mostrar(resultado: dict[str, Any]) -> None:
                mensagem = t(
                    "arbitration.export.package.done", quantidade=resultado["count"], pasta=pasta
                )
                if resultado["errors"]:
                    mensagem += "\n\n" + t("arbitration.export.warnings") + "\n"
                    mensagem += "\n".join(resultado["errors"][:6])
                host._show_info(mensagem)

            host._run_background(
                lambda: host.export_service.export_round_package(round_id, pasta),
                mostrar,
                t("arbitration.export.package.busy"),
            )
        except Exception as exc:
            host._show_error(exc)

    def export_round_bulletin(self) -> None:
        host = self.host
        try:
            self._require_tournament()
            rodadas = host.db.list_rounds(self.tournament_id)
            if not rodadas:
                raise self._app_error(t("arbitration.error.no_round_bulletin"))
            ultima = sorted(rodadas, key=lambda item: int(item["number"]))[-1]
            caminho = self._ask_path(
                t("arbitration.export.bulletin.title"),
                f"_boletim_r{ultima['number']}.pdf",
                PDF_SHEET,
            )
            if not caminho:
                return
            host._run_background(
                lambda: host.export_service.export_round_bulletin(int(ultima["id"]), caminho),
                lambda _resultado: host._show_info(
                    t("arbitration.export.bulletin.done", caminho=caminho)
                ),
                t("arbitration.export.bulletin.busy"),
            )
        except Exception as exc:
            host._show_error(exc)

    # ---- Documentos do torneio -------------------------------------------- #

    def export_podium(self) -> None:
        host = self.host
        try:
            self._require_tournament()
            caminho = self._ask_path(t("arbitration.export.podium.title"), "_podio.pdf", PDF_ONLY)
            if not caminho:
                return
            host._run_background(
                lambda: host.export_service.export_podium(self.tournament_id, caminho),
                lambda _resultado: host._show_info(
                    t("arbitration.export.podium.done", caminho=caminho)
                ),
                t("arbitration.export.podium.busy"),
            )
        except Exception as exc:
            host._show_error(exc)

    def export_minutes(self) -> None:
        host = self.host
        try:
            self._require_tournament()
            caminho = self._ask_path(
                t("arbitration.export.minutes.title"), "_ata_final.pdf", PDF_SHEET
            )
            if not caminho:
                return
            host._run_background(
                lambda: host.export_service.export_tournament_minutes(self.tournament_id, caminho),
                lambda _resultado: host._show_info(
                    t("arbitration.export.minutes.done", caminho=caminho)
                ),
                t("arbitration.export.minutes.busy"),
            )
        except Exception as exc:
            host._show_error(exc)

    # ---- Publicação online ------------------------------------------------ #

    def export_site(self) -> None:
        host = self.host
        try:
            host.db.backup_before("publish_site", tournament_id=self.tournament_id)
            destino = host._default_export_dir() / f"site_torneio_{self.tournament_id}"
            indice = host.export_service.export_site(self.tournament_id, destino)
            host._show_info(t("arbitration.export.site.done", caminho=indice))
        except Exception as exc:
            host._show_error(exc)

    def publish_live_portal(self) -> None:
        host = self.host
        try:
            host.db.backup_before("publish_live_portal", tournament_id=self.tournament_id)
            if host.local_result_server is None:
                host.local_result_server = LocalResultServer(host.qr_result_service)
            modo = str((host.db.get_app_settings() or {}).get("live_portal_mode") or "publico")
            url = host.local_result_server.publish_tournament(
                self.tournament_id, host.export_service, mode=modo
            )
            host.db.save_app_settings({"local_result_server_url": host.local_result_server.url})
            host._show_info(
                t(
                    "arbitration.export.live.done",
                    url=url,
                    json=(
                        f"{host.local_result_server.url}"
                        f"/api/tournaments/{self.tournament_id}/public?mode={modo}"
                    ),
                )
            )
        except Exception as exc:
            host._show_error(exc)

    # ---- Apoio ------------------------------------------------------------ #

    def _ask_path(self, title: str, suffix: str, filetypes: tuple[tuple[str, str], ...]) -> str:
        host = self.host
        torneio = self.controller.tournament(self.tournament_id)
        base = host._safe_filename(
            (torneio or {}).get("name") or t("arbitration.export.fallback_name"),
            t("arbitration.export.fallback_name"),
        )
        return filedialog.asksaveasfilename(
            title=title,
            initialdir=str(host._default_export_dir()),
            initialfile=base + suffix,
            defaultextension=".pdf",
            filetypes=list(filetypes),
        )

    def _require_tournament(self) -> None:
        if not self.host.current_tournament_id:
            raise self._app_error(t("arbitration.error.no_tournament"))

    @staticmethod
    def _app_error(message: str) -> Exception:
        from src.services.constants import AppError

        return AppError(message)
