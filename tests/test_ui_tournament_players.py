"""Tela de Jogadores em camadas (B-6, molde da F1.5).

**Nenhum destes abre janela.** Antes, tudo o que se testa aqui vivia dentro de
closures de `show_players` — 1.613 linhas em que a única forma de exercitar "o
que acontece quando o rating vem 'abc'" era digitar na janela e olhar.

Os casos que mais valem:

- `test_rating_nao_numerico_vira_recado_e_nao_erro_inesperado`: `int("abc")`
  subia como `ValueError` e a tela dizia "Erro inesperado" com código de log —
  para um erro de digitação previsível;
- `test_autofill_nao_sobrescreve_o_que_o_operador_digitou`: a base oficial
  completa o que falta, nunca corrige o que já está lá;
- `test_resumo_conta_todos_e_visiveis_conta_o_filtro`: os dois números saem da
  **mesma** varredura, então não podem discordar.
"""
from __future__ import annotations

import unittest
from typing import Any

from src.services.constants import AppError
from src.ui.screens.tournament_players.controller import TournamentPlayersController
from src.ui.screens.tournament_players.state import (
    PLAYER_FIELDS,
    PlayerForm,
    PlayersSummary,
    autofill_updates,
    field_labels,
    form_from_player,
    matches,
    normalize_scheveningen_group,
    parse_rating,
    scheveningen_labels,
    summarize,
)


def jogador(**campos: Any) -> dict[str, Any]:
    """Registro de jogador com o mínimo que o banco sempre devolve."""
    base = {
        "id": 1,
        "name": "Ana",
        "given_name": "Ana",
        "surname": "Silva",
        "club": "Clube A",
        "category": "ABS",
        "rating": 1800,
        "active": 1,
        "player_status": "active",
    }
    base.update(campos)
    return base


class BancoFalso:
    def __init__(self, jogadores: list[dict[str, Any]] | None = None) -> None:
        self.jogadores = jogadores or []
        self.socios: list[dict[str, Any]] = []
        self.oficiais: dict[tuple[str, str], dict[str, Any]] = {}
        self.criados: list[dict[str, Any]] = []
        self.atualizados: list[tuple[int, dict[str, Any]]] = []
        self.status: list[tuple[int, str]] = []
        self.grupos: list[tuple[int, str]] = []

    def list_players(self, tournament_id: int, active_only: bool = True) -> list[dict[str, Any]]:
        return self.jogadores

    def get_player(self, player_id: int) -> dict[str, Any] | None:
        return next((j for j in self.jogadores if j["id"] == player_id), None)

    def list_members_for_tournament(self, tournament_id: int, **kwargs: Any) -> list[dict[str, Any]]:
        return self.socios

    def find_latest_official_player(self, **params: Any) -> dict[str, Any] | None:
        (chave, valor), = params.items()
        return self.oficiais.get((chave, valor))

    def create_player(self, tournament_id: int, **payload: Any) -> int:
        self.criados.append({"tournament_id": tournament_id, **payload})
        return 99

    def update_player(self, player_id: int, **payload: Any) -> None:
        self.atualizados.append((player_id, payload))

    def set_player_status(self, player_id: int, status: str) -> None:
        self.status.append((player_id, status))

    def set_player_scheveningen_group(self, player_id: int, group: str) -> None:
        self.grupos.append((player_id, group))


class ServicoFalso:
    def __init__(self) -> None:
        self.chamadas: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def __getattr__(self, nome: str) -> Any:
        def registrar(*args: Any, **kwargs: Any) -> dict[str, Any]:
            self.chamadas.append((nome, args, kwargs))
            return {"registered": 2, "skipped": 1}

        return registrar


def controlador(banco: BancoFalso) -> tuple[TournamentPlayersController, ServicoFalso, ServicoFalso]:
    socios, pareamento = ServicoFalso(), ServicoFalso()
    return (
        TournamentPlayersController(banco, member_service=socios, pairing_service=pareamento),
        socios,
        pareamento,
    )


