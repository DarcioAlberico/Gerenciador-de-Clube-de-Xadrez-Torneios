"""Testes do cache de figuras do Dashboard (B-5 / P2-14).

Nenhum destes abre janela: o cache é puro e as figuras são montadas com
``Figure`` (sem pyplot, sem backend Tk). O que precisa ficar travado é o
**contrato da chave** — se um dado que entra no desenho não entra na chave, o
usuário vê número velho, e é exatamente esse o bug que um cache introduz.
"""
from __future__ import annotations

import unittest

from src.ui.charts import (
    ChartPalette,
    FigureCache,
    finance_chart_key,
    members_chart_key,
)
from src.ui.screens.dashboard_figures import (
    build_finance_figure,
    build_members_figure,
)

PALETA = ChartPalette(
    panel="#FFFFFF",
    text="#0F172A",
    sub="#64748B",
    accent="#3B82F6",
    success="#059669",
    warning="#D97706",
    danger="#EF4444",
)
OUTRA_PALETA = ChartPalette(
    panel="#1E293B",
    text="#F1F5F9",
    sub="#94A3B8",
    accent="#38BDF8",
    success="#34D399",
    warning="#FBBF24",
    danger="#F87171",
)

DADOS = {
    "summary": {"total_members": 30, "active_members": 24},
    "defaulters_count": 2,
    "finance_summary": {"paid_amount": 900, "pending_amount": 300, "late_amount": 100},
}


class FigureCacheTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cache = FigureCache(maxsize=2)
        self.construcoes = 0

    def _build(self, marca: str = "fig"):
        def build() -> str:
            self.construcoes += 1
            return marca
        return build

    def test_primeira_chamada_constroi_e_segunda_reaproveita(self) -> None:
        primeira = self.cache.get_or_build("k", self._build())
        segunda = self.cache.get_or_build("k", self._build())
        self.assertIs(primeira, segunda)
        self.assertEqual(self.construcoes, 1)
        self.assertEqual((self.cache.hits, self.cache.misses), (1, 1))

    def test_chave_diferente_constroi_de_novo(self) -> None:
        self.cache.get_or_build("a", self._build("A"))
        self.cache.get_or_build("b", self._build("B"))
        self.assertEqual(self.construcoes, 2)
        self.assertEqual(self.cache.misses, 2)

    def test_estoura_o_limite_descartando_o_mais_antigo(self) -> None:
        self.cache.get_or_build("a", self._build("A"))
        self.cache.get_or_build("b", self._build("B"))
        self.cache.get_or_build("c", self._build("C"))
        self.assertEqual(len(self.cache), 2)
        self.assertNotIn("a", self.cache)
        self.assertIn("c", self.cache)

    def test_uso_renova_a_entrada_e_o_descarte_pega_a_esquecida(self) -> None:
        self.cache.get_or_build("a", self._build("A"))
        self.cache.get_or_build("b", self._build("B"))
        self.cache.get_or_build("a", self._build("A"))  # renova 'a'
        self.cache.get_or_build("c", self._build("C"))
        self.assertIn("a", self.cache)
        self.assertNotIn("b", self.cache)

    def test_clear_esvazia(self) -> None:
        self.cache.get_or_build("a", self._build("A"))
        self.cache.clear()
        self.assertEqual(len(self.cache), 0)
        self.cache.get_or_build("a", self._build("A"))
        self.assertEqual(self.construcoes, 2)

    def test_maxsize_invalido_e_recusado(self) -> None:
        with self.assertRaises(ValueError):
            FigureCache(maxsize=0)


class ChaveDeGraficoTest(unittest.TestCase):
    """A chave tem de mudar sempre que o desenho mudaria — e só então."""

    def test_mesmos_dados_e_mesma_paleta_dao_a_mesma_chave(self) -> None:
        self.assertEqual(
            members_chart_key(DADOS, PALETA), members_chart_key(dict(DADOS), PALETA)
        )
        self.assertEqual(
            finance_chart_key(DADOS, PALETA), finance_chart_key(dict(DADOS), PALETA)
        )

    def test_membros_muda_com_total_ativos_e_inadimplentes(self) -> None:
        base = members_chart_key(DADOS, PALETA)
        for mudanca in (
            {"summary": {"total_members": 31, "active_members": 24}},
            {"summary": {"total_members": 30, "active_members": 25}},
            {"defaulters_count": 3},
        ):
            with self.subTest(mudanca=mudanca):
                self.assertNotEqual(base, members_chart_key({**DADOS, **mudanca}, PALETA))

    def test_financeiro_muda_com_qualquer_das_tres_barras(self) -> None:
        base = finance_chart_key(DADOS, PALETA)
        for campo in ("paid_amount", "pending_amount", "late_amount"):
            with self.subTest(campo=campo):
                mudado = {**DADOS, "finance_summary": {**DADOS["finance_summary"], campo: 42}}
                self.assertNotEqual(base, finance_chart_key(mudado, PALETA))

    def test_troca_de_tema_muda_as_duas_chaves(self) -> None:
        self.assertNotEqual(
            members_chart_key(DADOS, PALETA), members_chart_key(DADOS, OUTRA_PALETA)
        )
        self.assertNotEqual(
            finance_chart_key(DADOS, PALETA), finance_chart_key(DADOS, OUTRA_PALETA)
        )

    def test_dashboard_vazio_nao_estoura(self) -> None:
        self.assertIsNotNone(members_chart_key({}, PALETA))
        self.assertIsNotNone(finance_chart_key({}, PALETA))

    def test_secao_nula_e_tratada_como_ausente(self) -> None:
        """O serviço pode devolver ``None`` no lugar do dicionário."""
        nulo = {"summary": None, "finance_summary": None}
        self.assertEqual(members_chart_key(nulo, PALETA), members_chart_key({}, PALETA))
        self.assertEqual(finance_chart_key(nulo, PALETA), finance_chart_key({}, PALETA))


