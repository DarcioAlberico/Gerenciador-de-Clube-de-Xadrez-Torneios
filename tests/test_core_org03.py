"""ORG-03 — agenda e controle de tempo estruturados.

Três defeitos, todos do mesmo tipo: o programa tratava como texto solto coisas
que a operação usa como dado.

1. **O ritmo não entendia a grafia do edital.** `90'+30"` é como o cartaz e o
   regulamento escrevem, e o programa não reconhecia: o TRF25 omitia o registro
   222 e o relatório de rating não sabia classificar o evento.
2. **A agenda só tinha data e hora.** Faltavam local, ritmo por rodada e dia de
   descanso — sem este último, a data seguinte parece rodada atrasada.
3. **Reduzir rodadas apagava a agenda em silêncio** (`_validated_schedule`
   fazia `continue`). Quem publicou a data da rodada 5 e depois reduziu para 3
   perdia a data sem aviso nenhum.

E a tolerância de atraso não existia como configuração — vivia só na cabeça de
quem tinha lido o edital, justamente na hora de declarar ausência.
"""

from __future__ import annotations

import unittest

from src.services.constants import AppError
from src.services.time_control import (
    classify_speed,
    normalized_text,
    parse_time_control,
    total_seconds,
    trf25_descriptor,
)
from tests.support.core_service_base import CoreServiceTestCase


class GrafiaDoRitmoTest(unittest.TestCase):
    def test_grafia_internacional_classifica_e_gera_222(self) -> None:
        """Critério de aceite: `90'+30"` é standard e gera um 222 válido."""
        self.assertEqual("standard", classify_speed("90'+30\""))
        self.assertEqual("5400+30", trf25_descriptor("90'+30\""))
        self.assertEqual(120 * 60, total_seconds(parse_time_control("90'+30\"")))

    def test_grafias_equivalentes_dao_o_mesmo_ritmo(self) -> None:
        for texto in ("90'+30\"", "90+30", "90 min + 30 s"):
            with self.subTest(texto=texto):
                self.assertEqual("5400+30", trf25_descriptor(texto))

    def test_rapido_e_blitz_na_grafia_curta(self) -> None:
        self.assertEqual("rapid", classify_speed("15'+10\""))
        self.assertEqual("blitz", classify_speed("3'+2\""))

    def test_forma_compacta_da_fide(self) -> None:
        """`40/90+30`: 40 lances em 90 min, depois 30 min — 120 no total.

        O `+30` sem marca é PERÍODO em minutos, não incremento. Lido como
        incremento o mesmo texto daria 210 minutos.
        """
        self.assertEqual("40/5400:1800", trf25_descriptor("40/90+30"))
        self.assertEqual(120 * 60, total_seconds(parse_time_control("40/90+30")))

    def test_marca_de_segundos_continua_sendo_incremento(self) -> None:
        self.assertEqual("40/5400+30:5400+30", trf25_descriptor('40/90+30"'))

    def test_texto_irreconhecivel_nao_vira_ritmo_inventado(self) -> None:
        self.assertEqual("", classify_speed("a combinar"))
        self.assertIsNone(trf25_descriptor("a combinar"))

    def test_normalizacao_e_o_unico_tradutor(self) -> None:
        """O TRF25 e o relatório de rating passam pela MESMA normalização."""
        # O espaço em volta do `+` não importa: quem lê é o parser.
        self.assertEqual("90 min+30 s", normalized_text("90'+30\""))
        self.assertEqual("90 min + 30 s", normalized_text("90+30"))


