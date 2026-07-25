"""Testes do registro de destinos e do ``Navigator`` (``src/ui/navigation.py``).

Todo este arquivo roda **sem Tk**: o registro é dado puro e o ``Navigator``
conversa com o host por ``getattr``, então um objeto de mentira basta. É esse o
ganho da F1.3 — navegação testável sem subir a aplicação.
"""
from __future__ import annotations

import unittest

from src.ui import navigation
from src.ui.navigation import DESTINATIONS, Navigator, by_group, find, search


class HostFalso:
    """Imita a aplicação: guarda quais telas foram abertas."""

    def __init__(self, *, quebrar: str = "") -> None:
        self.abertas: list[str] = []
        self._quebrar = quebrar

    def __getattr__(self, nome: str):
        if not nome.startswith("show_") or nome == self._quebrar:
            raise AttributeError(nome)

        def abrir() -> None:
            self.abertas.append(nome)

        return abrir


class RegistroTest(unittest.TestCase):
    def test_chaves_e_metodos_sao_unicos(self) -> None:
        chaves = [d.key for d in DESTINATIONS]
        metodos = [d.method for d in DESTINATIONS]
        self.assertEqual(len(chaves), len(set(chaves)), "chave duplicada no registro")
        self.assertEqual(len(metodos), len(set(metodos)), "metodo duplicado no registro")

    def test_todo_destino_aponta_para_um_show(self) -> None:
        for destino in DESTINATIONS:
            self.assertTrue(
                destino.method.startswith("show_"),
                f"{destino.key} aponta para {destino.method}",
            )

    def test_todo_destino_existe_na_aplicacao(self) -> None:
        """Guarda contra destino órfão: renomear um show_* sem atualizar o registro."""
        from src.ui.app import AlbericusApp

        for destino in DESTINATIONS:
            self.assertTrue(
                hasattr(AlbericusApp, destino.method),
                f"registro aponta para {destino.method}, que nao existe em AlbericusApp",
            )

    def test_find_aceita_chave_ou_metodo(self) -> None:
        por_chave = find("pairings")
        por_metodo = find("show_pairings")
        self.assertIsNotNone(por_chave)
        self.assertIs(por_chave, por_metodo)
        self.assertIsNone(find("nao-existe"))

    def test_grupos_preservam_a_ordem_do_registro(self) -> None:
        grupos = by_group()
        self.assertIn("Torneio", grupos)
        rotulos = [d.label for d in grupos["Torneio"]]
        self.assertLess(
            rotulos.index("Torneios"), rotulos.index("Classificação"),
            "a ordem do registro define a ordem de exibicao",
        )


class BuscaTest(unittest.TestCase):
    def test_busca_vazia_devolve_tudo(self) -> None:
        self.assertEqual(len(DESTINATIONS), len(search("")))
        self.assertEqual(len(DESTINATIONS), len(search("   ")))

    def test_busca_por_rotulo(self) -> None:
        achados = [d.key for d in search("jogadores")]
        self.assertIn("players", achados)

    def test_busca_por_palavra_chave(self) -> None:
        achados = [d.key for d in search("trf16")]
        self.assertEqual(["export"], achados)

    def test_busca_ignora_acento_e_caixa(self) -> None:
        """Quem digita 'classificacao' tem de achar 'Classificação'."""
        self.assertIn("standings", [d.key for d in search("CLASSIFICACAO")])
        self.assertIn("standings", [d.key for d in search("classificação")])

    def test_busca_sem_resultado(self) -> None:
        self.assertEqual([], search("xyzzy-nao-existe"))


class NavigatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.host = HostFalso()
        self.nav = Navigator(self.host)

    def test_comeca_sem_tela_atual(self) -> None:
        self.assertIsNone(self.nav.current)
        self.assertIsNone(self.nav.current_destination)
        self.assertFalse(self.nav.refresh_current(), "sem tela, nao ha o que recarregar")

    def test_go_por_chave_e_por_metodo(self) -> None:
        self.assertTrue(self.nav.go("pairings"))
        self.assertTrue(self.nav.go("show_standings"))
        self.assertEqual(["show_pairings", "show_standings"], self.host.abertas)
        self.assertEqual("show_standings", self.nav.current)
        self.assertEqual("standings", self.nav.current_destination.key)

    def test_go_para_destino_inexistente_devolve_false(self) -> None:
        self.assertFalse(self.nav.go("nao_existe"))
        self.assertEqual([], self.host.abertas)
        self.assertIsNone(self.nav.current, "destino invalido nao pode virar tela atual")

    def test_go_quando_o_metodo_falta_no_host(self) -> None:
        """Destino no registro, método ausente no app: não pode explodir."""
        nav = Navigator(HostFalso(quebrar="show_pairings"))
        self.assertFalse(nav.go("pairings"))

    def test_refresh_current_reabre_a_mesma_tela(self) -> None:
        self.nav.go("members")
        self.assertTrue(self.nav.refresh_current())
        self.assertEqual(["show_members", "show_members"], self.host.abertas)

    def test_record_anota_tela_aberta_por_fora(self) -> None:
        """Botão que chama show_* direto: o F5 ainda tem de saber onde estamos."""
        self.nav.record("show_finance")
        self.assertEqual("show_finance", self.nav.current)
        self.assertTrue(self.nav.refresh_current())
        self.assertEqual(["show_finance"], self.host.abertas)

    def test_record_ignora_o_que_nao_e_tela(self) -> None:
        self.nav.go("club")
        self.nav.record("_clear_content")
        self.nav.record("qualquer_helper")
        self.assertEqual("show_club", self.nav.current, "so show_* muda a tela atual")

    def test_navigator_nao_segura_widget(self) -> None:
        """Guarda só o nome — é o que faz a tela sobreviver a rebuild/troca de tema."""
        self.nav.go("club")
        self.assertIsInstance(self.nav.current, str)


class PaletteDerivaDoRegistroTest(unittest.TestCase):
    def test_modulo_nao_depende_de_tk(self) -> None:
        """navigation.py tem de ser importável sem janela — é o ponto da F1.3."""
        self.assertFalse(hasattr(navigation, "ctk"))


class AppShellTest(unittest.TestCase):
    """F1.4: a aplicação sobe pela casca, e os mixins legados seguem no lugar.

    Tudo aqui é inspeção de classe — não abre janela.
    """

    def test_app_herda_a_casca(self) -> None:
        from src.ui.app import AlbericusApp
        from src.ui.shell import AppShell

        self.assertIn(AppShell, AlbericusApp.__mro__)

    def test_casca_e_dona_da_cromagem_da_janela(self) -> None:
        from src.ui.app import AlbericusApp

        for metodo in (
            "_build_content",
            "_clear_content",
            "_build_statusbar",
            "_refresh_statusbar",
            "_register_shortcuts",
            "_show_command_palette",
            "_show_toast",
            "_navigate",
            "_refresh_current_view",
        ):
            dono = getattr(AlbericusApp, metodo).__qualname__.split(".")[0]
            self.assertEqual("AppShell", dono, f"{metodo} deveria vir da casca")

    def test_mixins_legados_continuam_montando_as_telas(self) -> None:
        """A casca é fina: ela não pode ter absorvido as telas."""
        from src.ui.app import AlbericusApp
        from src.ui.shell import AppShell

        telas = [nome for nome in dir(AppShell) if nome.startswith("show_")]
        self.assertEqual([], telas, "a casca nao pode conhecer tela")

        for metodo in ("show_pairings", "show_members", "show_tournaments"):
            dono = getattr(AlbericusApp, metodo).__qualname__.split(".")[0]
            self.assertTrue(dono.endswith("Mixin"), f"{metodo} vem de {dono}")

    def test_casca_nao_importa_telas(self) -> None:
        """Se a casca importasse screens/, voltaria a ser o nó do acoplamento."""
        import pathlib

        codigo = pathlib.Path("src/ui/shell.py").read_text(encoding="utf-8")
        self.assertNotIn("from .screens", codigo)
        self.assertNotIn("import screens", codigo)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