class MontagemDeFiguraTest(unittest.TestCase):
    def test_membros_desenha_pizza_com_as_cores_da_paleta(self) -> None:
        figura = build_members_figure(DADOS, PALETA)
        eixo = figura.axes[0]
        self.assertEqual(len(eixo.patches), 2)  # ativos + inativos
        self.assertIn("Status dos Membros", eixo.get_title())
        self.assertEqual(figura.get_facecolor(), _rgba(PALETA.panel))

    def test_membros_avisa_inadimplentes_no_titulo(self) -> None:
        self.assertIn("2 inadimplentes", build_members_figure(DADOS, PALETA).axes[0].get_title())
        sem = {**DADOS, "defaulters_count": 0}
        self.assertNotIn("inadimplentes", build_members_figure(sem, PALETA).axes[0].get_title())

    def test_membros_sem_ninguem_cadastrado_diz_sem_dados(self) -> None:
        vazio = {"summary": {"total_members": 0, "active_members": 0}}
        eixo = build_members_figure(vazio, PALETA).axes[0]
        self.assertEqual(len(eixo.patches), 0)
        self.assertIn("Sem dados", [t.get_text() for t in eixo.texts])

    def test_financeiro_desenha_as_tres_barras_na_ordem(self) -> None:
        eixo = build_finance_figure(DADOS, PALETA).axes[0]
        self.assertEqual(len(eixo.patches), 3)
        self.assertEqual(
            [t.get_text() for t in eixo.get_xticklabels()],
            ["Recebido", "Pendente", "Atrasado"],
        )
        self.assertEqual(
            [b.get_facecolor() for b in eixo.patches],
            [_rgba(PALETA.success), _rgba(PALETA.warning), _rgba(PALETA.danger)],
        )

    def test_figura_da_paleta_escura_nao_sai_com_fundo_claro(self) -> None:
        figura = build_finance_figure(DADOS, OUTRA_PALETA)
        self.assertEqual(figura.get_facecolor(), _rgba(OUTRA_PALETA.panel))


class CicloCompletoTest(unittest.TestCase):
    """O caminho que a tela percorre: chave → cache → montagem."""

    def setUp(self) -> None:
        self.cache = FigureCache()
        self.montagens = 0

    def _montar(self, dados: dict, paleta: ChartPalette):
        def build():
            self.montagens += 1
            return build_members_figure(dados, paleta)
        return build

    def test_visita_repetida_sem_mudanca_nao_remonta(self) -> None:
        for _ in range(3):
            self.cache.get_or_build(
                members_chart_key(DADOS, PALETA), self._montar(DADOS, PALETA)
            )
        self.assertEqual(self.montagens, 1)

    def test_dado_novo_remonta(self) -> None:
        self.cache.get_or_build(members_chart_key(DADOS, PALETA), self._montar(DADOS, PALETA))
        novos = {**DADOS, "summary": {"total_members": 31, "active_members": 25}}
        self.cache.get_or_build(members_chart_key(novos, PALETA), self._montar(novos, PALETA))
        self.assertEqual(self.montagens, 2)

    def test_figura_cacheada_ainda_traz_os_numeros_novos_apos_troca_de_tema(self) -> None:
        """Tema novo é chave nova: nada de devolver a figura do tema anterior."""
        clara = self.cache.get_or_build(
            members_chart_key(DADOS, PALETA), self._montar(DADOS, PALETA)
        )
        escura = self.cache.get_or_build(
            members_chart_key(DADOS, OUTRA_PALETA), self._montar(DADOS, OUTRA_PALETA)
        )
        self.assertIsNot(clara, escura)
        self.assertEqual(escura.get_facecolor(), _rgba(OUTRA_PALETA.panel))


def _rgba(cor: str) -> tuple[float, float, float, float]:
    from matplotlib.colors import to_rgba

    return to_rgba(cor)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
