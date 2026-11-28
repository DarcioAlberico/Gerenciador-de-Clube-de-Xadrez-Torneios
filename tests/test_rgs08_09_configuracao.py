"""RGS-08 (caso de uso, F1.6) e RGS-09 (F1.7) — salvar configurações.

RGS-08: salvar a tela de Configurações gravava pela metade. ``save_profile``
fazia três gravações com conexão e commit próprios, e depois a tela gravava
prêmios, categorias e colunas em separado: uma linha de prêmio em branco
mostrava "Informe o nome de cada prêmio" com ``allow_dangerous_changes=1`` JÁ
gravado. Agora ``save_tournament_configuration`` valida TUDO sem tocar no banco
e grava tudo numa transação, precedida de backup.

RGS-09: a auditoria (``schedule_rounds_reduced``, mudança estrutural) era
gravada ANTES das recusas. Reduzir rodadas junto com uma mudança de
``initial_order`` caía no laço "Confirme…" → "Informe o motivo…": o total de
rodadas nunca mudava e cada volta gravava mais um ``schedule_rounds_reduced``
falso. Agora ``plan_tournament_configuration`` (pura) devolve TODAS as
confirmações de uma vez, e a auditoria entra na transação, depois das
validações.

A importação TRF passa pela mesma transação: falha no meio não deixa torneio
pela metade.
"""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from typing import Any

from src.services.constants import AppError
from src.services.tournament_configuration import (
    TIPO_AGENDA_PERDIDA,
    TIPO_MUDANCA_ESTRUTURAL,
    TIPO_MUDANCAS_PERIGOSAS,
    Confirmacao,
    PerfilTorneio,
    plan_tournament_configuration,
)
from tests.support.core_service_base import CoreServiceTestCase


class _Falha(RuntimeError):
    pass


