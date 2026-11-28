"""Modo Amistoso (Modo Livre no app): a regra mora em um lugar (MA-01).

Revisão do modo amistoso — `ESPEC_REVISAO_MODO_AMISTOSO.md`. Estes testes
chamam o serviço como a tela chama e conferem o que fica gravado.
"""
from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path

from src.core.database import Database
from src.services import friendly_mode
from src.services.friendly_mode import FriendlyModeService

RAIZ = Path(__file__).resolve().parents[1]


class FriendlyModeBase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)
        self.db = Database(base / "albericus.db", backup_dir=base / "backups")
        self.service = FriendlyModeService(self.db)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()


class DonoDaRegraTest(FriendlyModeBase):
    """MA-01 e MA-14.1."""

    def test_criar_liga_a_marca_e_aplica_o_preset(self) -> None:
        criado = self.service.create("Escola Estadual", rounds_count=4)
        tid = criado["tournament_id"]
        ajustes = self.db.get_tournament_settings(tid) or {}
        self.assertEqual(1, ajustes.get("free_mode"))
        # MA-14.1: o meio ponto pedagógico é o padrão do assistente também.
        self.assertEqual(0.5, float(ajustes.get("late_entry_points")))
        self.assertEqual(4, int(self.db.get_tournament(tid)["rounds_count"]))
        self.assertTrue(friendly_mode.is_friendly(ajustes))

    def test_nome_vazio_vira_nome_com_data(self) -> None:
        tid = self.service.create("   ")["tournament_id"]
        nome = self.db.get_tournament(tid)["name"]
        self.assertTrue(nome.startswith("Torneio Amistoso "), nome)

    def test_rotulo_por_marca(self) -> None:
        self.assertEqual(friendly_mode.FRIENDLY_MODE_LABEL, friendly_mode.mode_label(True))
        self.assertEqual("Modo Oficial", friendly_mode.mode_label(False))
        self.assertFalse(friendly_mode.is_friendly({}))
        self.assertFalse(friendly_mode.is_friendly(None))

    def test_o_literal_do_modo_nao_aparece_na_ui(self) -> None:
        """A troca do nome (decisão D1) tem de ser uma linha no módulo."""
        achados = []
        rotulo = friendly_mode.FRIENDLY_MODE_LABEL
        for arquivo in sorted((RAIZ / "src" / "ui").rglob("*.py")):
            arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
            docstrings = {
                id(no.body[0].value)
                for no in ast.walk(arvore)
                if isinstance(no, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                and no.body
                and isinstance(no.body[0], ast.Expr)
                and isinstance(no.body[0].value, ast.Constant)
            }
            for no in ast.walk(arvore):
                if (
                    isinstance(no, ast.Constant)
                    and isinstance(no.value, str)
                    and rotulo in no.value
                    and id(no) not in docstrings
                ):
                    achados.append(f"{arquivo.relative_to(RAIZ)}:{no.lineno}")
        self.assertEqual([], achados)


class BordasTest(FriendlyModeBase):
    """As bordas que o teste de mutação achou sem dono (scripts/mutate.py)."""

    def test_rodadas_vao_de_1_a_30(self) -> None:
        self.assertEqual("", friendly_mode.rounds_count_error("1"))
        self.assertEqual("", friendly_mode.rounds_count_error("30"))
        for invalido in ("0", "31", "abc", None):
            self.assertIn("de 1 a 30", friendly_mode.rounds_count_error(invalido), invalido)

    def test_criar_sem_dizer_rodadas_da_5_e_sem_turma_ninguem_inscrito(self) -> None:
        feito = self.service.create("Treino")
        self.assertEqual(5, int(self.db.get_tournament(feito["tournament_id"])["rounds_count"]))
        self.assertEqual(0, feito["registered"])

    def test_nome_vazio_volta_preenchido(self) -> None:
        self.assertTrue(self.service.create("  ")["name"].startswith("Torneio Amistoso "))

    def test_linha_de_atraso_so_no_modo_e_so_sem_tolerancia(self) -> None:
        self.assertEqual("", friendly_mode.late_tolerance_line(False, 0))
        self.assertEqual("", friendly_mode.late_tolerance_line(True, 1))
        self.assertIn("sem W.O.", friendly_mode.late_tolerance_line(True, 0))

    def test_limite_de_rodadas(self) -> None:
        limite = friendly_mode.is_round_limit_error
        fechada = {"status": "closed", "number": 3}
        self.assertIs(False, limite(None, fechada))
        self.assertIs(False, limite({"rounds_count": 3}, None))
        self.assertIs(True, limite({"rounds_count": 3}, fechada))
        self.assertIs(False, limite({"rounds_count": 3}, {"status": "open", "number": 3}))
        self.assertIs(False, limite({"rounds_count": 4}, fechada))
        self.assertIs(False, limite({"rounds_count": 1}, {"status": "closed"}))

    def test_dados_do_torneio_guardam_bye_zero_e_tipo(self) -> None:
        dados = friendly_mode._details_with_rounds({"bye_points": None, "competition_type": "team"}, 4)
        self.assertEqual(0.0, dados["bye_points"])
        self.assertEqual("team", dados["competition_type"])
        self.assertEqual("individual", friendly_mode._details_with_rounds({}, 4)["competition_type"])

    def test_ligar_o_que_ja_esta_ligado_nao_grava(self) -> None:
        tid = self.service.create("Treino")["tournament_id"]
        self.assertIs(False, self.service.set_enabled(tid, True))
        self.assertIs(True, self.service.set_enabled(tid, False))
        self.assertEqual(1, len(self.db.list_audit_events(tid, action="free_mode_changed")))

    def test_jogar_ja_sem_rodada_gerada_inscreve_normal(self) -> None:
        tid = self.service.create("Treino")["tournament_id"]
        feito = self.service.late_entry(tid, {"name": "Aluna"}, join_open_round=True)
        self.assertEqual(1, feito["entry_round"])

    def test_lista_de_turmas(self) -> None:
        from src.services.club_service import ClubService
        from src.services.member_service import MemberService

        clubes = ClubService(self.db)
        escola = clubes.save_profile({"name": "Escola Delta", "kind": "school", "active": 1}, club_id=None)
        uma = clubes.save_class({"club_id": escola, "name": "Turma 1", "active": 1})
        clubes.save_class({"club_id": escola, "name": "Turma vazia", "active": 1})
        clubes.save_class({"club_id": escola, "name": "Turma antiga", "active": 0})
        MemberService(self.db).create_member({"name": "Ana", "club_id": escola, "class_id": uma, "status": "active"})
        rotulos = sorted(t["label"] for t in self.service.school_classes())
        self.assertEqual(["Turma 1 – Escola Delta (1 aluno)", "Turma vazia – Escola Delta (0 alunos)"], rotulos)


class TorneioAmistosoBase(FriendlyModeBase):
    """Torneio amistoso com 6 alunos e a R1 gerada."""

    ALUNOS = 6

    def setUp(self) -> None:
        super().setUp()
        from src.services.pairing_service import PairingService

        self.tid = self.service.create("Escola", rounds_count=5)["tournament_id"]
        for i in range(self.ALUNOS):
            self.db.create_player(self.tid, name=f"Aluno {i + 1}", rating=1000 + 10 * i)
        self.pairing = PairingService(self.db)
        self.pairing.generate_next_round(self.tid)

    def rodada(self) -> dict:
        return self.db.get_latest_round(self.tid)

    def mesas(self, round_id: int) -> list[dict]:
        return [m for m in self.db.get_pairings_for_round(round_id) if not m.get("is_bye")]

    def eventos(self, acao: str) -> list[dict]:
        return self.db.list_audit_events(self.tid, action=acao)

    def jogadores_na_rodada(self, round_id: int) -> set[int]:
        ids: set[int] = set()
        for mesa in self.db.get_pairings_for_round(round_id):
            ids |= {mesa.get("white_player_id"), mesa.get("black_player_id")}
        ids.discard(None)
        return ids

    def fechar(self, round_id: int) -> None:
        for mesa in self.mesas(round_id):
            self.db.update_pairing_result(mesa["id"], "1-0")
        self.pairing.close_round(self.tid, round_id)


class ReemparceirarTest(TorneioAmistosoBase):
    """MA-03: apagar e gerar de novo é um passo só, no serviço."""

    def test_sem_resultado_refaz_sem_motivo(self) -> None:
        r1 = self.rodada()
        novo = self.pairing.repair_open_round(self.tid, int(r1["id"]))
        self.assertEqual(1, int(self.rodada()["number"]))
        self.assertNotEqual(int(r1["id"]), int(novo["round_id"]))
        self.assertEqual(1, len(self.eventos("round_repaired")))

    def test_geracao_que_falha_nao_apaga_a_rodada(self) -> None:
        r1 = self.rodada()
        mesa = self.mesas(int(r1["id"]))[0]
        self.db.update_pairing_result(mesa["id"], "1-0")
        for jogador in self.db.list_players(self.tid)[1:]:
            self.db.set_player_status(jogador["id"], "withdrawn")
        from src.services.constants import AppError

        with self.assertRaises(AppError):
            self.pairing.repair_open_round(self.tid, int(r1["id"]), reason="Alunos foram embora")
        # Nada mudou: a mesma rodada, com o resultado anotado.
        self.assertEqual(int(r1["id"]), int(self.rodada()["id"]))
        self.assertEqual("1-0", self.db.get_pairing(mesa["id"])["result"])
        self.assertEqual([], self.eventos("round_repaired"))

    def test_resultado_lancado_exige_motivo_e_fica_no_evento(self) -> None:
        from src.services.constants import AppError

        r1 = self.rodada()
        mesa = self.mesas(int(r1["id"]))[0]
        self.db.update_pairing_result(mesa["id"], "1-0")
        with self.assertRaises(AppError):
            self.pairing.repair_open_round(self.tid, int(r1["id"]))
        self.assertEqual(int(r1["id"]), int(self.rodada()["id"]))

        self.pairing.repair_open_round(self.tid, int(r1["id"]), reason="Metade da turma faltou")
        eventos = self.eventos("round_repaired")
        self.assertEqual(1, len(eventos))
        self.assertIn("Metade da turma faltou", eventos[0]["reason"])
        self.assertIn('"1-0"', str(eventos[0].get("before_json") or eventos[0].get("before")))

    def test_submissao_qr_pendente_conta_e_fica_no_evento(self) -> None:
        r1 = self.rodada()
        mesa = self.mesas(int(r1["id"]))[0]
        self.db.create_result_submission(
            self.tid, int(r1["id"]), int(mesa["id"]), None, int(mesa["board_number"]), "0-1", "Aluno"
        )
        previa = self.pairing.repair_open_round_preview(self.tid, int(r1["id"]))
        self.assertEqual(0, previa["results"])
        self.assertEqual(1, previa["qr_submissions"])
        from src.services.constants import AppError

        with self.assertRaises(AppError):  # sumiria calado: pede motivo
            self.pairing.repair_open_round(self.tid, int(r1["id"]))
        self.pairing.repair_open_round(self.tid, int(r1["id"]), reason="Refazer com quem chegou")
        before = str(self.eventos("round_repaired")[0].get("before_json") or "")
        self.assertIn('"0-1"', before)

    def test_torneio_oficial_recusa_no_servico(self) -> None:
        from src.services.constants import AppError

        self.db.set_free_mode(self.tid, False)
        r1 = self.rodada()
        with self.assertRaises(AppError):
            self.pairing.repair_open_round(self.tid, int(r1["id"]))
        self.assertEqual(int(r1["id"]), int(self.rodada()["id"]))

    def test_rodada_fechada_recusa(self) -> None:
        from src.services.constants import AppError

        r1 = self.rodada()
        self.fechar(int(r1["id"]))
        with self.assertRaises(AppError):
            self.pairing.repair_open_round(self.tid, int(r1["id"]))


class EntradaTardiaTest(TorneioAmistosoBase):
    """MA-04: um só plano de entrada tardia, e "jogar já" sem meia gravação."""

    def setUp(self) -> None:
        super().setUp()
        self.fechar(int(self.rodada()["id"]))  # R1
        self.pairing.generate_next_round(self.tid)
        self.fechar(int(self.rodada()["id"]))  # R2
        self.pairing.generate_next_round(self.tid)  # R3 aberta
        self.r3 = self.rodada()

    def entrar(self, **kw):
        return self.service.late_entry(self.tid, {"name": "Aluna Atrasada", "rating": 900}, **kw)

    def test_plano_puro_com_rodada_aberta(self) -> None:
        from src.services.pairing.player_round import late_entry_plan

        plano = late_entry_plan(
            latest_round_number=3, rounds_count=5, per_round_points=0.5,
            join_open_round=True, latest_round_open=True,
        )
        self.assertEqual((3, [1, 2], 1.0), (plano.entry_round, plano.missed_rounds, plano.starting_points))
        # Sem rodada aberta, "jogar já" não muda nada: entra na próxima.
        plano = late_entry_plan(
            latest_round_number=3, rounds_count=5, per_round_points=0.5,
            join_open_round=True, latest_round_open=False,
        )
        self.assertEqual(4, plano.entry_round)

    def test_esperar_a_proxima(self) -> None:
        feito = self.entrar(per_round_points=0.5)
        jogador = self.db.get_player(feito["player_id"])
        self.assertEqual(4, int(jogador["entry_round"]))
        self.assertEqual(1.5, float(jogador["starting_points"]))  # R1, R2 e R3 perdidas
        self.assertEqual(int(self.r3["id"]), int(self.rodada()["id"]))  # R3 intocada
        self.assertEqual(1, len(self.eventos("late_entry_registered")))

    def test_jogar_ja_nesta_rodada(self) -> None:
        feito = self.entrar(per_round_points=0.5, join_open_round=True)
        jogador = self.db.get_player(feito["player_id"])
        self.assertEqual(3, int(jogador["entry_round"]))
        self.assertEqual(1.0, float(jogador["starting_points"]))  # só R1 e R2
        r3 = self.rodada()
        self.assertEqual(3, int(r3["number"]))
        self.assertIn(feito["player_id"], self.jogadores_na_rodada(int(r3["id"])))
        self.assertEqual(1, len(self.eventos("late_entry_registered")))
        self.assertEqual(1, len(self.eventos("round_repaired")))

    def test_jogar_ja_que_falha_nao_inscreve(self) -> None:
        from src.services.constants import AppError

        mesa = self.mesas(int(self.r3["id"]))[0]
        self.db.update_pairing_result(mesa["id"], "1-0")  # exige motivo
        antes = len(self.db.list_players(self.tid))
        with self.assertRaises(AppError):
            self.entrar(per_round_points=0.5, join_open_round=True)
        self.assertEqual(antes, len(self.db.list_players(self.tid)))
        self.assertEqual("1-0", self.db.get_pairing(mesa["id"])["result"])
        self.assertEqual([], self.eventos("late_entry_registered"))

    def test_valor_por_rodada_fora_de_zero_meio_um(self) -> None:
        from src.services.constants import AppError

        with self.assertRaises(AppError):
            self.entrar(per_round_points=0.3)

    def test_torneio_oficial_recusa(self) -> None:
        from src.services.constants import AppError

        self.db.set_free_mode(self.tid, False)
        with self.assertRaises(AppError):
            self.entrar(per_round_points=0.5)


class SumulaTest(TorneioAmistosoBase):
    """MA-05: a súmula amistosa não promete W.O. na hora marcada."""

    def texto_da_sumula(self) -> str:
        from pypdf import PdfReader

        from src.services.export_service import ExportService

        caminho = Path(self.temp_dir.name) / "sumulas.pdf"
        ExportService(self.db, self.pairing).export_scoresheets(int(self.rodada()["id"]), caminho)
        return PdfReader(caminho).pages[0].extract_text()

    def test_amistoso_sem_tolerancia(self) -> None:
        texto = self.texto_da_sumula()
        self.assertNotIn("perde a hora marcada", texto)
        self.assertIn("sem W.O. automático", texto)

    def test_amistoso_com_tolerancia_mostra_minutos(self) -> None:
        self.db.save_tournament_settings(self.tid, {"late_tolerance_minutes": 15})
        self.assertIn("15 min", self.texto_da_sumula())

    def test_oficial_mantem_o_texto(self) -> None:
        self.db.set_free_mode(self.tid, False)
        self.assertIn("perde a hora marcada", self.texto_da_sumula())


class FronteiraComOficialTest(TorneioAmistosoBase):
    """MA-02 e MA-06: o torneio amistoso não vira rating oficial por engano."""

    def salvar_perfil(self, perfil: str) -> None:
        from src.services.tournament_configuration import PerfilTorneio
        from src.services.tournament_service import TournamentService

        torneio = self.db.get_tournament(self.tid)
        TournamentService(self.db).save_tournament_configuration(
            self.tid,
            PerfilTorneio(
                torneio={
                    "name": torneio["name"],
                    "rounds_count": str(torneio["rounds_count"]),
                    "bye_points": "1",
                },
                ajustes={"tournament_profile": perfil},
            ),
            [],
            [],
            ["position", "name", "points"],
        )

    def test_perfil_fide_em_amistoso_e_recusado(self) -> None:
        from src.services.constants import AppError

        with self.assertRaises(AppError) as recusa:
            self.salvar_perfil("fide")
        self.assertIn(friendly_mode.FRIENDLY_MODE_LABEL, str(recusa.exception))
        self.assertEqual("free", self.db.get_tournament_settings(self.tid)["tournament_profile"])

    def test_perfil_clube_em_amistoso_passa(self) -> None:
        self.salvar_perfil("club")
        self.assertEqual("club", self.db.get_tournament_settings(self.tid)["tournament_profile"])

    def test_ligar_o_modo_em_torneio_fide_e_recusado(self) -> None:
        from src.services.constants import AppError

        self.service.set_enabled(self.tid, False, reason="Vai valer como torneio do clube")
        self.salvar_perfil("fide")
        with self.assertRaises(AppError):
            self.service.set_enabled(self.tid, True)
        self.assertFalse(friendly_mode.is_friendly(self.db.get_tournament_settings(self.tid)))

    def test_conflito_puro(self) -> None:
        self.assertTrue(friendly_mode.profile_conflict(True, "fide"))
        self.assertEqual("", friendly_mode.profile_conflict(True, "club"))
        self.assertEqual("", friendly_mode.profile_conflict(False, "fide"))

    def exportar(self, submission: bool) -> list[str]:
        from src.services.export_service import ExportService

        caminho = Path(self.temp_dir.name) / "torneio.trf"
        return ExportService(self.db, self.pairing).export_chess_results_trf(
            self.tid, caminho, submission=submission
        )

    def test_submissao_de_rating_recusa_amistoso(self) -> None:
        from src.services.constants import AppError

        with self.assertRaises(AppError) as recusa:
            self.exportar(submission=True)
        self.assertIn(friendly_mode.FRIENDLY_MODE_LABEL, str(recusa.exception))

    def test_rating_interno_pergunta_antes_de_contar(self) -> None:
        """D2 decidida: o amistoso só conta para o rating interno se o usuário disser que sim."""
        from src.services.constants import AppError
        from src.services.rating_service import InternalRatingService

        servico = InternalRatingService(self.db)
        pergunta = friendly_mode.internal_rating_question(friendly_mode.played_as_friendly(self.db, self.tid))
        self.assertIn(friendly_mode.FRIENDLY_MODE_LABEL, pergunta)
        with self.assertRaises(AppError) as recusa:
            servico.apply_tournament_ratings(self.tid)
        self.assertIn(friendly_mode.FRIENDLY_MODE_LABEL, str(recusa.exception))
        self.assertIn("updated", servico.apply_tournament_ratings(self.tid, friendly_confirmed=True))

    def test_rating_interno_de_oficial_nao_pergunta(self) -> None:
        from src.services.rating_service import InternalRatingService

        self.db.set_free_mode(self.tid, False)
        self.assertEqual("", friendly_mode.internal_rating_question(friendly_mode.played_as_friendly(self.db, self.tid)))
        self.assertIn("updated", InternalRatingService(self.db).apply_tournament_ratings(self.tid))

    def test_arquivo_de_trabalho_sai_com_aviso(self) -> None:
        avisos = self.exportar(submission=False)
        self.assertTrue(any(friendly_mode.FRIENDLY_MODE_LABEL in aviso for aviso in avisos), avisos)


class MaisUmaRodadaTest(FriendlyModeBase):
    """MA-09: sobrou tempo de aula, mais uma rodada."""

    def setUp(self) -> None:
        super().setUp()
        from src.services.pairing_service import PairingService

        self.tid = self.service.create("Escola", rounds_count=1)["tournament_id"]
        for i in range(4):
            self.db.create_player(self.tid, name=f"Aluno {i + 1}", rating=1000 + i)
        self.pairing = PairingService(self.db)
        rodada = self.pairing.generate_next_round(self.tid)
        for mesa in self.db.get_pairings_for_round(int(rodada["id"])):
            self.db.update_pairing_result(mesa["id"], "1-0")
        self.pairing.close_round(self.tid, int(rodada["id"]))

    def test_limite_atingido_e_mais_uma(self) -> None:
        from src.services.constants import AppError

        with self.assertRaises(AppError):
            self.pairing.generate_next_round(self.tid)
        self.assertTrue(friendly_mode.is_round_limit_error(self.db.get_tournament(self.tid), self.db.get_latest_round(self.tid)))
        torneio = dict(self.db.get_tournament(self.tid))
        self.assertEqual(2, self.service.add_round(self.tid))
        depois = self.db.get_tournament(self.tid)
        self.assertEqual(2, int(depois["rounds_count"]))
        for campo in ("name", "class_id", "club_id", "bye_points", "competition_type"):
            self.assertEqual(torneio[campo], depois[campo], campo)
        self.pairing.generate_next_round(self.tid)
        self.assertEqual(2, int(self.db.get_latest_round(self.tid)["number"]))
        self.assertEqual(1, len(self.db.list_audit_events(self.tid, action="friendly_round_added")))

    def test_torneio_oficial_recusa(self) -> None:
        from src.services.constants import AppError

        self.db.set_free_mode(self.tid, False)
        with self.assertRaises(AppError):
            self.service.add_round(self.tid)
        self.assertEqual(1, int(self.db.get_tournament(self.tid)["rounds_count"]))

    def test_teto_de_rodadas_recusa_e_diz_o_limite(self) -> None:
        from src.services.constants import AppError

        for _ in range(friendly_mode.MAX_ROUNDS - 1):
            self.service.add_round(self.tid)
        with self.assertRaises(AppError) as recusa:
            self.service.add_round(self.tid)
        self.assertIn(str(friendly_mode.MAX_ROUNDS), str(recusa.exception))
        self.assertEqual(friendly_mode.MAX_ROUNDS, int(self.db.get_tournament(self.tid)["rounds_count"]))


class CriacaoComTurmaTest(FriendlyModeBase):
    """MA-08: a turma já cadastrada vira o torneio, sem redigitar ninguém."""

    def turma_com_alunos(self, ativos: int, inativos: int) -> int:
        from src.services.club_service import ClubService
        from src.services.member_service import MemberService

        clubes, membros = ClubService(self.db), MemberService(self.db)
        escola = clubes.save_profile({"name": "Escola Delta", "kind": "school", "active": 1}, club_id=None)
        turma = clubes.save_class({"club_id": escola, "name": "5º ano B", "active": 1})
        for i in range(ativos + inativos):
            membros.create_member(
                {
                    "name": f"Aluno {i + 1}",
                    "club_id": escola,
                    "class_id": turma,
                    "status": "active" if i < ativos else "inactive",
                }
            )
        return int(turma)

    def test_turma_inscreve_os_ativos(self) -> None:
        turma = self.turma_com_alunos(ativos=3, inativos=1)
        lista = self.service.school_classes()
        self.assertEqual([turma], [item["id"] for item in lista])
        self.assertIn("5º ano B – Escola Delta (3 alunos)", lista[0]["label"])
        criado = self.service.create("Festival do 5º ano", rounds_count=4, class_id=turma)
        tid = criado["tournament_id"]
        torneio = self.db.get_tournament(tid)
        self.assertEqual(turma, int(torneio["class_id"]))
        self.assertEqual(3, len(self.db.list_players(tid)))
        self.assertEqual(3, criado["registered"])
        self.assertTrue(friendly_mode.is_friendly(self.db.get_tournament_settings(tid)))

    def test_rodadas_invalidas_dizem_a_faixa(self) -> None:
        from src.services.constants import AppError

        with self.assertRaises(AppError) as recusa:
            self.service.create("Escola", rounds_count="0")
        self.assertIn(f"de 1 a {friendly_mode.MAX_ROUNDS}", str(recusa.exception))
        self.assertEqual([], self.db.list_tournaments())


if __name__ == "__main__":
    unittest.main()