class FormularioTest(unittest.TestCase):
    def test_nome_vazio_e_o_primeiro_impedimento(self) -> None:
        self.assertEqual("Informe o nome do jogador.", PlayerForm().validation_error())

    def test_formulario_valido_nao_reclama(self) -> None:
        self.assertIsNone(PlayerForm(name="Ana", rating="1800").validation_error())

    def test_rating_vazio_e_zero_e_nao_erro(self) -> None:
        """Cadastrar sem rating é legítimo — jogador novo não tem."""
        self.assertEqual(0, parse_rating(""))
        self.assertIsNone(PlayerForm(name="Ana").validation_error())

    def test_rating_nao_numerico_vira_recado_e_nao_erro_inesperado(self) -> None:
        erro = PlayerForm(name="Ana", rating="mil e oitocentos").validation_error()
        self.assertIsNotNone(erro)
        self.assertIn("Rating principal", str(erro))
        self.assertIsNone(parse_rating("abc"))

    def test_cada_campo_de_rating_se_identifica_no_recado(self) -> None:
        erro = PlayerForm(name="Ana", national_rating="x").validation_error()
        self.assertIn("Rating nacional", str(erro))

    def test_payload_de_criacao_converte_rating_e_zera_federacao(self) -> None:
        payload = PlayerForm(name=" Ana ", rating="1800").create_payload(starting_points=0.5)
        self.assertEqual("Ana", payload["name"], "o nome vai aparado")
        self.assertEqual(1800, payload["rating"])
        self.assertEqual("", payload["federation_id"])
        self.assertEqual(0.5, payload["starting_points"])

    def test_payload_de_atualizacao_preserva_o_que_a_tela_nao_mostra(self) -> None:
        """`active` e `federation_id` não estão no formulário — sobrescrevê-los
        apagaria escolha feita em outra tela."""
        atual = jogador(active=0, federation_id="BRA")
        payload = PlayerForm(name="Ana").update_payload(atual)
        self.assertEqual(0, payload["active"])
        self.assertEqual("BRA", payload["federation_id"])

    def test_formulario_vindo_do_banco_nao_traz_a_palavra_none(self) -> None:
        formulario = form_from_player(jogador(title=None, sex=None))
        self.assertEqual("", formulario.title)
        self.assertEqual("", formulario.sex)

    def test_todo_campo_tem_rotulo_no_catalogo(self) -> None:
        rotulos = field_labels()
        for campo in PLAYER_FIELDS:
            self.assertIn(campo, rotulos)
            self.assertNotIn(".", rotulos[campo], f"{campo} caiu na propria chave")


class AutofillTest(unittest.TestCase):
    OFICIAL = {
        "name": "Ana Oficial",
        "surname": "Oficial",
        "title": "WFM",
        "standard_rating": 1900,
        "national_rating": 1850,
        "cbx_id": "C1",
        "lbx_id": "L1",
        "fide_id": "F1",
    }

    def test_preenche_o_que_esta_vazio(self) -> None:
        atualizacoes = autofill_updates(self.OFICIAL, "fide_id", list(PLAYER_FIELDS))
        self.assertEqual("Ana Oficial", atualizacoes["name"])
        self.assertEqual("1900", atualizacoes["rating"], "rating padrao tem precedencia")
        self.assertEqual("C1", atualizacoes["cbx_id"])

    def test_autofill_nao_sobrescreve_o_que_o_operador_digitou(self) -> None:
        """O que está na tela vence a base: quem digitou, digitou por um motivo."""
        atualizacoes = autofill_updates(self.OFICIAL, "fide_id", ["surname"])
        self.assertEqual({"surname": "Oficial"}, atualizacoes)

    def test_valor_falso_da_base_nao_zera_campo(self) -> None:
        atualizacoes = autofill_updates(
            {"national_rating": 0, "name": ""}, "cbx_id", list(PLAYER_FIELDS)
        )
        self.assertEqual({}, atualizacoes)

    def test_id_digitado_traz_os_outros_ids_conforme_a_origem(self) -> None:
        por_fide = autofill_updates(self.OFICIAL, "fide_id", list(PLAYER_FIELDS))
        self.assertIn("lbx_id", por_fide)
        self.assertNotIn("fide_id", por_fide, "nao reescreve o campo que disparou")

        por_cbx = autofill_updates(self.OFICIAL, "cbx_id", list(PLAYER_FIELDS))
        self.assertIn("fide_id", por_cbx)
        self.assertNotIn("lbx_id", por_cbx, "a base CBX nao conhece o LBX")


