"""Testes do lint de acentuação (``scripts/check_ui_accents.py`` — F5.12).

A regra é a **auto-consistência**: o app é quem diz como se escreve cada
palavra. Se "Classificação" aparece no catálogo e "Classificacao" aparece numa
tela, a segunda está errada — sem dicionário, sem biblioteca, e melhorando
sozinha a cada texto novo escrito direito.

Como no lint de convenções, ele é exercitado nos dois sentidos: passa no
repositório como está e **reprova** quando alguém reintroduz o que a F5.12
acabou de tirar.
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "check_ui_accents", RAIZ / "scripts" / "check_ui_accents.py"
)
lint = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(lint)


class RepositorioLimpoTest(unittest.TestCase):
    def test_repositorio_passa_hoje(self) -> None:
        self.assertEqual([], lint.checar_acentos(), "textos visiveis deveriam estar acentuados")

    def test_corpus_nao_esta_vazio(self) -> None:
        """Lint que não lê nada passa sempre — e não vale nada."""
        self.assertGreater(len(lint.corpus()), 500)


class RegraTest(unittest.TestCase):
    """A regra em si, sem depender do estado do repositório."""

    def test_palavra_sem_acento_reprova_quando_o_app_a_acentua(self) -> None:
        textos = [("a", "Classificação final"), ("b", "Ver classificacao")]
        acentuadas = lint.grafias_acentuadas(textos)
        self.assertIn("classificacao", acentuadas)
        self.assertEqual({"Classificação"}, acentuadas["classificacao"])

    def test_placeholder_nao_e_texto_visivel(self) -> None:
        """``{codigo}`` é o **nome do parâmetro** que o ``t()`` preenche.

        Acentuá-lo quebra a chamada — e foi o que a primeira versão deste lint
        tentou fazer, transformando ``t("...", codigo=x)`` em ``{código}``.
        """
        visivel = lint._visivel("Federação {codigo} adicionada.")
        self.assertNotIn("codigo", visivel)
        self.assertIn("Federação", visivel)

    def test_chave_de_busca_fica_de_fora(self) -> None:
        """``nav.*.keywords`` não se lê: digita-se. Sem acento ali é o certo."""
        origens = {origem for origem, _texto in lint._textos_do_catalogo()}
        self.assertFalse(
            [origem for origem in origens if origem.endswith(".keywords")],
            "as chaves de busca nao deveriam entrar no corpus",
        )

    def test_homografo_nao_reprova(self) -> None:
        """"esta mesa" e "está pronto" convivem: a auto-consistência não decide."""
        self.assertIn("esta", lint.HOMOGRAFOS)
        self.assertIn("publico", lint.HOMOGRAFOS)

    def test_palavra_curta_nao_entra(self) -> None:
        # Menos de quatro letras da falso-positivo demais ("pos", "sao" x "são"
        # sao casos em que o contexto manda mais que a grafia).
        self.assertEqual([], lint._PALAVRA.findall("pos sa e"))


class ReprovaRegressaoTest(unittest.TestCase):
    """O ponto do lint: um rótulo já corrigido não pode voltar sem acento."""

    def test_rotulo_novo_sem_acento_reprova(self) -> None:
        tela = lint.UI / "screens" / "home.py"
        original = tela.read_text(encoding="utf-8")
        try:
            tela.write_text(
                original + '\n_teste = ctk.CTkLabel(text="Configuracoes do torneio")\n',
                encoding="utf-8",
            )
            problemas = lint.checar_acentos()
            self.assertTrue(
                any("Configuracoes" in problema for problema in problemas),
                f"deveria reprovar; veio {problemas}",
            )
        finally:
            tela.write_text(original, encoding="utf-8")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
