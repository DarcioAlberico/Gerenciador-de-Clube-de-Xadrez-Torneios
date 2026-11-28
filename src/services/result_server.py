"""Servidor local: formulário do QR e portal ao vivo (RG2-19, RG2-45; D4).

D4 (decidida pelo dono em 2026-11-28): o portal responde na rede local quando
o torneio é publicado — é para os pais na Wi-Fi —, mas só o torneio
publicado e só no modo em que foi publicado. O ``?mode=`` da URL vale só para
esta máquina, e o modo ``privado`` não responde para a rede. O QR impresso usa
o IP da rede, não ``localhost`` (no celular, ``localhost`` é o próprio celular).

Sem ``from __future__ import annotations`` de propósito: o FastAPI lê a
anotação ``Request`` das rotas, importada dentro de ``build_app``.
"""

import socket
from html import escape
import threading
from typing import Any

from src.services.constants import AppError, RESULTS
from src.services.qr_result_service import QRResultService

LOCAL_CLIENTS = frozenset({"127.0.0.1", "::1", "localhost"})
PRIVATE_MODE = "privado"
PRIVACY_HEADERS = {"Cache-Control": "no-store", "X-Frame-Options": "DENY"}


def lan_addresses() -> list[str]:
    """IPs IPv4 desta máquina na rede local (sem loopback nem link-local), o principal primeiro."""
    achados: list[str] = []
    try:
        # UDP não manda pacote no connect: só pergunta ao sistema qual interface sairia.
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sonda:
            sonda.connect(("10.255.255.255", 1))
            achados.append(str(sonda.getsockname()[0]))
    except OSError:
        pass  # sem rota (máquina sem rede): a consulta pelo nome da máquina ainda pode achar
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            achados.append(str(info[4][0]))
    except OSError:
        pass  # nome da máquina sem endereço: fica o que a sonda achou, ou nada
    vistos: list[str] = []
    for endereco in achados:
        if endereco not in vistos and not endereco.startswith(("127.", "169.254.", "0.")):
            vistos.append(endereco)
    return vistos


class LocalResultServer:
    def __init__(self, qr_result_service: QRResultService, host: str = "0.0.0.0", port: int = 8765) -> None:
        self.qr_result_service = qr_result_service
        self.host = host
        self.port = int(port)
        self._server: Any | None = None
        self._thread: threading.Thread | None = None
        self._export_service: Any | None = None
        self._published_tournament_id: int | None = None
        self._portal_mode = "publico"
        # O IP que vai no QR quando a máquina tem mais de um (RG2-45).
        self.advertised_host: str | None = None

    @property
    def url(self) -> str:
        if self.host not in {"0.0.0.0", "::"}:
            return f"http://{self.host}:{self.port}"
        visivel = self.advertised_host or next(iter(lan_addresses()), "") or "127.0.0.1"
        return f"http://{visivel}:{self.port}"

    def portal_mode_for(self, client_host: str, requested: str) -> str | None:
        """O modo que este cliente vê, ou ``None`` se ele não pode ver (RG2-19).

        Nesta máquina o ``?mode=`` vale. Da rede vale só o modo publicado, e
        o ``privado`` não responde.
        """
        if client_host in LOCAL_CLIENTS:
            return requested or self._portal_mode
        return None if self._portal_mode == PRIVATE_MODE else self._portal_mode

    def is_published(self, tournament_id: int) -> bool:
        return self._export_service is not None and self._published_tournament_id == int(tournament_id)

    def start(self) -> str:
        if self._thread and self._thread.is_alive():
            return self.url
        try:
            import uvicorn
        except ImportError as exc:
            raise AppError("Instale fastapi e uvicorn para ativar o servidor local de resultados.") from exc
        app = build_app(self)
        config = uvicorn.Config(app, host=self.host, port=self.port, log_level="warning")
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self._thread.start()
        return self.url

    def publish_tournament(self, tournament_id: int, export_service: Any, mode: str = "publico") -> str:
        """Publica UM torneio, num modo fixo: é só ele que o portal serve (RG2-19)."""
        self._published_tournament_id = int(tournament_id)
        self._export_service = export_service
        self._portal_mode = mode or "publico"
        return f"{self.start()}/portal/{int(tournament_id)}"

    def stop(self) -> None:
        if self._server is not None:
            self._server.should_exit = True

    @staticmethod
    def _result_form_html(token: str) -> str:
        safe_token = escape(token, quote=True)
        options = "".join(
            f'<option value="{escape(item, quote=True)}">{escape(item)}</option>'
            for item in RESULTS
            if item and item != "BYE"
        )
        return (
            "<!doctype html><html><head><meta name='viewport' content='width=device-width, initial-scale=1'>"
            "<title>Resultado Albericus</title>"
            "<style>body{font-family:Arial,sans-serif;margin:24px;max-width:520px}"
            "select,input,button{font-size:18px;width:100%;padding:12px;margin:8px 0}</style></head>"
            "<body><h1>Enviar resultado</h1>"
            "<form method='post' action='/resultado'>"
            f"<input type='hidden' name='token' value='{safe_token}'>"
            f"<select name='result'>{options}</select>"
            "<input name='submitter' placeholder='Nome de quem enviou'>"
            "<button type='submit'>Enviar para aprovação</button>"
            "</form></body></html>"
        )

    @staticmethod
    def _result_response_html(message: str) -> str:
        return (
            "<!doctype html><html><head><meta name='viewport' content='width=device-width, initial-scale=1'>"
            "<title>Resultado Albericus</title></head>"
            f"<body><h1>{escape(message)}</h1></body></html>"
        )


