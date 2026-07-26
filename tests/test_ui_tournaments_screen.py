"""Tela de Torneios em três camadas (B-6, molde da F1.5).

**Nenhum destes abre janela** — e esse é o aceite da tarefa. Antes, a validação
do formulário e a montagem das linhas viviam dentro de closures de 300 linhas
em `show_tournaments`, alcançáveis só clicando; agora são função e classe.

O caso que mais vale é `test_escopo_avulso_nao_leva_clube_no_payload`: a tela
*desabilita* clube e turma fora do escopo, mas desabilitar não esvazia — quem
mudasse de ideia depois de escolher um clube criaria um torneio avulso
carregando o clube junto, sem nada na tela denunciando.
"""
from __future__ import annotations

import unittest
from typing import Any

from src.services.constants import AppError
from src.ui.screens.tournaments.controller import TournamentListController
from src.ui.screens.tournaments.state import (
    SCOPE_CLASS,
    SCOPE_CLUB,
    SCOPE_STANDALONE,
    TournamentForm,
    TournamentListState,
    TournamentRow,
    scope_fields,
)

ROTULOS_ESCOPO = {"standalone": "Avulso", "club": "Clube/Escola", "class": "Turma"}
ROTULOS_FORMATO = {"individual": "Individual", "team": "Equipes"}


class BancoFalso:
    def __init__(self, torneios: list[dict[str, Any]] | None = None) -> None:
        self.torneios = torneios or []
        self.clubes: list[dict[str, Any]] = []
        self.turmas: list[dict[str, Any]] = []

    def list_tournaments(self) -> list[dict[str, Any]]:
        return self.torneios

    def list_clubs(self, active_only: bool = True) -> list[dict[str, Any]]:
        return self.clubes

    def list_classes(self, club_id: int | None = None, active_only: bool = True):
        return [t for t in self.turmas if t.get("club_id") == club_id]

    def get_tournament(self, tournament_id: int) -> dict[str, Any] | None:
        return next((t for t in self.torneios if t["id"] == tournament_id), None)


class ServicoFalso:
    def __init__(self) -> None:
        self.criados: list[dict[str, Any]] = []
        self.duplicados: list[tuple[int, str]] = []
        self.excluidos: list[int] = []
        self.divididos: list[tuple[int, str]] = []

    def create_tournament(self, payload: dict[str, Any]) -> int:
        self.criados.append(payload)
        return 42

    def duplicate_tournament(self, tournament_id: int, nome: str) -> int:
        self.duplicados.append((tournament_id, nome))
        return 43

    def delete_tournament(self, tournament_id: int) -> None:
        self.excluidos.append(tournament_id)

    def split_tournament(self, tournament_id: int, grupos: str) -> list[int]:
        self.divididos.append((tournament_id, grupos))
        return [1, 2]


def _controlador(db: BancoFalso, servico: ServicoFalso) -> TournamentListController:
    return TournamentListController(
        db,
        servico,
        import_service=None,
        scope_labels=ROTULOS_ESCOPO,
        competition_labels=ROTULOS_FORMATO,
        scope_key=lambda t: t.get("scope_key", "standalone"),
    )


class FormularioTest(unittest.TestCase):
    def test_nome_vazio_e_o_primeiro_impedimento(self) -> None:
        self.assertEqual("Informe o nome do torneio.", TournamentForm().validation_error())
        self.assertIsNone(TournamentForm(name="Aberto").validation_error())

    def test_so_espacos_conta_como_vazio(self) -> None:
        self.assertIsNotNone(TournamentForm(name="   ").validation_error())

    def test_escopo_de_clube_exige_clube(self) -> None:
        form = TournamentForm(name="Aberto", scope=SCOPE_CLUB)
        self.assertIn("clube", form.validation_error() or "")
        self.assertIsNone(TournamentForm(name="Aberto", scope=SCOPE_CLUB, club_id=1).validation_error())

    def test_escopo_de_turma_exige_clube_e_turma(self) -> None:
        form = TournamentForm(name="Aberto", scope=SCOPE_CLASS, club_id=1)
        self.assertIn("turma", form.validation_error() or "")
        completo = TournamentForm(name="Aberto", scope=SCOPE_CLASS, club_id=1, class_id=7)
        self.assertIsNone(completo.validation_error())

    def test_escopo_avulso_nao_leva_clube_no_payload(self) -> None:
        """A tela desabilita clube/turma fora do escopo — mas desabilitar não
        esvazia. Sem esta regra, quem escolhesse um clube e depois voltasse
        para 'avulso' criaria o torneio carregando o clube junto."""
        form = TournamentForm(name="Aberto", scope=SCOPE_STANDALONE, club_id=9, class_id=3)
        payload = form.payload()
        self.assertIsNone(payload["club_id"])
        self.assertIsNone(payload["class_id"])

    def test_escopo_de_clube_descarta_so_a_turma(self) -> None:
        form = TournamentForm(name="Aberto", scope=SCOPE_CLUB, club_id=9, class_id=3)
        payload = form.payload()
        self.assertEqual(9, payload["club_id"])
        self.assertIsNone(payload["class_id"])

    def test_payload_apara_o_nome(self) -> None:
        self.assertEqual("Aberto", TournamentForm(name="  Aberto  ").payload()["name"])

    def test_valores_padrao_do_formulario(self) -> None:
        form = TournamentForm()
        self.assertEqual("5", form.rounds_count)
        self.assertEqual("1.0", form.bye_points)