class BuscaEResumoTest(unittest.TestCase):
    def test_busca_vazia_mostra_tudo(self) -> None:
        self.assertTrue(matches("", jogador()))

    def test_busca_varre_clube_categoria_e_ids(self) -> None:
        alvo = jogador(club="Clube Norte", fide_id="123456")
        self.assertTrue(matches("norte", alvo), "ignora caixa")
        self.assertTrue(matches("123456", alvo), "acha por FIDE ID")
        self.assertFalse(matches("sul", alvo))

    def test_resumo_conta_todos_e_visiveis_conta_o_filtro(self) -> None:
        jogadores = [
            jogador(id=1, member_id=7),
            jogador(id=2, player_status="withdrawn"),
            jogador(id=3),
        ]
        resumo = summarize(jogadores, visible=1)
        self.assertEqual(3, resumo.total)
        self.assertEqual(1, resumo.visible)
        self.assertEqual(2, resumo.present)
        self.assertEqual(1, resumo.absent)
        self.assertEqual(1, resumo.members)
        self.assertEqual(2, resumo.guests)

    def test_texto_do_resumo_sai_do_catalogo_acentuado(self) -> None:
        texto = PlayersSummary(total=2, visible=2, present=2, members=0).as_text()
        self.assertEqual(
            "Total: 2 | Visíveis: 2 | Presentes: 2 | Ausentes: 0 | Membros: 0 | Convidados: 2",
            texto,
        )


class ScheveningenTest(unittest.TestCase):
    def test_codigo_desconhecido_vira_sem_grupo(self) -> None:
        self.assertEqual("", normalize_scheveningen_group("Z"))
        self.assertEqual("", normalize_scheveningen_group(None))

    def test_codigo_e_saneado_e_nao_recusado(self) -> None:
        self.assertEqual("A", normalize_scheveningen_group(" a "))

    def test_rotulos_cobrem_os_tres_codigos(self) -> None:
        self.assertEqual({"", "A", "B"}, set(scheveningen_labels()))


