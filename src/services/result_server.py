from __future__ import annotations

from html import escape
import threading
from typing import Any

from src.services.constants import AppError, RESULTS
from src.services.qr_result_service import QRResultService


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

    @property
    def url(self) -> str:
        visible_host = "localhost" if self.host in {"0.0.0.0", "::"} else self.host
        return f"http://{visible_host}:{self.port}"

    def start(self) -> str:
        if self._thread and self._thread.is_alive():
            return self.url
        try:
            import uvicorn
            from fastapi import FastAPI, Form
            from fastapi.responses import HTMLResponse, JSONResponse
        except ImportError as exc:
            raise AppError("Instale fastapi e uvicorn para ativar o servidor local de resultados.") from exc

        app = FastAPI(title="Albericus Resultados QR")

        @app.get("/resultado", response_class=HTMLResponse)
        def result_form(token: str) -> str:
            return self._result_form_html(token)

        @app.post("/resultado", response_class=HTMLResponse)
        def submit_result(token: str = Form(...), result: str = Form(...), submitter: str = Form("")) -> str:
            try:
                self.qr_result_service.submit_result(token, result, submitter)
                message = "Resultado enviado. Aguarde aprovacao do arbitro."
            except Exception as exc:
                message = f"Envio recusado: {exc}"
            return self._result_response_html(message)

        @app.get("/", response_class=HTMLResponse)
        def home() -> str:
            if self._export_service is None or self._published_tournament_id is None:
                return "<!doctype html><html><body><h1>Portal Albericus ativo</h1><p>Nenhum torneio publicado.</p></body></html>"
            return self._export_service.live_portal_html(self._published_tournament_id, mode=self._portal_mode)

        @app.get("/portal/{tournament_id}", response_class=HTMLResponse)
        def live_portal(tournament_id: int, mode: str = "") -> str:
            if self._export_service is None:
                return "<!doctype html><html><body><h1>Portal indisponivel</h1></body></html>"
            return self._export_service.live_portal_html(tournament_id, mode=mode or self._portal_mode)

        @app.get("/api/tournaments/{tournament_id}/public")
        def public_json(tournament_id: int, mode: str = "") -> JSONResponse:
            if self._export_service is None:
                return JSONResponse({"error": "portal_not_published"}, status_code=404)
            return JSONResponse(self._export_service.public_tournament_payload(tournament_id, mode=mode or self._portal_mode))

        config = uvicorn.Config(app, host=self.host, port=self.port, log_level="warning")
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self._thread.start()
        return self.url

    def publish_tournament(self, tournament_id: int, export_service: Any, mode: str = "publico") -> str:
        self._published_tournament_id = int(tournament_id)
        self._export_service = export_service
        self._portal_mode = mode or "publico"
        return f"{self.start()}/portal/{int(tournament_id)}?mode={self._portal_mode}"

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
            "<button type='submit'>Enviar para aprovacao</button>"
            "</form></body></html>"
        )

    @staticmethod
    def _result_response_html(message: str) -> str:
        return (
            "<!doctype html><html><head><meta name='viewport' content='width=device-width, initial-scale=1'>"
            "<title>Resultado Albericus</title></head>"
            f"<body><h1>{escape(message)}</h1></body></html>"
        )
