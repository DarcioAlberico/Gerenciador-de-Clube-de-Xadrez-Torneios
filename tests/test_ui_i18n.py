"""Catálogo de textos da interface (B-3 / P2-12).

O teste que sustenta o desenho é o `test_toda_chave_usada_existe_no_catalogo`.
Chave ausente devolve a **própria chave** — de propósito, para aparecer feia na
tela em vez de se esconder atrás de um texto padrão. Mas "aparecer na tela"
significa aparecer para o **usuário**, e é esse teste que faz aparecer antes,
para quem pode consertar.
"""
from __future__ import annotations

import ast
import json
import pathlib
import unittest

from src.ui.i18n import (
    DEFAULT_LOCALE,
    Catalog,
    catalog_path,
    current_catalog,
    load_catalog,
    set_catalog,
    t,
)

RAIZ = pathlib.Path(__file__).resolve().parents[1]
FONTES = sorted((RAIZ / "src").rglob("*.py"))


def _chaves_usadas() -> dict[str, list[str]]:
    """Toda chamada ``t("chave")`` em ``src/`` → arquivos onde aparece.

    Só literais: ``t(variavel)`` é invisível para esta varredura, e é por isso
    que o módulo registra erro em tempo de execução — as duas redes cobrem
    buracos diferentes.
    """
    achadas: dict[str, list[str]] = {}
    for arquivo in FONTES:
        if "gacrux" in arquivo.parts:
            continue
        try:
            arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover
            continue
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Call):
                continue
            alvo = no.func
            nome = alvo.id if isinstance(alvo, ast.Name) else getattr(alvo, "attr", "")
            if nome != "t" or not no.args:
                continue
            primeiro = no.args[0]
            if isinstance(primeiro, ast.Constant) and isinstance(primeiro.value, str):
                achadas.setdefault(primeiro.value, []).append(arquivo.name)
    return achadas


def _chaves_de_navegacao() -> set[str]:
    """As chaves que o registro de destinos monta em tempo de execução.

    Elas nascem de f-string (``f"nav.{key}.label"``), então a varredura de
    literais não as vê — mas são deriváveis do próprio registro.
    """
    from src.ui.navigation import DESTINATIONS

    chaves: set[str] = set()
    for destino in DESTINATIONS:
        chaves.add(f"nav.{destino.key}.label")
        chaves.add(f"nav.{destino.key}.keywords")
        if destino.group_key:
            chaves.add(f"nav.group.{destino.group_key}")
    return chaves


class CatalogoTest(unittest.TestCase):
    def setUp(self) -> None:
        self.catalogo = load_catalog()

    def test_o_catalogo_padrao_existe_e_nao_esta_vazio(self) -> None:
        self.assertTrue(catalog_path().exists(), f"faltou {catalog_path()}")
        self.assertGreater(len(self.catalogo), 50)

    def test_toda_chave_usada_existe_no_catalogo(self) -> None:
        usadas = set(_chaves_usadas()) | _chaves_de_navegacao()
        ausentes = sorted(chave for chave in usadas if chave not in self.catalogo)
        self.assertEqual(
            [],
            ausentes,
            "chave usada no codigo e ausente do catalogo (apareceria crua na tela): "
            + ", ".join(ausentes),
        )

    def test_catalogo_nao_acumula_chave_orfa(self) -> None:
        """Chave que ninguém usa é texto que ninguém revisa."""
        usadas = set(_chaves_usadas()) | _chaves_de_navegacao()
        orfas = sorted(self.catalogo.keys - usadas)
        self.assertEqual([], orfas, "chave no catalogo sem uso no codigo: " + ", ".join(orfas))

    def test_nenhum_texto_vazio(self) -> None:
        vazias = sorted(k for k in self.catalogo.keys if not self.catalogo.get(k).strip())
        self.assertEqual([], vazias)

    def test_json_e_ordenado_para_o_diff_ser_legivel(self) -> None:
        cru = json.loads(catalog_path().read_text(encoding="utf-8"))
        self.assertEqual(list(cru), sorted(cru), "regenere o catalogo com sort_keys=True")


class ResolucaoTest(unittest.TestCase):
    def tearDown(self) -> None:
        set_catalog(load_catalog())

    def test_devolve_o_texto_da_chave(self) -> None:
        set_catalog(Catalog({"oi": "Olá"}))
        self.assertEqual("Olá", t("oi"))

    def test_chave_ausente_devolve_a_propria_chave(self) -> None:
        """Feio na tela é melhor que errado escondido."""
        set_catalog(Catalog({}))
        self.assertEqual("nao.existe", t("nao.existe"))

    def test_parametros_sao_aplicados(self) -> None:
        set_catalog(Catalog({"oi": "Olá, {nome}"}))
        self.assertEqual("Olá, Ana", t("oi", nome="Ana"))

    def test_parametro_faltando_nao_derruba_a_tela(self) -> None:
        set_catalog(Catalog({"oi": "Olá, {nome}"}))
        self.assertEqual("Olá, {nome}", t("oi"))

    def test_arquivo_ausente_vira_catalogo_vazio_e_nao_excecao(self) -> None:
        """App abrindo com as chaves à mostra é diagnosticável; app não abrindo, não."""
        catalogo = load_catalog("xx_YY", base_dir=RAIZ / "i18n")
        self.assertEqual(0, len(catalogo))

    def test_json_quebrado_tambem_vira_catalogo_vazio(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            pasta = pathlib.Path(tmp)
            (pasta / f"{DEFAULT_LOCALE}.json").write_text("{isto nao e json", encoding="utf-8")
            self.assertEqual(0, len(load_catalog(base_dir=pasta)))

    def test_catalogo_em_uso_e_o_padrao(self) -> None:
        set_catalog(load_catalog())
        self.assertEqual(DEFAULT_LOCALE, current_catalog().locale)


class NavegacaoTraduzidaTest(unittest.TestCase):
    """O registro guarda identidade; o texto vem do catálogo."""

    def test_rotulo_vem_do_catalogo(self) -> None:
        from src.ui.navigation import find

        destino = find("club")
        self.assertIsNotNone(destino)
        self.assertEqual("Perfil do Clube", destino.label)

    def test_trocar_o_catalogo_troca_o_rotulo_sem_tocar_no_registro(self) -> None:
        """A promessa da tarefa: idioma novo = arquivo novo, não caçada a literais."""
        from src.ui.navigation import find

        destino = find("club")
        try:
            set_catalog(Catalog({"nav.club.label": "Club profile"}, "en_US"))
            self.assertEqual("Club profile", destino.label)
        finally:
            set_catalog(load_catalog())
        self.assertEqual("Perfil do Clube", destino.label)

    def test_busca_continua_funcionando_com_o_rotulo_do_catalogo(self) -> None:
        from src.ui.navigation import search

        chaves = [d.key for d in search("classificacao")]
        self.assertIn("standings", chaves)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
