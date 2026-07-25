"""Testes do lint de convenções de UI (``scripts/check_ui_conventions.py``).

Um lint que nunca reprova é decoração. Aqui ele é exercitado nos dois sentidos:
passa no repositório como está, e **reprova** quando alguém reintroduz o que a
F1.6 e a F3.3 acabaram de tirar.
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "check_ui_conventions", RAIZ / "scripts" / "check_ui_conventions.py"
)
lint = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(lint)


class RepositorioLimpoTest(unittest.TestCase):
    def test_repositorio_passa_hoje(self) -> None:
        problemas = lint.checar_wildcards() + lint.checar_cores_e_fontes()
        self.assertEqual([], problemas, "o repositorio deveria estar em dia")

    def test_linha_de_base_so_lista_arquivos_existentes(self) -> None:
        for nome in lint.WILDCARD_PERMITIDO:
            self.assertTrue(
                (lint.UI / nome).is_file(), f"{nome} esta na linha de base mas nao existe"
            )


class DeteccaoTest(unittest.TestCase):
    """As regras em si — testadas por padrão, sem depender do estado do repo."""

    def test_hex_embutido_e_pego(self) -> None:
        self.assertTrue(lint._HEX.search('ctk.CTkLabel(text_color="#FF0000")'))

    def test_constante_nomeada_e_permitida(self) -> None:
        self.assertTrue(lint._CONSTANTE.match('PROJETOR_FUNDO = "#000000"'))
        self.assertTrue(lint._CONSTANTE.match('WHATSAPP_VERDE = "#25D366"'))

    def test_atribuicao_comum_nao_conta_como_constante(self) -> None:
        self.assertIsNone(lint._CONSTANTE.match('cor_de_fundo = "#000000"'))

    def test_cor_nomeada_do_tk_e_pega(self) -> None:
        self.assertTrue(lint._CORES_NOMEADAS.search('ctk.CTkLabel(text_color="gray")'))
        self.assertTrue(lint._CORES_NOMEADAS.search("botao.configure(fg_color='red')"))

    def test_tamanho_de_fonte_cravado_e_pego(self) -> None:
        self.assertTrue(lint._FONTE.search("font=ctk.CTkFont(size=18, weight='bold')"))

    def test_token_de_fonte_nao_e_pego(self) -> None:
        self.assertIsNone(lint._FONTE.search("font=ctk.CTkFont(size=SIZE_BODY)"))

    def test_wildcard_e_pego_em_qualquer_profundidade(self) -> None:
        self.assertTrue(lint._WILDCARD.search("from ..support import *"))
        self.assertTrue(lint._WILDCARD.search("from .support import *"))

    def test_import_explicito_nao_e_pego(self) -> None:
        self.assertIsNone(lint._WILDCARD.search("from ..support import AppError, logger"))


class ReprovaRegressaoTest(unittest.TestCase):
    """O ponto do lint: uma tela ja migrada nao pode voltar ao `import *`."""

    def test_wildcard_novo_em_tela_migrada_reprova(self) -> None:
        migrada = lint.UI / "screens" / "home.py"
        original = migrada.read_text(encoding="utf-8")
        try:
            migrada.write_text("from ..support import *\n" + original, encoding="utf-8")
            problemas = lint.checar_wildcards()
            self.assertTrue(
                any("home.py" in problema for problema in problemas),
                f"deveria reprovar; veio {problemas}",
            )
        finally:
            migrada.write_text(original, encoding="utf-8")

    def test_cor_cravada_nova_reprova(self) -> None:
        tela = lint.UI / "screens" / "home.py"
        original = tela.read_text(encoding="utf-8")
        try:
            tela.write_text(original + '\n_teste = ctk.CTkLabel(text_color="#123456")\n', encoding="utf-8")
            problemas = lint.checar_cores_e_fontes()
            self.assertTrue(
                any("cor cravada" in problema for problema in problemas),
                f"deveria reprovar; veio {problemas}",
            )
        finally:
            tela.write_text(original, encoding="utf-8")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
