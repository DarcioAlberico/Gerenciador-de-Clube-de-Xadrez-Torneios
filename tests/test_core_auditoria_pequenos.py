"""Quatro defeitos de alta severidade achados na auditoria das áreas novas.

A auditoria de 2026-07-29 cobriu a arbitragem. Clube, certificados e portal
nunca tinham sido auditados, e cada um destes quatro custava dado — ou o
entregava a quem não devia:

1. **A tela de clubes salvava a unidade nova por cima da existente.** O
   formulário abria em branco enquanto o estado interno já apontava para a
   primeira unidade cadastrada: quem digitasse uma unidade nova e salvasse sem
   clicar antes em "Nova unidade" renomeava a antiga e apagava os contatos dela,
   com os membros seguindo junto. O aviso dizia "Unidade salva.".
2. **O rodapé do modelo nunca era impresso.** A tela oferece o campo, o serviço
   valida, o banco grava, o adaptador renderiza o texto — e ninguém o desenhava.
   O diploma saía sem dizer onde nem quando o torneio aconteceu.
3. **O diploma de aula saía sem sobrenome** quando havia presença lançada: a
   consulta de presença ordenava por `m.surname` sem selecioná-lo, e o mesmo
   aluno saía com nome completo ou pela metade conforme o caminho.
4. **O portal deixava o visitante escolher o modo.** As rotas anônimas liam
   `?mode=` da querystring, então qualquer um na rede do salão pedia
   `?mode=privado` e recebia o e-mail do árbitro, os comentários internos e o
   FIDE ID de todos os inscritos.
"""

from __future__ import annotations

import contextlib
import unittest

from src.services.certificates.overlay import render_overlay
from src.services.certificates.palettes import resolve_palette
from src.services.certificates.renderer import (
    CertificateContent,
    RenderOptions,
    render_certificate,
)
from src.services.certificates.styles import CLASSIC
from tests.support.core_service_base import CoreServiceTestCase

RODAPE = "Teresina-PI - 12/06/2026 a 14/06/2026"


class _SondaDeDesenho:
    """Superfície que só anota o texto desenhado — o resto é engolido."""

    width, height = 842.0, 595.0

    def __init__(self) -> None:
        self.textos: list[str] = []

    def __getattr__(self, _nome: str):
        def _nada(*_a, **_k) -> None:
            return None

        return _nada

    def text(self, _x, _y, texto, **_k) -> None:
        self.textos.append(str(texto))

    @contextlib.contextmanager
    def alpha(self, *_a, **_k):
        yield


class RodapeDoDiplomaTest(unittest.TestCase):
    CONTEUDO = CertificateContent(
        title="Certificado",
        name="Ana",
        body="corpo",
        footer=RODAPE,
        signature_left="Organizacao",
        signature_right="Arbitragem",
        verification_code="ABC123",
    )

    def _textos(self, conteudo: CertificateContent) -> list[str]:
        sonda = _SondaDeDesenho()
        render_certificate(
            sonda,
            CLASSIC,
            resolve_palette("classic"),
            conteudo,
            RenderOptions(watermark_enabled=False),
        )
        return sonda.textos

    def test_rodape_sai_no_modo_gerado(self) -> None:
        self.assertIn(RODAPE, self._textos(self.CONTEUDO))

    def test_rodape_fica_entre_assinaturas_e_codigo(self) -> None:
        """Ordem de desenho: o rodapé é o penúltimo texto, antes do código."""
        textos = self._textos(self.CONTEUDO)
        self.assertLess(textos.index("Arbitragem"), textos.index(RODAPE))
        self.assertLess(
            textos.index(RODAPE),
            next(i for i, t in enumerate(textos) if t.startswith("Codigo ")),
        )

    def test_modelo_sem_rodape_nao_desenha_linha_vazia(self) -> None:
        import dataclasses

        textos = self._textos(dataclasses.replace(self.CONTEUDO, footer=""))
        self.assertNotIn("", textos)

    def test_rodape_sai_tambem_no_modo_imagem(self) -> None:
        sonda = _SondaDeDesenho()
        render_overlay(sonda, resolve_palette("classic"), self.CONTEUDO)
        self.assertIn(RODAPE, sonda.textos)


