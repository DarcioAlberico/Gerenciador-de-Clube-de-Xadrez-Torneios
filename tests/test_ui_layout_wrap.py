"""Contas do layout responsivo (continuação da B-8).

Nenhum abre janela: "quantos cabem em N pixels" é aritmética, e é a aritmética
que decide se um botão fica acessível ou sai da tela. A parte com Tk — medir e
re-``grid``ar — é uma dúzia de linhas em `components/wrap_row.py`.
"""
from __future__ import annotations

import unittest

from src.ui.layout import column_widths, rows_used, wrap_positions


class QuebraTest(unittest.TestCase):
    def test_tudo_numa_linha_quando_cabe(self) -> None:
        posicoes = wrap_positions([100, 100, 100], available=1000, pad=8)
        self.assertEqual([(0, 0), (0, 1), (0, 2)], posicoes)
        self.assertEqual(1, rows_used(posicoes))

    def test_quebra_quando_o_proximo_nao_cabe(self) -> None:
        # 100 + 8 + 100 = 208 cabe em 220; o terceiro pediria 316.
        posicoes = wrap_positions([100, 100, 100], available=220, pad=8)
        self.assertEqual([(0, 0), (0, 1), (1, 0)], posicoes)
        self.assertEqual(2, rows_used(posicoes))

    def test_o_espacamento_conta_na_soma(self) -> None:
        """Sem contar o `pad`, dois itens de 100 "cabem" em 200 e transbordam 8px."""
        self.assertEqual([(0, 0), (1, 0)], wrap_positions([100, 100], available=200, pad=8))
        self.assertEqual([(0, 0), (0, 1)], wrap_positions([100, 100], available=208, pad=8))

    def test_largura_desconhecida_vira_linha_unica(self) -> None:
        """Antes do primeiro desenho tudo mede 1px; quebrar aí é piscar à toa."""
        self.assertEqual([(0, 0), (0, 1)], wrap_positions([500, 500], available=1))
        self.assertEqual([(0, 0), (0, 1)], wrap_positions([500, 500], available=0))

    def test_item_que_sozinho_nao_cabe_fica_numa_linha_propria(self) -> None:
        """Espremer esconde rótulo; sair da janela é o que se quer evitar."""
        posicoes = wrap_positions([300, 100], available=150, pad=8)
        self.assertEqual([(0, 0), (1, 0)], posicoes)

    def test_reserva_desconta_o_que_ja_ocupa_a_faixa(self) -> None:
        """O título da página fica ao lado da barra do torneio e não pode ser
        atropelado — foi o achado que a B-8 corrigiu na barra de 8 botões."""
        self.assertEqual([(0, 0), (0, 1)], wrap_positions([100, 100], available=500, reserve=0))
        self.assertEqual([(0, 0), (1, 0)], wrap_positions([100, 100], available=500, reserve=350))

    def test_lista_vazia_nao_ocupa_linha(self) -> None:
        self.assertEqual([], wrap_positions([], available=500))
        self.assertEqual(0, rows_used([]))

    def test_a_coluna_do_grid_e_do_item_mais_largo_que_caiu_nela(self) -> None:
        """O `grid` não empilha linhas independentes: a coluna tem uma largura
        só. Ignorar isso foi o que pôs o último campo da tela Relatórios 1px
        fora da janela — ele herdava a largura do vizinho de baixo."""
        # 3 por linha: coluna 0 recebe os itens 0 e 3.
        self.assertEqual([200, 50, 60], column_widths([100, 50, 60, 200], per_row=3))

    def test_quebra_leva_em_conta_a_coluna_compartilhada(self) -> None:
        """Somando linha a linha, [100, 50] cabe em 200 e o 200 vai sozinho
        embaixo. No grid não cabe: a coluna 0 passa a valer 200 (por causa do
        item de baixo) e a linha de cima mede 258. Daí três linhas."""
        larguras = [100, 50, 200]
        self.assertEqual([(0, 0), (1, 0), (2, 0)], wrap_positions(larguras, available=200, pad=8))
        # Com folga para a coluna compartilhada, duas linhas voltam a caber.
        self.assertEqual([(0, 0), (0, 1), (1, 0)], wrap_positions(larguras, available=260, pad=8))

    def test_barra_do_torneio_com_8_itens_em_janela_estreita(self) -> None:
        """Caso real da B-8: 8 botões de 112px, título reservando 300px."""
        larguras = [112] * 8
        largos = wrap_positions(larguras, available=1600, pad=6, reserve=300)
        self.assertEqual(1, rows_used(largos), "em janela larga cabe numa linha")
        estreitos = wrap_positions(larguras, available=950, pad=6, reserve=300)
        self.assertGreater(rows_used(estreitos), 1, "em janela estreita quebra")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