class ControladorTest(unittest.TestCase):
    def test_linhas_e_resumo_saem_da_mesma_varredura(self) -> None:
        banco = BancoFalso(
            [jogador(id=1, name="Ana", given_name="Ana", surname="Silva"), jogador(id=2, given_name="Bruno", surname="Costa")]
        )
        ctrl, _, _ = controlador(banco)
        linhas, resumo = ctrl.rows(1, query="bruno")
        self.assertEqual(1, len(linhas))
        self.assertEqual(2, resumo.total, "o resumo conta todos, nao so os visiveis")
        self.assertEqual(1, resumo.visible)

    def test_linha_traduz_origem_e_status(self) -> None:
        banco = BancoFalso([jogador(id=1, member_id=5, player_status="withdrawn")])
        ctrl, _, _ = controlador(banco)
        (linha,), _ = ctrl.rows(1)
        self.assertEqual("Membro", linha.source)
        self.assertEqual("Desistente", linha.status)
        self.assertEqual(14, len(linha.as_values()), "a tabela tem 14 colunas")

    def test_convidado_e_o_padrao_de_origem(self) -> None:
        ctrl, _, _ = controlador(BancoFalso([jogador(id=1)]))
        (linha,), _ = ctrl.rows(1)
        self.assertEqual("Convidado", linha.source)

    def test_socio_ja_inscrito_nao_aparece_no_seletor(self) -> None:
        banco = BancoFalso()
        banco.socios = [
            {"id": 1, "name": "Ana", "surname": "Silva", "rating": 1800, "registered_player_id": 7},
            {"id": 2, "name": "Bruno", "surname": "Costa", "rating": 1700, "registered_player_id": None},
        ]
        ctrl, _, _ = controlador(banco)
        opcoes = ctrl.member_options(1)
        self.assertEqual([2], list(opcoes.values()))
        self.assertIn("Costa, Bruno", next(iter(opcoes)))

    def test_socio_sem_clube_ainda_tem_escopo_legivel(self) -> None:
        banco = BancoFalso()
        banco.socios = [
            {"id": 3, "name": "Caio", "surname": "", "rating": 0, "registered_player_id": None}
        ]
        ctrl, _, _ = controlador(banco)
        self.assertIn("Sem clube", next(iter(ctrl.member_options(1))))

    def test_rotulo_do_seletor_acompanha_o_escopo_do_torneio(self) -> None:
        ctrl, _, _ = controlador(BancoFalso())
        self.assertEqual("Membro cadastrado", ctrl.member_source_label(None))
        self.assertEqual("Membro do clube/escola", ctrl.member_source_label({"club_id": 1}))
        self.assertEqual(
            "Membro da turma", ctrl.member_source_label({"club_id": 1, "class_id": 2})
        )

    def test_criar_valida_antes_de_tocar_no_banco(self) -> None:
        banco = BancoFalso()
        ctrl, _, _ = controlador(banco)
        with self.assertRaises(AppError):
            ctrl.create(1, PlayerForm(rating="1800"))
        self.assertEqual([], banco.criados, "nada pode ter sido gravado")

    def test_criar_grava_o_payload_do_formulario(self) -> None:
        banco = BancoFalso()
        ctrl, _, _ = controlador(banco)
        self.assertEqual(99, ctrl.create(1, PlayerForm(name="Ana", rating="1800"), 0.5))
        self.assertEqual(1, banco.criados[0]["tournament_id"])
        self.assertEqual(1800, banco.criados[0]["rating"])
        self.assertEqual(0.5, banco.criados[0]["starting_points"])

    def test_atualizar_jogador_que_sumiu_vira_recado(self) -> None:
        ctrl, _, _ = controlador(BancoFalso())
        with self.assertRaises(AppError):
            ctrl.update(42, PlayerForm(name="Ana"))

    def test_grupo_scheveningen_e_saneado_antes_de_gravar(self) -> None:
        banco = BancoFalso()
        ctrl, _, _ = controlador(banco)
        ctrl.set_scheveningen_group(1, "z")
        self.assertEqual([(1, "")], banco.grupos)

    def test_inscrever_sem_membro_disponivel_vira_recado(self) -> None:
        ctrl, socios, _ = controlador(BancoFalso())
        with self.assertRaises(AppError):
            ctrl.register_member(1, None)
        self.assertEqual([], socios.chamadas, "o servico nem chega a ser chamado")

    def test_inscrever_membro_repassa_o_fora_de_escopo(self) -> None:
        ctrl, socios, _ = controlador(BancoFalso())
        ctrl.register_member(1, 5, allow_out_of_scope=True)
        nome, args, kwargs = socios.chamadas[0]
        self.assertEqual("register_member_in_tournament", nome)
        self.assertEqual((1, 5), args)
        self.assertTrue(kwargs["allow_out_of_scope"])

    def test_excluir_passa_pelo_servico_de_pareamento(self) -> None:
        """Quem sabe se o jogador já jogou é o pareamento, não a tela."""
        ctrl, _, pareamento = controlador(BancoFalso())
        ctrl.delete_if_unpaired(1, 7)
        self.assertEqual(("delete_player_if_unpaired", (1, 7), {}), pareamento.chamadas[0])

    def test_busca_na_base_oficial_ignora_id_em_branco(self) -> None:
        banco = BancoFalso()
        banco.oficiais[("fide_id", "123")] = {"name": "Ana Oficial"}
        ctrl, _, _ = controlador(banco)
        self.assertIsNone(ctrl.official_match("fide_id", "   "))
        self.assertEqual({"name": "Ana Oficial"}, ctrl.official_match("fide_id", " 123 "))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
