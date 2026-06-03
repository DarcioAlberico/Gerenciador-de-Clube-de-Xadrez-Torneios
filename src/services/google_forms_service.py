"""Criacao ao vivo de formularios de inscricao no Google Forms (REG-01).

As dependencias Google (``google-api-python-client`` e ``google-auth-oauthlib``)
e a credencial OAuth do arbitro sao opcionais: quando faltam, o gerador de
formulario cai no script Apps Script (``ExportService.export_registration_form``).
Por isso todos os imports da Google ficam dentro dos metodos (lazy), e o modulo
importa sem essas bibliotecas instaladas.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, TYPE_CHECKING

from src.core.database import app_data_dir
from src.services.constants import AppError
from src.services.export_service import REGISTRATION_FORM_QUESTIONS

if TYPE_CHECKING:
    from src.core.database import Database

logger = logging.getLogger(__name__)

# Escopo minimo para criar e editar o corpo do formulario.
FORMS_SCOPES = ["https://www.googleapis.com/auth/forms.body"]

FORM_DESCRIPTION = "Inscricao gerada pelo Albericus. Preencha os dados do jogador."


class GoogleFormsService:
    def __init__(self, db: Database) -> None:
        self.db = db

    # --- localizacao de credencial/token ---------------------------------

    def _config_dir(self) -> Path:
        path = app_data_dir() / "config"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def client_secret_path(self) -> Path:
        configured = str(
            self.db.get_app_settings().get("google_oauth_client_secret_path") or ""
        ).strip()
        if configured:
            return Path(configured).expanduser()
        return self._config_dir() / "google_client_secret.json"

    def _token_path(self) -> Path:
        return self._config_dir() / "google_forms_token.json"

    # --- disponibilidade --------------------------------------------------

    @staticmethod
    def libraries_available() -> bool:
        try:
            import google.oauth2.credentials  # noqa: F401
            import google_auth_oauthlib.flow  # noqa: F401
            import googleapiclient.discovery  # noqa: F401
        except ImportError:
            return False
        return True

    def is_configured(self) -> bool:
        return self.libraries_available() and self.client_secret_path().exists()

    def unavailable_reason(self) -> str:
        if not self.libraries_available():
            return (
                "Bibliotecas Google ausentes. Instale com: pip install "
                "google-api-python-client google-auth-oauthlib"
            )
        if not self.client_secret_path().exists():
            return (
                "Credencial OAuth nao encontrada em "
                f"{self.client_secret_path()}. Veja docs/GUIA_GOOGLE_FORMS.md."
            )
        return ""

    # --- criacao ----------------------------------------------------------

    def create_registration_form(
        self, title: str, questions: list[dict[str, Any]] | None = None
    ) -> dict[str, str]:
        reason = self.unavailable_reason()
        if reason:
            raise AppError(reason)
        questions = questions if questions is not None else REGISTRATION_FORM_QUESTIONS
        credentials = self._get_credentials(self.client_secret_path())
        service = self._build_service(credentials)
        return self._create_form(service, title, questions)

    def _get_credentials(self, secret_path: Path) -> Any:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow

        token_path = self._token_path()
        creds = None
        if token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(token_path), FORMS_SCOPES)
            except Exception:
                logger.warning("Token Google invalido em %s; refazendo login", token_path)
                creds = None

        if creds and creds.valid:
            return creds
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                token_path.write_text(creds.to_json(), encoding="utf-8")
                return creds
            except Exception:
                logger.warning("Falha ao renovar token Google; refazendo login")

        flow = InstalledAppFlow.from_client_secrets_file(str(secret_path), FORMS_SCOPES)
        creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")
        return creds

    @staticmethod
    def _build_service(credentials: Any) -> Any:
        from googleapiclient.discovery import build

        return build("forms", "v1", credentials=credentials, cache_discovery=False)

    def _create_form(
        self, service: Any, title: str, questions: list[dict[str, Any]]
    ) -> dict[str, str]:
        created = (
            service.forms()
            .create(body={"info": {"title": title, "documentTitle": title}})
            .execute()
        )
        form_id = created["formId"]
        requests = self.build_form_requests(questions)
        if requests:
            service.forms().batchUpdate(
                formId=form_id, body={"requests": requests}
            ).execute()
        form = service.forms().get(formId=form_id).execute()
        responder_url = form.get("responderUri", "")
        edit_url = f"https://docs.google.com/forms/d/{form_id}/edit"
        logger.info("Formulario Google Forms criado ao vivo: %s", form_id)
        return {"form_id": form_id, "responder_url": responder_url, "edit_url": edit_url}

    @staticmethod
    def build_form_requests(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Monta os requests do ``batchUpdate`` (descricao + perguntas).

        Funcao pura: nao depende das bibliotecas Google, o que permite testar o
        payload sem credencial nem rede.
        """
        requests: list[dict[str, Any]] = [
            {
                "updateFormInfo": {
                    "info": {"description": FORM_DESCRIPTION},
                    "updateMask": "description",
                }
            }
        ]
        for index, question in enumerate(questions):
            item_question: dict[str, Any] = {"required": bool(question.get("required"))}
            qtype = question.get("type")
            if qtype == "date":
                item_question["dateQuestion"] = {"includeYear": True}
            elif qtype == "choice":
                item_question["choiceQuestion"] = {
                    "type": "RADIO",
                    "options": [{"value": str(choice)} for choice in question.get("choices", [])],
                }
            else:
                item_question["textQuestion"] = {"paragraph": False}
            requests.append(
                {
                    "createItem": {
                        "item": {
                            "title": str(question["title"]),
                            "questionItem": {"question": item_question},
                        },
                        "location": {"index": index},
                    }
                }
            )
        return requests
