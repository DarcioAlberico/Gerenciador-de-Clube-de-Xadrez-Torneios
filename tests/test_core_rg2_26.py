"""RG2-26 — configuração salva não some em silêncio.

``save_app_settings`` descartava, calado, a chave fora da lista: o perfil de
mapeamento de importação e o link do formulário de inscrição "salvavam" e
sumiam. Agora as chaves estão na lista e chave desconhecida é erro de
programação, visível no teste.
"""
from __future__ import annotations

import unittest

from tests.support.core_service_base import CoreServiceTestCase


class ConfiguracaoQueSomeTest(CoreServiceTestCase):
    def test_perfil_de_mapeamento_volta_depois_de_salvo(self) -> None:
        self.import_service.save_mapping_profile("Forms do clube", {"nome": "name", "rating": "rating"})
        self.assertIn("Forms do clube", self.import_service.list_mapping_profiles())

    def test_link_do_formulario_de_inscricao_fica_gravado(self) -> None:
        self.db.save_app_settings(
            {"registration_form_prefill_base": "https://forms.example/x", "registration_form_tournament_entry": "entry.1"}
        )
        ajustes = self.db.get_app_settings()
        self.assertEqual("https://forms.example/x", ajustes["registration_form_prefill_base"])
        self.assertEqual("entry.1", ajustes["registration_form_tournament_entry"])

    def test_chave_desconhecida_levanta_e_nada_e_gravado(self) -> None:
        with self.assertRaisesRegex(ValueError, "x_inexistente"):
            self.db.save_app_settings({"operator_name": "Fulano", "x_inexistente": 1})
        self.assertNotEqual("Fulano", self.db.get_app_settings().get("operator_name"))


if __name__ == "__main__":
    unittest.main()
