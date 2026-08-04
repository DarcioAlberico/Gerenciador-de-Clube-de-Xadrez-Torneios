"""ORG-04 — configuração honesta: flags mortas, mudança estrutural e arquivo.

Uma opção visível que não faz nada é pior do que opção nenhuma: o árbitro marca
e acredita. Seis viviam na tela de configuração sem UM consumidor no código —
`accelerated_system` (o árbitro marcava e achava que tinha acelerado o torneio,
enquanto a aceleração de verdade é `acceleration_method`),
`allow_public_registration` e `allow_player_result_edit` (não existe inscrição
pública nem edição direta: o envio por QR sempre passou pela fila de aprovação),
`hide_color_names`, `show_opponents_in_standings` e `calculate_performance` (a
performance sempre foi calculada).

Além disso: dava para trocar ordem inicial, aceleração ou sequência de
desempates com o torneio em andamento sem aviso e sem rastro — a classificação
publicada mudava sozinha entre uma rodada e outra. E `archived` não arquivava:
o torneio continuava na lista igual aos outros.
"""

from __future__ import annotations

import unittest

from src.services.constants import TOURNAMENT_FLAG_FIELDS, AppError
from tests.support.core_service_base import CoreServiceTestCase

FLAGS_REMOVIDAS = (
    "accelerated_system",
    "allow_public_registration",
    "allow_player_result_edit",
    "hide_color_names",
    "show_opponents_in_standings",
    "calculate_performance",
)


class FlagsInertesTest(unittest.TestCase):
    def test_flags_sem_consumidor_sairam_do_registro(self) -> None:
        for flag in FLAGS_REMOVIDAS:
            with self.subTest(flag=flag):
                self.assertNotIn(flag, TOURNAMENT_FLAG_FIELDS)

    def test_flags_vivas_continuam(self) -> None:
        """As que fazem alguma coisa não podem ter ido junto."""
        for flag in ("allow_dangerous_changes", "disable_bye", "hide_standings",
                     "round_robin_double", "knockout_third_place", "tiebreak_strict",
                     "archived"):
            with self.subTest(flag=flag):
                self.assertIn(flag, TOURNAMENT_FLAG_FIELDS)

    def test_nenhuma_flag_do_registro_esta_sem_uso(self) -> None:
        """Rede contra a proxima flag morta: toda flag tem de ser consumida.

        "Consumida" aqui é ter alguma menção fora do esquema, da migração e da
        persistência — que é exatamente o que faltava às seis removidas.
        """
        from pathlib import Path

        raiz = Path(__file__).resolve().parents[1] / "src"
        ignorados = {"database_schema.py", "legacy_migrations.py", "constants.py"}
        arquivos = [
            caminho
            for caminho in raiz.rglob("*.py")
            if caminho.name not in ignorados and "database_tournament_core" not in caminho.name
        ]
        corpo = "\n".join(caminho.read_text(encoding="utf-8") for caminho in arquivos)
        for flag in sorted(TOURNAMENT_FLAG_FIELDS):
            with self.subTest(flag=flag):
                self.assertIn(flag, corpo, f"flag `{flag}` nao e lida por ninguem")


class ArquivamentoTest(CoreServiceTestCase):
    def test_arquivado_some_da_lista_padrao(self) -> None:
        """Critério de aceite do ORG-04."""
        arquivado = self.db.create_tournament("Arquivado", rounds_count=3)
        self.db.save_tournament_settings(arquivado, {"archived": 1})

        nomes = [item["name"] for item in self.db.list_tournaments()]
        self.assertNotIn("Arquivado", nomes)

    def test_arquivado_reaparece_com_filtro(self) -> None:
        arquivado = self.db.create_tournament("Arquivado", rounds_count=3)
        self.db.save_tournament_settings(arquivado, {"archived": 1})

        nomes = [item["name"] for item in self.db.list_tournaments(include_archived=True)]
        self.assertIn("Arquivado", nomes)

    def test_torneio_comum_continua_na_lista(self) -> None:
        nomes = [item["name"] for item in self.db.list_tournaments()]
        self.assertIn("Torneio teste", nomes)

    def test_lista_traz_a_marca_de_arquivado(self) -> None:
        arquivado = self.db.create_tournament("Arquivado", rounds_count=3)
        self.db.save_tournament_settings(arquivado, {"archived": 1})
        por_nome = {
            item["name"]: item for item in self.db.list_tournaments(include_archived=True)
        }
        self.assertEqual(1, int(por_nome["Arquivado"]["archived"]))
        self.assertEqual(0, int(por_nome["Torneio teste"]["archived"]))


class MudancaEstruturalTest(CoreServiceTestCase):
    """Trocar o que define o torneio no meio dele exige motivo e vira auditoria."""

    def _perfil(self, **settings) -> None:
        self.tournament_service.save_profile(
            self.tournament_id,
            {
                "name": "Torneio teste",
                "scope": "standalone",
                "competition_type": "individual",
                "rounds_count": "5",
                "bye_points": "1",
            },
            settings,
            [],
        )

    def _com_rodada(self) -> None:
        self._create_players(4)
        self.service.generate_next_round(self.tournament_id)

    def test_antes_da_primeira_rodada_muda_sem_cerimonia(self) -> None:
        self._perfil(initial_order="international_then_national")
        settings = self.db.get_tournament_settings(self.tournament_id)
        self.assertEqual("international_then_national", settings["initial_order"])

    def test_depois_da_rodada_1_exige_motivo(self) -> None:
        """Critério de aceite: trocar desempates em andamento gera auditoria."""
        self._com_rodada()
        with self.assertRaises(AppError) as erro:
            self._perfil(initial_order="international_then_national")
        self.assertIn("motivo", str(erro.exception))

    def test_com_motivo_a_mudanca_passa_e_fica_registrada(self) -> None:
        self._com_rodada()
        self.tournament_service.save_profile(
            self.tournament_id,
            {
                "name": "Torneio teste",
                "scope": "standalone",
                "competition_type": "individual",
                "rounds_count": "5",
                "bye_points": "1",
            },
            {"initial_order": "international_then_national"},
            [],
            structural_change_reason="Edital corrigido pela federacao",
        )
        eventos = [
            evento
            for evento in self.db.list_audit_events(tournament_id=self.tournament_id)
            if evento["action"] == "tournament_structural_change"
        ]
        self.assertTrue(eventos)
        self.assertIn("Edital corrigido", str(eventos[0]["reason"]))

    def test_salvar_sem_mudar_nada_nao_pede_motivo(self) -> None:
        """Salvar a tela inteira e rotina; so a MUDANCA e que e estrutural."""
        self._com_rodada()
        atual = self.db.get_tournament_settings(self.tournament_id)
        self._perfil(initial_order=atual["initial_order"])

    def test_desempates_tambem_sao_estruturais(self) -> None:
        self._com_rodada()
        with self.assertRaises(AppError):
            self._perfil(tiebreak_sequence="buchholz")
