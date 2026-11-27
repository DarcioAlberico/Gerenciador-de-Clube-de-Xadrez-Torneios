"""A marca de prêmio casa com ou sem acento.

O app passou a gerar "Sócio do Clube" (antes "Socio do Clube"). Categoria
cadastrada com a grafia antiga, e jogador gravado com ela, têm de continuar
casando: a marca é escrita à mão pelo árbitro, e acento não muda quem ela é.
"""
from __future__ import annotations

import unittest

from src.services.categories.definition import TAG, CategoryDefinition
from src.services.categories.matching import matches


class MarcaSemAcentoTest(unittest.TestCase):
    def casa(self, marca_da_categoria: str, marcas_do_jogador: str) -> bool:
        categoria = CategoryDefinition(name="Sócios", kind=TAG, tag=marca_da_categoria)
        return matches(categoria, {"prize_tags": marcas_do_jogador}, reference_year=2026)

    def test_categoria_antiga_casa_com_marca_nova(self) -> None:
        self.assertTrue(self.casa("Socio do Clube", "Feminino; Sócio do Clube"))

    def test_categoria_nova_casa_com_jogador_antigo(self) -> None:
        self.assertTrue(self.casa("Sócio do Clube", "Socio do Clube"))

    def test_marca_diferente_continua_fora(self) -> None:
        self.assertFalse(self.casa("Sócio do Clube", "Feminino"))


if __name__ == "__main__":
    unittest.main()