def build_app(server: LocalResultServer) -> Any:
    """O app do servidor, fora de ``start`` para poder ser testado (RG2-19)."""
    try:
        from fastapi import FastAPI, Form, Request
        from fastapi.responses import HTMLResponse, JSONResponse
    except ImportError as exc:
        raise AppError("Instale fastapi e uvicorn para ativar o servidor local de resultados.") from exc

    app = FastAPI(title="Albericus Resultados QR")

    @app.middleware("http")
    async def privacy_headers(request: Request, call_next: Any) -> Any:
        resposta = await call_next(request)
        resposta.headers.update(PRIVACY_HEADERS)
        return resposta

    def _origem(request: Request) -> str:
        return request.client.host if request.client else ""

    @app.get("/resultado", response_class=HTMLResponse)
    def result_form(token: str) -> str:
        return server._result_form_html(token)

    @app.post("/resultado", response_class=HTMLResponse)
    def submit_result(token: str = Form(...), result: str = Form(...), submitter: str = Form("")) -> str:
        try:
            server.qr_result_service.submit_result(token, result, submitter)
            message = "Resultado enviado. Aguarde aprovação do árbitro."
        except Exception as exc:
            message = f"Envio recusado: {exc}"
        return server._result_response_html(message)

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request) -> Any:
        if server._published_tournament_id is None or server._export_service is None:
            return "<!doctype html><html><body><h1>Portal Albericus ativo</h1><p>Nenhum torneio publicado.</p></body></html>"
        modo = server.portal_mode_for(_origem(request), "")
        if modo is None:
            return HTMLResponse(_PRIVATE_HTML, status_code=403)
        return server._export_service.live_portal_html(server._published_tournament_id, mode=modo)

    @app.get("/portal/{tournament_id}", response_class=HTMLResponse)
    def live_portal(tournament_id: int, request: Request, mode: str = "") -> Any:
        if not server.is_published(tournament_id):
            return HTMLResponse(_NOT_PUBLISHED_HTML, status_code=404)
        modo = server.portal_mode_for(_origem(request), mode)
        if modo is None:
            return HTMLResponse(_PRIVATE_HTML, status_code=403)
        return server._export_service.live_portal_html(tournament_id, mode=modo)

    @app.get("/api/tournaments/{tournament_id}/public")
    def public_json(tournament_id: int, request: Request, mode: str = "") -> Any:
        if not server.is_published(tournament_id):
            return JSONResponse({"error": "portal_not_published"}, status_code=404)
        modo = server.portal_mode_for(_origem(request), mode)
        if modo is None:
            return JSONResponse({"error": "portal_private"}, status_code=403)
        return JSONResponse(server._export_service.public_tournament_payload(tournament_id, mode=modo))

    return app


_NOT_PUBLISHED_HTML = "<!doctype html><html><body><h1>Torneio não publicado</h1></body></html>"
_PRIVATE_HTML = "<!doctype html><html><body><h1>Portal privado: abra nesta máquina.</h1></body></html>"