class CamposPorEscopoTest(unittest.TestCase):
    """O que a tela habilita tem de casar com o que a validação cobra."""

    def test_avulso_nao_habilita_nada(self) -> None:
        campos = scope_fields(SCOPE_STANDALONE)
        self.assertFalse(campos.club_enabled)
        self.assertFalse(campos.class_enabled)
        self.assertEqual("disabled", campos.club_widget_state)

    def test_clube_habilita_so_o_clube(self) -> None:
        campos = scope_fields(SCOPE_CLUB)
        self.assertTrue(campos.club_enabled)
        self.assertFalse(campos.class_enabled)

    def test_turma_habilita_os_dois(self) -> None:
        campos = scope_fields(SCOPE_CLASS)
        self.assertTrue(campos.club_enabled)
        self.assertTrue(campos.class_enabled)

    def test_habilitado_e_exigido_andam_juntos(self) -> None:
        """Uma regra, duas leituras: nunca cobrar um campo que a tela apagou."""
        for escopo in (SCOPE_STANDALONE, SCOPE_CLUB, SCOPE_CLASS):
            with self.subTest(escopo=escopo):
                campos = scope_fields(escopo)
                form = TournamentForm(name="X", scope=escopo)
                self.assertEqual(campos.club_enabled, form.requires_club())
                self.assertEqual(campos.class_enabled, form.requires_class())


class ControladorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = BancoFalso(
            [
                {
                    "id": 1,
                    "name": "Aberto",
                    "competition_type": "team",
                    "scope_key": "club",
                    "club_name": "Clube A",
                    "class_name": "",
                    "location": "Ginasio",
                    "rounds_count": 7,
                    "status": "running",
                }
            ]
        )
        self.servico = ServicoFalso()
        self.controlador = _controlador(self.db, self.servico)

    def test_linha_traz_os_rotulos_resolvidos(self) -> None:
        linha = self.controlador.rows()[0]
        self.assertEqual("Equipes", linha.competition)
        self.assertEqual("Clube/Escola", linha.scope)
        self.assertEqual(
            (1, "Aberto", "Equipes", "Clube/Escola", "Clube A", "", "Ginasio", "7", "running"),
            linha.as_values(),
        )

    def test_formato_desconhecido_cai_em_individual(self) -> None:
        self.db.torneios[0]["competition_type"] = "xadrez-de-marte"
        self.assertEqual("Individual", self.controlador.rows()[0].competition)

    def test_criar_valida_antes_de_chamar_o_servico(self) -> None:
        with self.assertRaises(AppError):
            self.controlador.create(TournamentForm())
        self.assertEqual([], self.servico.criados, "servico nao pode ser chamado com form invalido")

    def test_criar_repassa_o_payload(self) -> None:
        self.assertEqual(42, self.controlador.create(TournamentForm(name="Novo")))
        self.assertEqual("Novo", self.servico.criados[0]["name"])

    def test_duplicar_com_nome_vazio_usa_o_sugerido(self) -> None:
        """Apertar Enter no diálogo não pode virar torneio sem nome."""
        self.controlador.duplicate(1, "   ")
        self.assertEqual((1, "Aberto - copia"), self.servico.duplicados[0])

    def test_duplicar_torneio_inexistente_reclama(self) -> None:
        with self.assertRaises(AppError):
            self.controlador.duplicate(999, "X")

    def test_nome_para_exibir_cai_no_id_quando_o_registro_sumiu(self) -> None:
        self.assertEqual("Aberto", self.controlador.display_name(1))
        self.assertEqual("999", self.controlador.display_name(999))

    def test_opcoes_de_clube_nunca_ficam_vazias(self) -> None:
        opcoes = self.controlador.club_options({"club": "Clube"})
        self.assertEqual(1, len(opcoes))
        self.assertEqual(1, next(iter(opcoes.values())))

    def test_opcoes_de_clube_listam_o_cadastro(self) -> None:
        self.db.clubes = [{"id": 3, "name": "Escola X", "kind": "school"}]
        opcoes = self.controlador.club_options({"school": "Escola"})
        self.assertEqual({"3 - Escola X (Escola)": 3}, opcoes)

    def test_turmas_sempre_oferecem_sem_turma(self) -> None:
        self.assertEqual({"Sem turma": None}, self.controlador.class_options(None))
        self.db.turmas = [{"id": 5, "name": "Iniciantes", "club_id": 3}]
        self.assertEqual(
            {"Sem turma": None, "5 - Iniciantes": 5}, self.controlador.class_options(3)
        )

    def test_dividir_repassa_a_resposta_aparada(self) -> None:
        self.assertEqual([1, 2], self.controlador.split(1, "  3 "))
        self.assertEqual((1, "3"), self.servico.divididos[0])


class EstadoDaListaTest(unittest.TestCase):
    def setUp(self) -> None:
        self.estado = TournamentListState(
            rows=[
                TournamentRow(1, "A", "Individual", "Avulso", "", "", "", "5", "draft"),
                TournamentRow(2, "B", "Equipes", "Avulso", "", "", "", "7", "running"),
            ]
        )

    def test_acha_a_linha_pelo_id(self) -> None:
        linha = self.estado.row(2)
        self.assertIsNotNone(linha)
        self.assertEqual("B", linha.name)

    def test_id_desconhecido_devolve_nada(self) -> None:
        self.assertIsNone(self.estado.row(99))

    def test_selecionado_acompanha_o_id(self) -> None:
        self.assertIsNone(self.estado.selected)
        self.estado.selected_id = 1
        self.assertEqual("A", self.estado.selected.name)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
