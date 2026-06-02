"""Publicação de álbum de fotos por FTP (Fase J).

Replica o "upload de fotos/álbuns via FTP" do Swiss-Manager: envia uma pasta de
imagens para um servidor FTP e, opcionalmente, gera um ``index.html`` de galeria.
Coerente com offline-first — é um passo de publicação opcional.

Módulo **puro** (só stdlib ``ftplib``/``html``/``pathlib``). A fábrica de cliente
é injetável (``client_factory``) para permitir testes sem rede.
"""

from __future__ import annotations

import ftplib
import html
from pathlib import Path
from typing import Any, Callable

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}


def list_images(local_dir: str | Path) -> list[Path]:
    """Imagens (ordenadas por nome) na pasta indicada, não recursivo."""
    directory = Path(local_dir)
    if not directory.is_dir():
        return []
    return sorted(
        (item for item in directory.iterdir() if item.is_file() and item.suffix.lower() in IMAGE_SUFFIXES),
        key=lambda item: item.name.lower(),
    )


def build_gallery_html(image_names: list[str], title: str) -> str:
    """HTML simples e responsivo de galeria (referencia as imagens por nome)."""
    safe_title = html.escape(title or "Album de fotos")
    cards = "\n".join(
        f'      <figure><img src="{html.escape(name)}" alt="{html.escape(name)}" loading="lazy">'
        f"<figcaption>{html.escape(name)}</figcaption></figure>"
        for name in image_names
    )
    return (
        "<!DOCTYPE html>\n"
        '<html lang="pt-br">\n<head>\n'
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"  <title>{safe_title}</title>\n"
        "  <style>\n"
        "    body{font-family:system-ui,Arial,sans-serif;margin:0;background:#0b0f19;color:#f1f5f9}\n"
        "    h1{padding:16px 20px;margin:0;font-size:20px}\n"
        "    .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:12px;padding:16px}\n"
        "    figure{margin:0;background:#1e293b;border-radius:10px;overflow:hidden}\n"
        "    img{width:100%;height:160px;object-fit:cover;display:block}\n"
        "    figcaption{padding:6px 8px;font-size:12px;color:#94a3b8;word-break:break-all}\n"
        "  </style>\n</head>\n<body>\n"
        f"  <h1>{safe_title}</h1>\n"
        '  <div class="grid">\n'
        f"{cards}\n"
        "  </div>\n</body>\n</html>\n"
    )


def make_ftp_client(
    config: dict[str, Any],
    client_factory: Callable[[dict[str, Any]], Any] | None = None,
) -> Any:
    """Cria e autentica um cliente FTP a partir da config (ou usa a fábrica injetada)."""
    if client_factory is not None:
        return client_factory(config)

    host = str(config.get("host") or "").strip()
    if not host:
        raise ValueError("Informe o host FTP.")
    try:
        port = int(config.get("port") or 21)
    except (TypeError, ValueError):
        port = 21
    user = str(config.get("user") or "")
    password = str(config.get("password") or "")
    use_tls = bool(config.get("use_tls"))
    passive = bool(config.get("passive", True))

    client: Any = ftplib.FTP_TLS() if use_tls else ftplib.FTP()
    client.connect(host, port, timeout=30)
    client.login(user, password)
    if use_tls:
        client.prot_p()
    client.set_pasv(passive)
    return client


def _ensure_remote_dir(client: Any, remote_dir: str) -> None:
    remote = (remote_dir or "").strip().strip("/")
    if not remote:
        return
    for part in remote.split("/"):
        if not part:
            continue
        try:
            client.cwd(part)
        except ftplib.all_errors:
            client.mkd(part)
            client.cwd(part)


def upload_files(
    client: Any,
    files: list[Path],
    remote_dir: str = "",
    *,
    progress_cb: Callable[[str], None] | None = None,
) -> list[str]:
    """Envia os arquivos para ``remote_dir`` (criado se preciso). Devolve os nomes enviados."""
    _ensure_remote_dir(client, remote_dir)
    uploaded: list[str] = []
    for file_path in files:
        path = Path(file_path)
        with path.open("rb") as handle:
            client.storbinary(f"STOR {path.name}", handle)
        uploaded.append(path.name)
        if progress_cb is not None:
            progress_cb(path.name)
    return uploaded