class AgendaTest(CoreServiceTestCase):
    AGENDA = [
        {"round_number": 1, "date": "2026-06-01", "time": "09:00", "venue": "Salao A",
         "time_control": "90'+30\""},
        {"round_number": 2, "date": "2026-06-02", "time": "09:00", "rest_day": 1},
        {"round_number": 3, "date": "2026-06-03", "time": "09:00", "venue": "Salao B"},
    ]

    def _salvar(self, rodadas: str, agenda: list[dict], **kwargs) -> None:
        self.tournament_service.save_profile(
            self.tournament_id,
            {
                "name": "Torneio",
                "scope": "standalone",
                "competition_type": "individual",
                "rounds_count": rodadas,
                "bye_points": "1",
            },
            {},
            agenda,
            **kwargs,
        )

    def test_local_ritmo_e_descanso_sobrevivem(self) -> None:
        self._salvar("3", list(self.AGENDA))
        agenda = {
            int(item["round_number"]): item
            for item in self.db.list_round_schedule(self.tournament_id)
        }
        self.assertEqual("Salao A", agenda[1]["venue"])
        self.assertEqual("90'+30\"", agenda[1]["time_control"])
        self.assertEqual(1, agenda[2]["rest_day"])
        self.assertEqual("Salao B", agenda[3]["venue"])

    def test_rodada_sem_agenda_nasce_vazia_e_nao_quebra(self) -> None:
        self._salvar("3", [])
        agenda = self.db.list_round_schedule(self.tournament_id)
        self.assertEqual([1, 2, 3], [int(item["round_number"]) for item in agenda])
        self.assertEqual([""] * 3, [item["venue"] for item in agenda])

    def test_reduzir_rodadas_com_agenda_exige_confirmacao(self) -> None:
        """Critério de aceite do ORG-03."""
        agenda = list(self.AGENDA) + [
            {"round_number": 4, "date": "2026-06-04", "time": "09:00"},
        ]
        with self.assertRaises(AppError) as erro:
            self._salvar("3", agenda)
        self.assertIn("4", str(erro.exception))
        self.assertIn("Confirme", str(erro.exception))

    def test_reducao_confirmada_apaga_e_audita(self) -> None:
        agenda = list(self.AGENDA) + [
            {"round_number": 4, "date": "2026-06-04", "time": "09:00"},
        ]
        self._salvar("3", agenda, confirm_schedule_loss=True)
        numeros = [
            int(item["round_number"]) for item in self.db.list_round_schedule(self.tournament_id)
        ]
        self.assertEqual([1, 2, 3], numeros)
        acoes = [
            evento["action"]
            for evento in self.db.list_audit_events(tournament_id=self.tournament_id)
        ]
        self.assertIn("schedule_rounds_reduced", acoes)

    def test_rodada_excedente_sem_data_nao_pede_confirmacao(self) -> None:
        """Linha vazia acima do total não é dado que alguém publicou."""
        agenda = list(self.AGENDA) + [{"round_number": 4, "date": "", "time": ""}]
        self._salvar("3", agenda)
        self.assertEqual(3, self.db.get_tournament(self.tournament_id)["rounds_count"])


class ToleranciaDeAtrasoTest(CoreServiceTestCase):
    def test_tolerancia_e_configuravel_e_validada(self) -> None:
        self.db.save_tournament_settings(self.tournament_id, {"late_tolerance_minutes": 15})
        settings = self.db.get_tournament_settings(self.tournament_id)
        self.assertEqual(15, settings["late_tolerance_minutes"])

    def test_tolerancia_negativa_e_recusada(self) -> None:
        with self.assertRaises(AppError):
            self.tournament_service.save_profile(
                self.tournament_id,
                {"name": "T", "rounds_count": "5", "bye_points": "1"},
                {"late_tolerance_minutes": "-5"},
                [],
            )

    def test_tolerancia_chega_ao_painel_do_arbitro(self) -> None:
        """Critério de aceite: a tolerância aparece no painel."""
        self.db.save_tournament_settings(self.tournament_id, {"late_tolerance_minutes": 30})
        painel = self.service.arbitration_dashboard(self.tournament_id)
        self.assertEqual(30, painel["metrics"]["late_tolerance_minutes"])

    def test_padrao_e_zero_como_a_fide(self) -> None:
        painel = self.service.arbitration_dashboard(self.tournament_id)
        self.assertEqual(0, painel["metrics"]["late_tolerance_minutes"])