class NomeNoDiplomaDeAulaTest(CoreServiceTestCase):
    """O mesmo aluno saía completo ou pela metade conforme houvesse presença."""

    def setUp(self) -> None:
        super().setUp()
        self.member_id = self.member_service.create_member(
            {"name": "Maria", "surname": "Albuquerque Costa", "status": "active"}
        )
        self.session_id = self.training_service.save_session(
            {"title": "Aula de finais", "date": "2026-06-10", "club_id": "1"}
        )

    def _nomes(self) -> list[str]:
        return [
            str(item.get("name") or "")
            for item in self.certificate_service.training_recipients(
                self.session_id, present_only=False
            )
        ]

    def test_sem_presenca_lancada_o_nome_sai_completo(self) -> None:
        self.assertIn("Maria Albuquerque Costa", self._nomes())

    def _lancar_presenca(self) -> None:
        self.training_service.record_attendance(
            self.session_id, [{"member_id": self.member_id, "status": "present"}]
        )

    def test_com_presenca_lancada_o_nome_continua_completo(self) -> None:
        """Era aqui que o sobrenome sumia."""
        self._lancar_presenca()
        self.assertIn("Maria Albuquerque Costa", self._nomes())

    def test_a_consulta_de_presenca_traz_o_sobrenome(self) -> None:
        self._lancar_presenca()
        linha = self.db.list_session_attendance(self.session_id)[0]
        self.assertEqual("Albuquerque Costa", linha["surname"])


class PortalNaoAceitaModoDoVisitanteTest(CoreServiceTestCase):
    """O modo quem decide é o árbitro, em `publish_tournament`."""

    def setUp(self) -> None:
        super().setUp()
        self.db.save_tournament_settings(
            self.tournament_id,
            {"contact_email": "arbitro@exemplo.com", "comments": "Nota interna do arbitro"},
        )
        self.db.create_player(
            self.tournament_id, name="Ana", fide_id="2900001", cbx_id="12345", rating=1800
        )

    def test_payload_publico_esconde_dado_privado(self) -> None:
        payload = self.export_service.public_tournament_payload(
            self.tournament_id, mode="publico"
        )
        texto = str(payload)
        self.assertNotIn("arbitro@exemplo.com", texto)
        self.assertNotIn("2900001", texto)

    def test_modo_privado_existe_e_realmente_expoe(self) -> None:
        """Guarda do teste acima: se o modo privado nao expusesse nada, o
        teste de vazamento passaria por engano."""
        payload = self.export_service.public_tournament_payload(
            self.tournament_id, mode="privado"
        )
        self.assertIn("arbitro@exemplo.com", str(payload))

    def test_rota_anonima_nao_repassa_o_modo_da_querystring(self) -> None:
        """Rede contra a volta do defeito, lida na FONTE — e de proposito.

        As duas rotas anonimas sao closures dentro de `LocalResultServer.start()`
        e so existem com o uvicorn de pe; testa-las de outro jeito significaria
        subir um servidor HTTP de verdade dentro da suite. O que precisa nunca
        mais acontecer e textual e exato: o modo chegar do parametro. Se alguem
        reescrever `mode=mode or self._portal_mode`, este teste reprova.
        """
        from pathlib import Path

        fonte = Path("src/services/result_server.py").read_text(encoding="utf-8")
        self.assertNotIn("mode=mode or self._portal_mode", fonte)
        # E as TRES rotas de portal (`/`, `/portal/{id}` e o JSON publico)
        # continuam servindo o modo que o arbitro publicou.
        self.assertEqual(3, fonte.count("mode=self._portal_mode"))


class TelaDeClubesNaoSobrescreveTest(CoreServiceTestCase):
    """O serviço por trás do botão: id vazio cria, id preenchido atualiza.

    A tela é coberta pelo `test_ui_layout`; o que se fixa aqui é que criar uma
    unidade nova NÃO passa o id de outra — que era o efeito do formulário em
    branco com o estado interno apontando para a primeira unidade.
    """

    def test_salvar_sem_id_cria_unidade_nova(self) -> None:
        primeiro = self.club_service.save_profile(
            {"name": "Clube Alfa", "city": "Recife", "kind": "club", "active": 1}, None
        )
        segundo = self.club_service.save_profile(
            {"name": "Escola Nova", "city": "Olinda", "kind": "school", "active": 1}, None
        )
        self.assertNotEqual(primeiro, segundo)
        nomes = {item["name"] for item in self.db.list_clubs(active_only=False)}
        self.assertIn("Clube Alfa", nomes)
        self.assertIn("Escola Nova", nomes)

    def test_salvar_com_id_atualiza_a_unidade_apontada(self) -> None:
        clube_id = self.club_service.save_profile(
            {"name": "Clube Alfa", "city": "Recife", "kind": "club", "active": 1}, None
        )
        self.club_service.save_profile(
            {"name": "Clube Alfa Renomeado", "city": "Recife", "kind": "club", "active": 1},
            clube_id,
        )
        clube = self.db.get_club(clube_id)
        self.assertEqual("Clube Alfa Renomeado", clube["name"])
