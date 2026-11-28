"""Achado das Fases 1 e 2 da RG2: "Importar Ratings" na tela de membros não fazia nada.

O botão lia um CSV de ratings FIDE/CBX e casava cada linha pelo ``fide_id`` ou
``cbx_id`` do membro — colunas que a tabela ``members`` não tem. O mapa saía
vazio, toda linha era "ignorada" e a tela dizia "0 membros atualizados" sem
explicar por quê; de quebra, "1.850" virava 1. Não há identificador no cadastro
de membro para casar com a lista oficial (nome + nascimento não é seguro), e o
rating oficial já chega ao jogador do torneio pela lista FIDE/CBX/LBX. Por isso
o botão sai, em vez de ganhar um casamento inventado.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from src.services.import_service import ImportService

TELA_DE_MEMBROS = Path(__file__).resolve().parents[1] / "src" / "ui" / "screens" / "club_members_ui.py"


class SemImportacaoQueNaoAtualizaNinguemTest(unittest.TestCase):
    def test_o_servico_nao_oferece_a_importacao_sem_chave(self) -> None:
        self.assertFalse(hasattr(ImportService, "import_rating_list_csv"))

    def test_a_tela_de_membros_nao_tem_o_botao(self) -> None:
        fonte = TELA_DE_MEMBROS.read_text(encoding="utf-8")
        self.assertNotIn("Importar Ratings", fonte)
        self.assertNotIn("import_rating_list_csv", fonte)


if __name__ == "__main__":
    unittest.main()