def _retrato(db_path: Path) -> dict[str, list[tuple[Any, ...]]]:
    """``SELECT *`` de todas as tabelas, por uma conexão independente.

    As linhas do backup automático (evento ``backup_created``) ficam de fora:
    o aceite admite exatamente esse evento a mais, e ele é contado à parte.
    """
    conexao = sqlite3.connect(db_path)
    try:
        tabelas = [
            str(linha[0])
            for linha in conexao.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        retrato: dict[str, list[tuple[Any, ...]]] = {}
        for tabela in sorted(tabelas):
            linhas = conexao.execute(f'SELECT * FROM "{tabela}" ORDER BY rowid').fetchall()
            retrato[tabela] = [
                tuple(linha) for linha in linhas if "backup_created" not in tuple(linha)
            ]
        return retrato
    finally:
        conexao.close()


def _eventos(db_path: Path, acao: str) -> int:
    conexao = sqlite3.connect(db_path)
    try:
        return int(
            conexao.execute("SELECT COUNT(*) FROM audit_events WHERE action = ?", (acao,)).fetchone()[0]
        )
    finally:
        conexao.close()


# --------------------------------------------------------------------------- #
# RGS-09: o plano puro
# --------------------------------------------------------------------------- #
class PlanoPuroTest(unittest.TestCase):
    AGENDA = [
        {"round_number": 1, "date": "2026-06-01", "time": "09:00"},
        {"round_number": 2, "date": "2026-06-02", "time": "09:00"},
        {"round_number": 3, "date": "2026-06-03", "time": "09:00"},
    ]

    def _plano(self, **kwargs: Any) -> list[Confirmacao]:
        padrao: dict[str, Any] = {
            "rodadas_geradas": 0,
            "ajustes_atuais": {"initial_order": "rating", "allow_dangerous_changes": 0},
            "ajustes_pedidos": {},
            "ajustes_validados": {"initial_order": "rating", "allow_dangerous_changes": 0},
            "total_rodadas": 3,
            "agenda": list(self.AGENDA),
        }
        padrao.update(kwargs)
        return plan_tournament_configuration(**padrao)

    def test_nada_mudou_nada_a_confirmar(self) -> None:
        self.assertEqual([], self._plano())

    def test_reduzir_com_agenda_marcada_pede_confirmacao(self) -> None:
        plano = self._plano(total_rodadas=2)
        self.assertEqual([TIPO_AGENDA_PERDIDA], [item.tipo for item in plano])
        self.assertIn("3", plano[0].mensagem)
        self.assertFalse(plano[0].exige_motivo)

    def test_reduzir_sem_data_na_rodada_excedente_nao_pede_nada(self) -> None:
        agenda = list(self.AGENDA[:2]) + [{"round_number": 3, "date": "", "time": ""}]
        self.assertEqual([], self._plano(total_rodadas=2, agenda=agenda))

    def test_cenario_combinado_devolve_todas_as_confirmacoes_de_uma_vez(self) -> None:
        """O laço "Confirme…" → "Informe o motivo…" vira UMA lista."""
        plano = self._plano(
            rodadas_geradas=1,
            total_rodadas=2,
            ajustes_pedidos={"initial_order": "national_rating", "allow_dangerous_changes": 1},
            ajustes_validados={"initial_order": "national_rating", "allow_dangerous_changes": 1},
        )
        self.assertEqual(
            [TIPO_AGENDA_PERDIDA, TIPO_MUDANCA_ESTRUTURAL, TIPO_MUDANCAS_PERIGOSAS],
            [item.tipo for item in plano],
        )
        estrutural = plano[1]
        self.assertTrue(estrutural.exige_motivo)
        self.assertIn("ordem inicial", estrutural.mensagem)

    def test_mudanca_estrutural_antes_da_rodada_1_nao_pede_nada(self) -> None:
        plano = self._plano(
            ajustes_pedidos={"initial_order": "national_rating"},
            ajustes_validados={"initial_order": "national_rating", "allow_dangerous_changes": 0},
        )
        self.assertEqual([], plano)

    def test_campo_que_a_tela_nao_enviou_nao_conta_como_mudanca(self) -> None:
        plano = self._plano(
            rodadas_geradas=1,
            ajustes_pedidos={},
            ajustes_validados={"initial_order": "national_rating", "allow_dangerous_changes": 0},
        )
        self.assertEqual([], plano)

    def test_mudancas_perigosas_so_pedem_confirmacao_com_rodada_gerada(self) -> None:
        pedido = {"allow_dangerous_changes": 1}
        validado = {"initial_order": "rating", "allow_dangerous_changes": 1}
        self.assertEqual([], self._plano(ajustes_pedidos=pedido, ajustes_validados=validado))
        plano = self._plano(rodadas_geradas=1, ajustes_pedidos=pedido, ajustes_validados=validado)
        self.assertEqual([TIPO_MUDANCAS_PERIGOSAS], [item.tipo for item in plano])
        self.assertIn("Rodadas", plano[0].mensagem)

    def test_desligar_mudancas_perigosas_nao_pede_nada(self) -> None:
        plano = self._plano(
            rodadas_geradas=1,
            ajustes_atuais={"initial_order": "rating", "allow_dangerous_changes": 1},
            ajustes_pedidos={"allow_dangerous_changes": 0},
            ajustes_validados={"initial_order": "rating", "allow_dangerous_changes": 0},
        )
        self.assertEqual([], plano)


# --------------------------------------------------------------------------- #
# Base com torneio em andamento
# --------------------------------------------------------------------------- #
class _ConfiguracaoBase(CoreServiceTestCase):
    AGENDA_DE_CINCO = [
        {"round_number": numero, "date": f"2026-06-0{numero}", "time": "09:00"}
        for numero in range(1, 6)
    ]

    TORNEIO = {
        "name": "Torneio teste",
        "scope": "standalone",
        "competition_type": "individual",
        "rounds_count": "5",
        "bye_points": "1",
    }

    def setUp(self) -> None:
        super().setUp()
        self.db.save_round_schedule(self.tournament_id, list(self.AGENDA_DE_CINCO))
        self.db.replace_tournament_prizes(
            self.tournament_id,
            [{"kind": "overall", "label": "Campeão", "rank_from": 1, "rank_to": 1, "amount": 100}],
        )
        # O edital já é o que a tela manda de volta: salvar o mesmo edital não
        # pede a confirmação de recálculo de categorias (RG2-15, D3) — o assunto
        # destes testes é agenda e mudança estrutural.
        self.db.replace_tournament_categories(self.tournament_id, self._categorias())

    def _com_rodada_fechada(self) -> None:
        self._create_players(4)
        rodada = self.service.generate_next_round(self.tournament_id)
        for pairing in self.db.get_pairings_for_round(int(rodada["id"])):
            if not pairing["is_bye"]:
                self.db.update_pairing_result(int(pairing["id"]), "1-0")
        self.service.close_round(self.tournament_id, int(rodada["id"]))

    def _perfil_combinado(self) -> PerfilTorneio:
        """Reduz para 3 rodadas (agenda 4 e 5 marcadas) e troca a ordem inicial."""
        return PerfilTorneio(
            torneio={**self.TORNEIO, "rounds_count": "3"},
            ajustes={"initial_order": "national_rating"},
            agenda=list(self.AGENDA_DE_CINCO),
        )

    def _premios(self) -> list[dict[str, Any]]:
        return [{"kind": "overall", "label": "Campeão", "rank_from": "1", "rank_to": "1", "amount": "150"}]

    def _categorias(self) -> list[dict[str, Any]]:
        return [{"name": "Sub-12", "kind": "age", "max_value": 12}]

    def _colunas(self) -> list[Any]:
        return ["position", "name", "points"]


# --------------------------------------------------------------------------- #
# RGS-09: auditoria depois das validações, na transação
# --------------------------------------------------------------------------- #
class AuditoriaNaTransacaoTest(_ConfiguracaoBase):
    def test_recusa_por_falta_de_motivo_nao_grava_auditoria_de_agenda(self) -> None:
        """O bug do laço: cada volta gravava um `schedule_rounds_reduced` falso."""
        self._com_rodada_fechada()
        perfil = self._perfil_combinado()
        for _volta in range(3):
            with self.assertRaises(AppError):
                self.tournament_service.save_profile(
                    self.tournament_id,
                    dict(perfil.torneio),
                    dict(perfil.ajustes),
                    list(perfil.agenda),
                    confirm_schedule_loss=True,
                )
        self.assertEqual(0, _eventos(self.db.db_path, "schedule_rounds_reduced"))
        self.assertEqual(5, self.db.get_tournament(self.tournament_id)["rounds_count"])

    def test_cenario_combinado_salva_em_uma_tentativa_com_um_evento_de_cada(self) -> None:
        """Aceite do RGS-09."""
        self._com_rodada_fechada()
        perfil = self._perfil_combinado()
        backups_antes = _eventos(self.db.db_path, "backup_created")
        plano = self.tournament_service.plan_configuration(
            self.tournament_id, perfil, self._premios(), self._categorias(), self._colunas()
        )
        self.assertEqual(
            {TIPO_AGENDA_PERDIDA, TIPO_MUDANCA_ESTRUTURAL}, {item.tipo for item in plano}
        )

        self.tournament_service.save_tournament_configuration(
            self.tournament_id,
            perfil,
            self._premios(),
            self._categorias(),
            self._colunas(),
            confirmadas=[item.tipo for item in plano],
            motivo="Edital corrigido pela federação",
        )

        self.assertEqual(3, self.db.get_tournament(self.tournament_id)["rounds_count"])
        ajustes = self.db.get_tournament_settings(self.tournament_id)
        self.assertEqual("national_rating", ajustes["initial_order"])
        self.assertEqual(1, _eventos(self.db.db_path, "schedule_rounds_reduced"))
        self.assertEqual(1, _eventos(self.db.db_path, "tournament_structural_change"))
        self.assertEqual(backups_antes + 1, _eventos(self.db.db_path, "backup_created"))
        self.assertEqual(150.0, self.db.list_tournament_prizes(self.tournament_id)[0]["amount"])
        self.assertEqual(["Sub-12"], [c["name"] for c in self.db.list_tournament_categories(self.tournament_id)])

    def test_cancelar_nao_grava_evento_nenhum(self) -> None:
        """Planejar é só ler: quem cancela o diálogo não deixa rastro."""
        self._com_rodada_fechada()
        antes = _retrato(self.db.db_path)
        backups_antes = _eventos(self.db.db_path, "backup_created")
        self.tournament_service.plan_configuration(
            self.tournament_id, self._perfil_combinado(), self._premios(), self._categorias(), self._colunas()
        )
        self.assertEqual(antes, _retrato(self.db.db_path))
        self.assertEqual(backups_antes, _eventos(self.db.db_path, "backup_created"))

    def test_salvar_sem_as_confirmacoes_recusa_sem_gravar(self) -> None:
        """O serviço continua sendo quem decide: a tela pode ser burlada."""
        self._com_rodada_fechada()
        antes = _retrato(self.db.db_path)
        backups_antes = _eventos(self.db.db_path, "backup_created")
        with self.assertRaises(AppError) as erro:
            self.tournament_service.save_tournament_configuration(
                self.tournament_id,
                self._perfil_combinado(),
                self._premios(),
                self._categorias(),
                self._colunas(),
                confirmadas=[TIPO_AGENDA_PERDIDA, TIPO_MUDANCA_ESTRUTURAL],
                motivo="   ",
            )
        self.assertIn("motivo", str(erro.exception))
        self.assertEqual(antes, _retrato(self.db.db_path))
        self.assertEqual(backups_antes, _eventos(self.db.db_path, "backup_created"))

    def test_ligar_mudancas_perigosas_com_rodada_fechada_e_auditado(self) -> None:
        self._com_rodada_fechada()
        perfil = PerfilTorneio(
            torneio=dict(self.TORNEIO),
            ajustes={"allow_dangerous_changes": 1},
            agenda=list(self.AGENDA_DE_CINCO),
        )
        plano = self.tournament_service.plan_configuration(
            self.tournament_id, perfil, self._premios(), self._categorias(), self._colunas()
        )
        self.assertEqual([TIPO_MUDANCAS_PERIGOSAS], [item.tipo for item in plano])
        self.tournament_service.save_tournament_configuration(
            self.tournament_id,
            perfil,
            self._premios(),
            self._categorias(),
            self._colunas(),
            confirmadas=[TIPO_MUDANCAS_PERIGOSAS],
        )
        self.assertEqual(1, self.db.get_tournament_settings(self.tournament_id)["allow_dangerous_changes"])
        self.assertEqual(1, _eventos(self.db.db_path, "dangerous_changes_enabled"))


# --------------------------------------------------------------------------- #
# RGS-08: valida tudo antes, grava tudo junto
# --------------------------------------------------------------------------- #
class AtomicidadeTest(_ConfiguracaoBase):
    GRAVACOES = (
        "update_tournament_details",
        "save_tournament_settings",
        "save_round_schedule",
        "replace_tournament_prizes",
        "replace_tournament_categories",
        "save_report_layout",
        "create_audit_event",
    )

    def _salvar(self, perfil: PerfilTorneio, premios: list[dict[str, Any]] | None = None) -> None:
        self.tournament_service.save_tournament_configuration(
            self.tournament_id,
            perfil,
            self._premios() if premios is None else premios,
            self._categorias(),
            self._colunas(),
            confirmadas=[TIPO_AGENDA_PERDIDA, TIPO_MUDANCA_ESTRUTURAL, TIPO_MUDANCAS_PERIGOSAS],
            motivo="Teste de falha",
        )

    def _perfil_que_mexe_em_tudo(self) -> PerfilTorneio:
        return PerfilTorneio(
            torneio={**self.TORNEIO, "name": "Nome novo", "rounds_count": "3"},
            ajustes={"initial_order": "national_rating", "allow_dangerous_changes": 1, "organizer": "Novo"},
            agenda=list(self.AGENDA_DE_CINCO),
        )

    def test_premio_em_branco_nao_muda_coluna_nenhuma(self) -> None:
        """Aceite do RGS-08: antes, `allow_dangerous_changes=1` já estava gravado."""
        self._com_rodada_fechada()
        antes = _retrato(self.db.db_path)
        backups_antes = _eventos(self.db.db_path, "backup_created")
        premios = self._premios() + [{"kind": "overall", "label": "", "rank_from": "2"}]
        with self.assertRaises(AppError) as erro:
            self._salvar(self._perfil_que_mexe_em_tudo(), premios)
        self.assertIn("prêmio", str(erro.exception))
        self.assertEqual(antes, _retrato(self.db.db_path))
        # Recusa na validação: nem o backup chega a ser feito.
        self.assertEqual(backups_antes, _eventos(self.db.db_path, "backup_created"))

    def test_falha_injetada_em_cada_gravacao_desfaz_tudo(self) -> None:
        """Aceite do RGS-08: tudo igual ao anterior, exceto 1 `backup_created`."""
        self._com_rodada_fechada()
        for metodo in self.GRAVACOES:
            with self.subTest(gravacao=metodo):
                antes = _retrato(self.db.db_path)
                backups_antes = _eventos(self.db.db_path, "backup_created")
                original = getattr(self.db, metodo)

                def falhar(*args: Any, _original=original, _metodo=metodo, **kwargs: Any) -> Any:
                    if _metodo == "create_audit_event" and kwargs.get("action") == "backup_created":
                        return _original(*args, **kwargs)
                    _original(*args, **kwargs)  # grava de verdade e SÓ ENTÃO falha
                    raise _Falha(f"falha injetada em {_metodo}")

                setattr(self.db, metodo, falhar)
                try:
                    with self.assertRaises(_Falha):
                        self._salvar(self._perfil_que_mexe_em_tudo())
                finally:
                    delattr(self.db, metodo)

                self.assertEqual(antes, _retrato(self.db.db_path))
                self.assertEqual(backups_antes + 1, _eventos(self.db.db_path, "backup_created"))

    def test_sem_falha_grava_tudo(self) -> None:
        self._com_rodada_fechada()
        self._salvar(self._perfil_que_mexe_em_tudo())
        torneio = self.db.get_tournament(self.tournament_id)
        ajustes = self.db.get_tournament_settings(self.tournament_id)
        self.assertEqual("Nome novo", torneio["name"])
        self.assertEqual(3, torneio["rounds_count"])
        self.assertEqual("Novo", ajustes["organizer"])
        self.assertEqual(1, ajustes["allow_dangerous_changes"])
        self.assertEqual([1, 2, 3], [int(r["round_number"]) for r in self.db.list_round_schedule(self.tournament_id)])
        self.assertEqual(
            ["position", "name", "points"],
            [c["key"] if isinstance(c, dict) else c for c in self.db.get_report_layout_columns(self.tournament_id, "standings")],
        )

    def test_categoria_repetida_recusa_antes_de_gravar(self) -> None:
        antes = _retrato(self.db.db_path)
        with self.assertRaises(AppError):
            self.tournament_service.save_tournament_configuration(
                self.tournament_id,
                PerfilTorneio(torneio={**self.TORNEIO, "name": "Outro"}, ajustes={}, agenda=[]),
                self._premios(),
                self._categorias() + self._categorias(),
                self._colunas(),
            )
        self.assertEqual(antes, _retrato(self.db.db_path))

    def test_colunas_vazias_recusam_antes_de_gravar(self) -> None:
        antes = _retrato(self.db.db_path)
        with self.assertRaises(AppError):
            self.tournament_service.save_tournament_configuration(
                self.tournament_id,
                PerfilTorneio(torneio={**self.TORNEIO, "name": "Outro"}, ajustes={}, agenda=[]),
                self._premios(),
                self._categorias(),
                [],
            )
        self.assertEqual(antes, _retrato(self.db.db_path))


# --------------------------------------------------------------------------- #
# RGS-08: importação TRF na mesma transação
# --------------------------------------------------------------------------- #
class ImportacaoTrfAtomicaTest(CoreServiceTestCase):
    def _arquivo_trf(self, pasta: Path) -> Path:
        self._create_players(5)
        rodada = self.service.generate_next_round(self.tournament_id)
        for pairing in self.db.get_pairings_for_round(int(rodada["id"])):
            if not pairing["is_bye"]:
                self.db.update_pairing_result(int(pairing["id"]), "1-0")
        self.service.close_round(self.tournament_id, int(rodada["id"]))
        destino = pasta / "origem.trf"
        self.export_service.export_chess_results_trf(self.tournament_id, destino)
        return destino

    def test_falha_no_meio_da_importacao_nao_deixa_torneio_pela_metade(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            arquivo = self._arquivo_trf(Path(tmp))
            antes = _retrato(self.db.db_path)
            original = self.db.close_round

            def falhar(*args: Any, **kwargs: Any) -> None:
                original(*args, **kwargs)
                raise _Falha("falha injetada no fechamento da rodada importada")

            self.db.close_round = falhar  # type: ignore[method-assign]
            try:
                with self.assertRaises(_Falha):
                    self.import_service.import_trf(arquivo)
            finally:
                del self.db.close_round
        self.assertEqual(antes, _retrato(self.db.db_path))

    def test_importacao_sem_falha_continua_criando_tudo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            arquivo = self._arquivo_trf(Path(tmp))
            importado = self.import_service.import_trf(arquivo)
        novo = int(importado["tournament_id"])
        self.assertEqual(5, len(self.db.list_players(novo, active_only=False)))
        self.assertEqual(1, len(self.db.list_rounds(novo)))
