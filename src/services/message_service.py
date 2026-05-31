import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import urllib.parse
import webbrowser

class MessageService:
    def __init__(self, smtp_server: str = "", smtp_port: int = 587, smtp_user: str = "", smtp_password: str = ""):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password

    def configure(self, smtp_server: str, smtp_port: int, smtp_user: str, smtp_password: str) -> None:
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password

    def send_email(self, to_email: str, subject: str, body: str) -> bool:
        if not self.smtp_server or not self.smtp_user:
            raise ValueError("Servidor SMTP não configurado.")

        msg = MIMEMultipart()
        msg['From'] = self.smtp_user
        msg['To'] = to_email
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain'))

        try:
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            if self.smtp_password:
                server.login(self.smtp_user, self.smtp_password)
            server.send_message(msg)
            server.quit()
            return True
        except Exception as e:
            raise RuntimeError(f"Erro ao enviar e-mail: {e}")

    def send_bulk_email(self, recipients: list[dict], subject: str, body: str) -> dict:
        """Envia o mesmo e-mail para varios destinatarios. `recipients` e uma
        lista de dicts; cada um precisa da chave 'email' (os demais campos sao
        repassados intactos no resumo, ex.: 'member_id'/'name'). Nunca
        interrompe no meio: um destinatario que falha entra em 'failed' com o
        motivo e o envio continua. Devolve um resumo com contagens e listas."""
        sent: list[dict] = []
        failed: list[dict] = []
        for recipient in recipients:
            email = str(recipient.get("email") or "").strip()
            if not email:
                failed.append({"recipient": recipient, "error": "sem e-mail"})
                continue
            try:
                self.send_email(email, subject, body)
                sent.append(recipient)
            except Exception as exc:
                failed.append({"recipient": recipient, "error": str(exc)})
        return {
            "total": len(recipients),
            "sent": sent,
            "failed": failed,
            "sent_count": len(sent),
            "failed_count": len(failed),
        }

    def generate_whatsapp_link(self, phone_number: str, message: str) -> str:
        """
        Gera um link do WhatsApp (wa.me) para o número e mensagem fornecidos.
        """
        # Limpar o número mantendo apenas os dígitos
        clean_number = "".join(filter(str.isdigit, phone_number))
        if not clean_number.startswith("55"):
            clean_number = "55" + clean_number
        
        encoded_message = urllib.parse.quote(message)
        return f"https://wa.me/{clean_number}?text={encoded_message}"

    def open_whatsapp(self, phone_number: str, message: str) -> None:
        """
        Abre o WhatsApp no navegador padrão.
        """
        link = self.generate_whatsapp_link(phone_number, message)
        webbrowser.open(link)
