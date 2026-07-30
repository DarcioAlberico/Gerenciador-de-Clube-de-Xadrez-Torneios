"""Telas de arbitragem sem abrir janela (B-6, aceite da F1.5).

Nenhum teste daqui cria widget: exercitam o dado puro de
``screens/pairing_arbitration/state.py``, o controlador (com um banco de
mentira) e o mapa de ações do mixin. Era justamente isso que as 1.527 linhas do
arquivo original tornavam impossível — "o que o painel recomenda quando a
rodada está pronta para fechar" só se descobria abrindo a tela.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path
from typing import Any

from src.services.constants import AppError
from src.ui.screens.pairing_arbitration import state
from src.ui.screens.pairing_arbitration.adjustments import AdjustmentsPage
from src.ui.screens.pairing_arbitration.byes import RequestedByesPage
from src.ui.screens.pairing_arbitration.controller import ArbitrationController
from src.ui.screens.pairing_arbitration.prohibitions import ProhibitionsPage
from src.ui.screens.pairing_arbitration.view import ArbitrationPagesMixin

RAIZ = Path(__file__).resolve().parents[1]


def _chamadas(codigo: str, funcao: str) -> list[str]:
    """Os argumentos de cada ``funcao(...)`` do código, com parênteses balanceados.

    Uma regex ``\\([^)]*\\)`` não serve aqui: metade dos alertas do serviço é
    montada com f-string que **contém** parêntese — ``"resultado(s)"`` —, e a
    varredura ingênua cortava a chamada no meio e perdia justamente a ação.
    """
    trechos: list[str] = []
    for inicio in (m.end() for m in re.finditer(rf"\b{funcao}\(", codigo)):
        profundidade = 1
        posicao = inicio
        while posicao < len(codigo) and profundidade:
            profundidade += {"(": 1, ")": -1}.get(codigo[posicao], 0)
            posicao += 1
        trechos.append(codigo[inicio : posicao - 1])
    return trechos


def _ultimo_literal(argumentos: str) -> str:
    """O último literal entre aspas da chamada — que é onde a ação vai."""
    literais = re.findall(r'"([a-z_]*)"', argumentos)
    return literais[-1] if literais else ""


def metricas(**mudancas: Any) -> dict[str, Any]:
    """Métricas do painel com tudo zerado — o teste liga só o que interessa."""
    base = {
        "rounds_count": 5,
        "generated_rounds": 2,
        "closed_rounds": 1,
        "absent_players": 0,
        "corrections": 0,
        "latest_round_number": 2,
        "pending_results": 0,
        "submitted_results": 0,
        "byes": 0,
        "blocking_issues": 0,
        "ready_to_close": False,
        "can_preview_next_round": False,
        "total_results": 0,
        "resolved_results": 0,
        "round_progress_percent": 0,
        "round_duration_label": "00:12",
        "round_started_label": "19:30",
        "round_clock_status": "em_andamento",
    }
    base.update(mudancas)
    return base


class ProximoPassoTest(unittest.TestCase):
    """A ordem das recomendações **é** a regra de arbitragem."""

    def test_bloqueante_vem_antes_de_tudo(self) -> None:
        passo = state.next_step(metricas(blocking_issues=1, pending_results=3, ready_to_close=True))
        self.assertEqual(state.ACTION_BLOCKING_ISSUES, passo.action)

    def test_resultado_qr_submetido_tambem_bloqueia(self) -> None:
        """Resultado enviado por QR e não revisado é decisão pendente do árbitro."""
        passo = state.next_step(metricas(submitted_results=1, pending_results=3))
        self.assertEqual(state.ACTION_BLOCKING_ISSUES, passo.action)

    def test_lancar_resultado_vem_antes_de_fechar(self) -> None:
        passo = state.next_step(metricas(pending_results=3, ready_to_close=True))
        self.assertEqual(state.ACTION_PENDING_RESULTS, passo.action)
        self.assertIn("3", passo.label)

    def test_fechar_rodada_vem_antes_de_pre_visualizar(self) -> None:
        passo = state.next_step(metricas(ready_to_close=True, can_preview_next_round=True))
        self.assertEqual(state.ACTION_READY_TO_CLOSE, passo.action)
        self.assertIn("2", passo.label)

    def test_sem_nada_pendente_sobra_a_chamada_inicial(self) -> None:
        self.assertEqual(state.ACTION_INITIAL_CALL, state.next_step(metricas()).action)


class CartoesDoPainelTest(unittest.TestCase):
    def test_seis_cartoes_e_todo_destino_conhecido(self) -> None:
        cartoes = state.panel_cards(metricas(pending_results=4, absent_players=2))
        self.assertEqual(6, len(cartoes))
        for cartao in cartoes:
            self.assertIn(cartao.action, state.PANEL_ACTIONS)
        self.assertEqual("1/5", cartoes[0].value)
        self.assertEqual("4", cartoes[1].value)

    def test_rodada_sem_mesas_nao_mostra_barra_de_progresso(self) -> None:
        """``None`` e não ``0.0``: rodada sem mesa não é rodada 0% resolvida."""
        self.assertIsNone(state.progress_ratio(metricas()))
        self.assertAlmostEqual(
            0.5, state.progress_ratio(metricas(total_results=4, round_progress_percent=50))
        )

    def test_progresso_fica_preso_entre_zero_e_um(self) -> None:
        self.assertEqual(1.0, state.progress_ratio(metricas(total_results=1, round_progress_percent=150)))


class LeituraDeCamposTest(unittest.TestCase):
    def test_pontos_aceitam_virgula_e_recusam_texto(self) -> None:
        self.assertEqual(0.0, state.parse_points(""))
        self.assertEqual(-0.5, state.parse_points("-0,5"))
        self.assertEqual(1.0, state.parse_points(" 1.0 "))
        self.assertIsNone(state.parse_points("abc"))

    def test_rodada_recusa_negativo_e_texto(self) -> None:
        self.assertEqual(7, state.parse_round("", 7))
        self.assertEqual(3, state.parse_round("3", 1))
        self.assertIsNone(state.parse_round("-1", 1))
        self.assertIsNone(state.parse_round("x", 1))

    def test_janela_de_rodadas(self) -> None:
        self.assertEqual("2+", state.round_window_label(2, 0))
        self.assertEqual("3", state.round_window_label(3, 3))
        self.assertEqual("1-5", state.round_window_label(1, 5))

    def test_alvo_sem_nome_nao_vira_rotulo_vazio(self) -> None:
        """Sem nome o rótulo ainda identifica: sobra o ``#id``.

        A ordenação é por nome, então o cadastro incompleto sobe para o topo da
        lista — o que é bom: é ele que precisa de atenção do árbitro.
        """
        rotulos = state.targets_by_label([{"id": 2, "name": "Zeca"}, {"id": 1, "name": ""}])
        self.assertEqual([1, 2], list(rotulos.values()))
        self.assertTrue(any("(#1)" in rotulo for rotulo in rotulos))


class FormularioDeAjusteTest(unittest.TestCase):
    def formulario(self, **mudancas: Any) -> state.AdjustmentForm:
        campos: dict[str, Any] = {
            "target_id": 7,
            "round_number": 0,
            "aat_type": "",
            "match_points_text": "",
            "game_points_text": "-1",
            "reason": " atraso ",
        }
        campos.update(mudancas)
        return state.AdjustmentForm(**campos)

    def test_sem_alvo_recusa(self) -> None:
        self.assertTrue(self.formulario(target_id=None).validation_error())

    def test_pontos_invalidos_recusam_com_recado_e_nao_com_excecao(self) -> None:
        erro = self.formulario(game_points_text="abc").validation_error()
        self.assertIn("decimal", erro)

    def test_tudo_zero_e_sem_tipo_recusa(self) -> None:
        erro = self.formulario(game_points_text="0").validation_error()
        self.assertTrue(erro)

    def test_tipo_sozinho_basta(self) -> None:
        self.assertEqual("", self.formulario(game_points_text="", aat_type="W").validation_error())

    def test_payload_individual_zera_a_equipe_e_vice_versa(self) -> None:
        """O que a tela não oferece, o payload não manda.

        Mesma lição da tela de Torneios: desabilitar um campo não o esvazia, e
        um id de equipe viajando num torneio individual grava lixo sem que nada
        na tela denuncie.
        """
        individual = self.formulario().payload()
        self.assertEqual(7, individual["player_id"])
        self.assertIsNone(individual["team_id"])
        self.assertEqual(0.0, individual["match_points"], "match points só existem por equipes")

        equipes = self.formulario(is_team=True, match_points_text="2").payload()
        self.assertEqual(7, equipes["team_id"])
        self.assertIsNone(equipes["player_id"])
        self.assertEqual(2.0, equipes["match_points"])

    def test_motivo_vai_sem_espaco_sobrando(self) -> None:
        self.assertEqual("atraso", self.formulario().payload()["reason"])


class FormularioDeByeTest(unittest.TestCase):
    def test_tipo_fora_de_fhz_recusa(self) -> None:
        formulario = state.RequestedByeForm(target_id=1, round_number=2, bye_type="X", reason="")
        self.assertTrue(formulario.validation_error())

    def test_rodada_ausente_recusa(self) -> None:
        formulario = state.RequestedByeForm(target_id=1, round_number=None, bye_type="H", reason="")
        self.assertTrue(formulario.validation_error())

    def test_valido_passa(self) -> None:
        formulario = state.RequestedByeForm(target_id=1, round_number=2, bye_type="H", reason="x")
        self.assertEqual("", formulario.validation_error())

    def test_recado_muda_com_o_tipo_de_competicao(self) -> None:
        jogador = state.RequestedByeForm(None, 1, "H", "").validation_error()
        equipe = state.RequestedByeForm(None, 1, "H", "", is_team=True).validation_error()
        self.assertNotEqual(jogador, equipe)


class FormularioDeProibicaoTest(unittest.TestCase):
    def formulario(self, **mudancas: Any) -> state.ProhibitionForm:
        campos: dict[str, Any] = {
            "target_a_id": 1,
            "target_b_id": 2,
            "first_round_text": "",
            "last_round_text": "",
            "reason": "",
        }
        campos.update(mudancas)
        return state.ProhibitionForm(**campos)

    def test_mesmo_alvo_dos_dois_lados_recusa(self) -> None:
        self.assertTrue(self.formulario(target_b_id=1).validation_error())

    def test_janela_invertida_recusa(self) -> None:
        erro = self.formulario(first_round_text="5", last_round_text="2").validation_error()
        self.assertTrue(erro)

    def test_rodada_nao_numerica_recusa(self) -> None:
        self.assertTrue(self.formulario(first_round_text="x").validation_error())

    def test_padrao_e_janela_aberta_a_partir_da_primeira(self) -> None:
        formulario = self.formulario()
        self.assertEqual("", formulario.validation_error())
        self.assertEqual({"first_round": 1, "last_round": 0, "reason": ""}, formulario.payload())


class BancoDeMentira:
    """Registra o que foi chamado; devolve o que o teste plantou."""

    def __init__(self, **dados: Any) -> None:
        self.chamadas: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self.dados = dados

    def __getattr__(self, nome: str) -> Any:
        def registrar(*args: Any, **kwargs: Any) -> Any:
            self.chamadas.append((nome, args, kwargs))
            return self.dados.get(nome, [])

        return registrar

    def nomes_chamados(self) -> list[str]:
        return [nome for nome, _args, _kwargs in self.chamadas]


class ControladorTest(unittest.TestCase):
    def controlador(self, **dados: Any) -> tuple[ArbitrationController, BancoDeMentira]:
        db = BancoDeMentira(**dados)
        return ArbitrationController(db, pairing_service=BancoDeMentira()), db

    def test_rodadas_previstas_nao_sao_as_geradas(self) -> None:
        """Bye é declarado antes de a rodada existir — por isso são duas listas."""
        controlador, _db = self.controlador(list_rounds=[{"id": 9, "number": 1}])
        self.assertEqual([1], controlador.generated_rounds(1))
        self.assertEqual([1, 2, 3, 4], controlador.configured_rounds({"rounds_count": 4}))

    def test_alvos_saem_de_equipes_ou_de_jogadores(self) -> None:
        controlador, db = self.controlador(
            list_players=[{"id": 1, "name": "Ana"}], list_teams=[{"id": 5, "name": "Time"}]
        )
        self.assertEqual({"Ana (#1)": 1}, controlador.targets(1, is_team=False))
        self.assertEqual({"Time (#5)": 5}, controlador.targets(1, is_team=True))

    def test_bye_individual_e_de_equipe_chamam_funcoes_diferentes(self) -> None:
        controlador, db = self.controlador()
        controlador.add_bye(1, state.RequestedByeForm(3, 2, "H", "", is_team=False))
        controlador.add_bye(1, state.RequestedByeForm(3, 2, "H", "", is_team=True))
        controlador.delete_bye(8, is_team=True)
        self.assertEqual(
            ["add_requested_bye", "add_requested_team_bye", "delete_requested_team_bye"],
            db.nomes_chamados(),
        )

    def test_proibicao_de_equipe_usa_a_tabela_de_equipes(self) -> None:
        controlador, db = self.controlador()
        controlador.add_prohibition(1, state.ProhibitionForm(1, 2, "", "", "", is_team=True))
        self.assertEqual(["add_prohibited_team_pairing"], db.nomes_chamados())

    def test_formulario_invalido_nao_chega_ao_banco(self) -> None:
        controlador, db = self.controlador()
        with self.assertRaises(AppError):
            controlador.add_adjustment(1, state.AdjustmentForm(None, 0, "", "", "", ""))
        self.assertEqual([], db.nomes_chamados(), "banco nao pode ser tocado por formulario invalido")

    def test_retrato_para_desfazer_sai_da_lista_pelo_id(self) -> None:
        controlador, _db = self.controlador(
            list_point_adjustments=[{"id": 1, "reason": "a"}, {"id": 2, "reason": "b"}]
        )
        self.assertEqual("b", (controlador.find_adjustment(1, 2) or {})["reason"])
        self.assertIsNone(controlador.find_adjustment(1, 99))

    def test_ajuste_lancado_deixa_trilha_com_o_motivo(self) -> None:
        """TBK-01: o ajuste move a classificação, então precisa de auditoria.

        Vai para `audit_events` — a mesma trilha de `round_generated` — porque é
        de lá que o `export_tournament_audit` tira o relatório de auditoria.
        """
        controlador, db = self.controlador()
        controlador.add_adjustment(
            7, state.AdjustmentForm(3, 2, "", "", "-0,5", "Celular tocou")
        )
        self.assertEqual(["add_point_adjustment", "create_audit_event"], db.nomes_chamados())
        _nome, _args, kwargs = db.chamadas[-1]
        self.assertEqual("point_adjustment_added", kwargs["action"])
        self.assertEqual(7, kwargs["tournament_id"])
        self.assertEqual("Celular tocou", kwargs["reason"])
        self.assertIn("-0,5 (rodada 2)", kwargs["metadata"]["summary"])

    def test_exclusao_de_ajuste_tambem_e_auditada(self) -> None:
        """Apagar o ajuste devolve os pontos: é uma decisão como a de lançar."""
        controlador, db = self.controlador(
            list_point_adjustments=[
                {"id": 4, "player_id": 3, "game_points": -0.5, "reason": "Celular tocou",
                 "round_number": 2, "player_name": "Ana"}
            ]
        )
        controlador.delete_adjustment(7, 4)
        self.assertEqual(
            ["list_point_adjustments", "delete_point_adjustment", "create_audit_event"],
            db.nomes_chamados(),
        )
        _nome, _args, kwargs = db.chamadas[-1]
        self.assertEqual("point_adjustment_removed", kwargs["action"])
        self.assertIn("Ana", kwargs["metadata"]["summary"])

    def test_trilha_indisponivel_nao_derruba_o_lancamento(self) -> None:
        """Em pleno salão, problema de registro não pode virar problema de operação."""

        class BancoQueFalhaNaAuditoria(BancoDeMentira):
            def create_audit_event(self, **kwargs: Any) -> int:
                raise RuntimeError("banco ocupado")

        db = BancoQueFalhaNaAuditoria()
        controlador = ArbitrationController(db, pairing_service=BancoDeMentira())
        controlador.add_adjustment(7, state.AdjustmentForm(3, 2, "", "", "-0,5", "Celular"))
        self.assertEqual(["add_point_adjustment"], db.nomes_chamados())

    def test_sem_rodada_gerada_o_pacote_recusa_com_recado(self) -> None:
        controlador, _db = self.controlador(list_rounds=[])
        with self.assertRaises(AppError):
            controlador.latest_round_id(1)

    def test_ultima_rodada_e_a_de_maior_numero_e_nao_a_ultima_inserida(self) -> None:
        controlador, _db = self.controlador(
            list_rounds=[{"id": 7, "number": 3}, {"id": 9, "number": 1}]
        )
        self.assertEqual(7, controlador.latest_round_id(1))


class HostDeMentira:
    """Só os destinos que o mapa de ações usa. Nenhum widget."""

    def __getattr__(self, nome: str) -> Any:
        if nome.startswith(("show_", "_preview", "_close")):
            return lambda *a, **k: nome
        raise AttributeError(nome)


class MapaDeAcoesTest(unittest.TestCase):
    """Deep link quebrado no painel do árbitro é pior que alerta nenhum (F3.2)."""

    def acao(self, chave: str) -> Any:
        return ArbitrationPagesMixin._arbitration_action(HostDeMentira(), chave)

    def test_toda_acao_conhecida_tem_destino(self) -> None:
        for chave in state.PANEL_ACTIONS:
            with self.subTest(action=chave):
                self.assertIsNotNone(self.acao(chave))

    def test_acao_vazia_ou_desconhecida_vira_alerta_sem_botao(self) -> None:
        self.assertIsNone(self.acao(""))
        self.assertIsNone(self.acao("acao_que_nao_existe"))

    def test_toda_acao_que_o_servico_emite_esta_no_mapa(self) -> None:
        """Varre o serviço, e não a lista de constantes.

        Uma lista conferindo a si mesma passaria para sempre. O que precisa ser
        pego é o alerta novo que alguém acrescenta no ``pairing_service`` sem
        dizer para onde ele leva — e aí o árbitro vê o recado e não consegue
        agir sobre ele.
        """
        codigo = (RAIZ / "src" / "services" / "pairing_service.py").read_text(encoding="utf-8")
        emitidas = {_ultimo_literal(argumentos) for argumentos in _chamadas(codigo, "add_alert")}
        emitidas |= set(re.findall(r'"action":\s*"([a-z_]+)"', codigo))
        emitidas.discard("")
        # Oito alertas e o `lineups` do checklist. O número está aqui de
        # propósito: uma varredura que passasse a achar menos (por uma regex
        # que parou de casar, por exemplo) deixaria de guardar o que promete.
        self.assertGreaterEqual(len(emitidas), 9, f"varredura fraca demais: {sorted(emitidas)}")
        for chave in sorted(emitidas):
            with self.subTest(action=chave):
                self.assertIsNotNone(self.acao(chave), f"acao '{chave}' emitida sem destino")


class PaginaDeCadastroTest(unittest.TestCase):
    """As três páginas TRF25 sem Tk: campos, colunas e a ponte com o controlador."""

    def pagina(self, classe: Any, is_team: bool = False, **dados: Any) -> Any:
        db = BancoDeMentira(**dados)
        controlador = ArbitrationController(db, pairing_service=BancoDeMentira())
        torneio = {"name": "Aberto", "rounds_count": 3}
        if is_team:
            torneio["competition_type"] = "team"
        pagina = classe(controlador, 1, torneio)
        pagina.db = db
        return pagina

    def test_ajuste_por_equipes_ganha_o_campo_de_match_points(self) -> None:
        individual = self.pagina(AdjustmentsPage, list_players=[{"id": 1, "name": "Ana"}])
        equipes = self.pagina(AdjustmentsPage, is_team=True, list_teams=[{"id": 1, "name": "T"}])
        chaves_individual = [campo.key for campo in individual.fields()]
        chaves_equipes = [campo.key for campo in equipes.fields()]
        self.assertNotIn("match_points", chaves_individual)
        self.assertIn("match_points", chaves_equipes)

    def test_lista_vazia_vira_rotulo_de_vazio_e_nao_selecao_valida(self) -> None:
        pagina = self.pagina(RequestedByesPage)
        alvo = next(campo for campo in pagina.fields() if campo.key == "target")
        self.assertEqual(1, len(alvo.values))
        self.assertIsNone(pagina.target_id(alvo.values[0]), "rotulo de vazio nao e um alvo")

    def test_proibicao_abre_o_segundo_seletor_em_outro_nome(self) -> None:
        pagina = self.pagina(
            ProhibitionsPage,
            list_players=[{"id": 1, "name": "Ana"}, {"id": 2, "name": "Bia"}],
        )
        campos = {campo.key: campo for campo in pagina.fields()}
        self.assertEqual("", campos["target_a"].initial)
        self.assertEqual(campos["target_b"].values[1], campos["target_b"].initial)

    def test_linha_do_ajuste_mostra_todas_e_sinal_nos_pontos(self) -> None:
        pagina = self.pagina(
            AdjustmentsPage,
            list_players=[{"id": 1, "name": "Ana"}],
            list_point_adjustments=[
                {
                    "id": 4,
                    "round_number": 0,
                    "player_name": "Ana",
                    "aat_type": "",
                    "match_points": 0,
                    "game_points": -0.5,
                    "reason": "atraso",
                }
            ],
        )
        (record_id, valores) = pagina.rows()[0]
        self.assertEqual(4, record_id)
        self.assertEqual("-0.5", valores[4])
        self.assertNotEqual("0", valores[0], "rodada 0 e 'todas', nao a rodada zero")

    def test_alvo_removido_nao_deixa_a_linha_em_branco(self) -> None:
        pagina = self.pagina(
            RequestedByesPage,
            list_requested_byes=[
                {"id": 1, "round_number": 2, "player_name": None, "bye_type": "h", "reason": ""}
            ],
        )
        (_id, valores) = pagina.rows()[0]
        self.assertTrue(valores[1], "sem nome, a linha precisa dizer que o alvo sumiu")
        self.assertEqual("H", valores[2], "o codigo do bye e maiusculo, venha como vier")


if __name__ == "__main__":
    unittest.main()
