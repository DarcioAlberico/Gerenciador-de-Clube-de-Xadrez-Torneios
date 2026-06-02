"""Serviço de álbum de fotos por FTP (Fase J).

Lê a configuração FTP de ``app_settings`` (senha protegida por DPAPI, como o
``smtp_password``), gera a galeria e publica a pasta de imagens. Sem rede, nada
quebra — é um passo de publicação opcional. A fábrica de cliente é injetável
(testes).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

from src.core.database import Database
from src.services.constants import AppError
from src.services.ftp_publish import (
    build_gallery_html,
    list_images,
    make_ftp_client,
    upload_files,
)

logger = logging.getLogger(__name__)

# Chaves usadas em app_settings; ftp_password é protegida (ver database.py).
CONFIG_KEYS = ("ftp_host", "ftp_port", "ftp_user", "ftp_password", "ftp_remote_dir", "ftp_use_tls", "ftp_passive")


class PhotoAlbumService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def get_config(self) -> dict[str, Any]:
        settings = self.db.get_app_settings()
        return {
            "host": str(settings.get("ftp_host") or ""),
            "port": int(str(settings.get("ftp_port") or "21") or "21"),
            "user": str(settings.get("ftp_user") or ""),
            "password": str(settings.get("ftp_password") or ""),
            "remote_dir": str(settings.get("ftp_remote_dir") or ""),
            "use_tls": str(settings.get("ftp_use_tls") or "0") in ("1", "true", "True"),
            "passive": str(settings.get("ftp_passive") or "1") in ("1", "true", "True"),
        }

    def save_config(self, config: dict[str, Any]) -> None:
        self.db.save_app_settings(
            {
                "ftp_host": str(config.get("host") or "").strip(),
                "ftp_port": str(int(config.get("port") or 21)),
                "ftp_user": str(config.get("user") or ""),
                "ftp_password": str(config.get("password") or ""),
                "ftp_remote_dir": str(config.get("remote_dir") or "").strip(),
                "ftp_use_tls": "1" if config.get("use_tls") else "0",
                "ftp_passive": "1" if config.get("passive", True) else "0",
            }
        )

    def test_connection(
        self,
        config: dict[str, Any] | None = None,
        *,
        client_factory: Callable[[dict[str, Any]], Any] | None = None,
    ) -> bool:
        cfg = config or self.get_config()
        if not cfg.get("host"):
            raise AppError("Informe o host FTP nas configuracoes.")
        try:
            client = make_ftp_client(cfg, client_factory)
            try:
                client.voidcmd("NOOP")
            except Exception:
                pass
            client.quit()
            return True
        except Exception as exc:
            raise AppError(f"Falha na conexao FTP: {exc}") from exc

    def publish_album(
        self,
        local_dir: str | Path,
        *,
        generate_gallery: bool = True,
        progress_cb: Callable[[str], None] | None = None,
        client_factory: Callable[[dict[str, Any]], Any] | None = None,
    ) -> dict[str, Any]:
        directory = Path(local_dir)
        if not directory.is_dir():
            raise AppError("Selecione uma pasta de fotos valida.")
        images = list_images(directory)
        if not images:
            raise AppError("A pasta nao contem imagens (jpg/png/gif/webp).")

        config = self.get_config()
        if not config.get("host"):
            raise AppError("Configure o servidor FTP antes de publicar.")

        files = list(images)
        gallery = False
        if generate_gallery:
            gallery_path = directory / "index.html"
            gallery_path.write_text(
                build_gallery_html([img.name for img in images], directory.name),
                encoding="utf-8",
            )
            files.append(gallery_path)
            gallery = True

        client = make_ftp_client(config, client_factory)
        try:
            uploaded = upload_files(client, files, config.get("remote_dir", ""), progress_cb=progress_cb)
        finally:
            try:
                client.quit()
            except Exception:
                pass

        logger.info("%s arquivos publicados por FTP de %s", len(uploaded), directory)
        return {"uploaded": uploaded, "total": len(uploaded), "gallery": gallery}
