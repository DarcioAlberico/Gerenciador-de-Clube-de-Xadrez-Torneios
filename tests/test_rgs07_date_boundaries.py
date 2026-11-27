"""RGS-07 — a mesma regra de data em toda fronteira.

Evidência da spec:

- `_normalize_optional_date` aceitava o formato brasileiro; `_validated_schedule`
  aceitava só ISO;
- `cutoff_date`, `category_reference_date` e `team_lineup_deadline` eram texto
  livre (e `category_reference_date` nem chegava ao banco pela tela);
- a importação TRF aceitava data impossível: `2026.02.30` virava `2026-02-30`.

Requisito: toda fronteira lê data por `src.domain.dates`. O teste-varredura no
fim reprova `strptime`/`fromisoformat` novo fora de lá.
"""

from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from src.core.services import AppError
from src.services.trf_import import parse_trf
from tests.support.core_service_base import CoreServiceTestCase

RAIZ = Path(__file__).resolve().parents[1]


def _linha_jogador(rank: int, nome: str, nascimento: str = "2000/01/01") -> str:
    return (
        f"001 {rank:4d} m    {nome:<33} {1800:4d} BRA {'':>11} {nascimento:<10} "
        f"{'0.0':>4} {rank:4d}  \r\n"
    )


class ServicoDoTorneioTest(CoreServiceTestCase):
    def test_normaliza_formatos_aceitos(self) -> None:
        normalizar = self.tournament_service._normalize_optional_date
        self.assertEqual("2010-05-12", normalizar("2010/05/12", "x"))
        self.assertEqual("2026-11-13", normalizar("2026-11-13 08:00", "x"))
        self.assertEqual("2026-02-01", normalizar("1/2/2026", "x"))
        with self.assertRaises(AppError):
            normalizar("13/11/26", "Data inicial invalida.")

    def test_agenda_aceita_o_que_o_torneio_aceita_e_grava_iso(self) -> None:
        linhas = self.tournament_service._validated_schedule(
            [{"round_number": 1, "date": "13/11/2026"}], 1
        )
        self.assertEqual("2026-11-13", linhas[0]["date"])
        with self.assertRaises(AppError):
            self.tournament_service._validated_schedule([{"round_number": 1, "date": "2026-02-30"}], 1)

    def _salvar(self, **ajustes: str) -> None:
        torneio = self.db.get_tournament(self.tournament_id)
        self.tournament_service.save_profile(
            self.tournament_id,
            {
                "name": torneio["name"],
                "rounds_count": str(torneio["rounds_count"]),
                "bye_points": "1",
            },
            dict(ajustes),
            [],
        )

    def test_datas_das_configuracoes_sao_normalizadas(self) -> None:
        self._salvar(
            cutoff_date="31/12/2026",
            category_reference_date="2028",
            team_lineup_deadline="2026-11-13 08:00",
        )
        ajustes = self.db.get_tournament_settings(self.tournament_id)
        self.assertEqual("2026-12-31", ajustes["cutoff_date"])
        self.assertEqual("2028", ajustes["category_reference_date"])
        self.assertEqual("2026-11-13", ajustes["team_lineup_deadline"])

    def test_data_de_configuracao_invalida_e_recusada(self) -> None:
        antes = self.db.get_tournament_settings(self.tournament_id)
        for campo in ("cutoff_date", "category_reference_date", "team_lineup_deadline"):
            with self.subTest(campo=campo), self.assertRaises(AppError):
                self._salvar(**{campo: "31/02/2026"})
        self.assertEqual(antes, self.db.get_tournament_settings(self.tournament_id))

    def test_data_legada_que_a_tela_nao_envia_nao_trava_o_salvamento(self) -> None:
        """O prazo de escalação não tem campo na tela: valor legado inválido fica
        como está (vai para "Datas a revisar") em vez de travar todo salvamento."""
        self.db.save_tournament_settings(self.tournament_id, {"team_lineup_deadline": "sexta"})
        self._salvar(cutoff_date="31/12/2026")
        ajustes = self.db.get_tournament_settings(self.tournament_id)
        self.assertEqual("sexta", ajustes["team_lineup_deadline"])
        self.assertEqual("2026-12-31", ajustes["cutoff_date"])


class ImportacaoTrfTest(CoreServiceTestCase):
    def _importar(self, conteudo: str) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            origem = Path(tmp) / "torneio.trf"
            origem.write_text(conteudo, encoding="utf-8", newline="")
            return self.import_service.import_trf(origem)

    def test_data_impossivel_e_recusada_citando_a_linha(self) -> None:
        conteudo = "012 Aberto\r\n042 2026.02.30\r\n" + _linha_jogador(1, "Ana")
        antes = len(self.db.list_tournaments())
        with self.assertRaises(AppError) as contexto:
            self._importar(conteudo)
        mensagem = str(contexto.exception)
        self.assertIn("linha 2", mensagem)
        self.assertIn("2026.02.30", mensagem)
        self.assertEqual(antes, len(self.db.list_tournaments()))

    def test_nascimento_impossivel_cita_linha_e_coluna(self) -> None:
        conteudo = "012 Aberto\r\n" + _linha_jogador(1, "Ana", "2001/02/30")
        with self.assertRaises(ValueError) as contexto:
            parse_trf(conteudo)
        self.assertIn("linha 2", str(contexto.exception))
        self.assertIn("colunas 70-79", str(contexto.exception))

    def test_registro_132_e_aa_mm_dd(self) -> None:
        linha_132 = "132" + " " * 88 + "26/11/13  26/11/14"
        conteudo = "012 Aberto\r\n" + linha_132 + "\r\n" + _linha_jogador(1, "Ana")
        self.assertEqual(["2026-11-13", "2026-11-14"], parse_trf(conteudo)["round_dates"])

    def test_registro_132_impossivel_e_recusado(self) -> None:
        linha_132 = "132" + " " * 88 + "26/02/30"
        with self.assertRaises(ValueError) as contexto:
            parse_trf("012 Aberto\r\n" + linha_132 + "\r\n" + _linha_jogador(1, "Ana"))
        self.assertIn("linha 2", str(contexto.exception))

    def test_nascimento_so_com_ano(self) -> None:
        jogadores = parse_trf(_linha_jogador(1, "Ana", "1985/00/00") + _linha_jogador(2, "Bia", "1990"))[
            "players"
        ]
        self.assertEqual(["1985", "1990"], [jogador["birth_date"] for jogador in jogadores])


class ImportacaoDePlanilhaTest(CoreServiceTestCase):
    """XLSX/CSV de jogadores e respostas do Google Forms passam pela mesma regra."""

    def _csv(self, conteudo: str) -> Path:
        caminho = Path(self.temp_dir.name) / "jogadores.csv"
        caminho.write_text(conteudo, encoding="utf-8")
        return caminho

    def test_planilha_de_jogadores_normaliza_e_recusa_com_linha(self) -> None:
        caminho = self._csv(
            "nome,rating,data_nascimento\n"
            "Ana,1500,12/05/2010\n"
            "Bia,1400,1985\n"
            "Caio,1300,30/02/2010\n"
        )
        resultado = self.import_service.import_players_csv(self.tournament_id, caminho)
        nascimentos = {
            jogador["name"]: jogador["birth_date"] for jogador in self.db.list_players(self.tournament_id)
        }
        self.assertEqual("2010-05-12", nascimentos["Ana"])
        self.assertEqual("1985", nascimentos["Bia"])
        self.assertNotIn("Caio", nascimentos)
        self.assertEqual(1, len(resultado["errors"]))
        self.assertIn("Linha 4", resultado["errors"][0])
        self.assertIn("data_nascimento", resultado["errors"][0])

    def test_inscricao_online_com_data_ruim_vira_erro_da_linha(self) -> None:
        caminho = self._csv("nome,data de nascimento\nAna,13/11/26\nBia,2010-05-12 00:00:00\n")
        previa = self.import_service.preview_online_registrations(self.tournament_id, caminho)
        por_nome = {linha["name"]: linha for linha in previa["rows"]}
        self.assertEqual("error", por_nome["Ana"]["status"])
        self.assertIn("nascimento", por_nome["Ana"]["message"])
        self.assertEqual("2010-05-12", por_nome["Bia"]["birth_date"])


# --- varredura ---------------------------------------------------------------
# Lista FECHADA de leituras de data fora de `src/domain/dates.py`. Cada uma é
# carimbo de tempo gerado pelo próprio programa (nunca texto de usuário ou de
# arquivo) e por isso não passa pela regra de data. Entrar aqui exige motivo.
EXCECOES: dict[str, tuple[int, str]] = {
    "src/services/pairing_service.py": (
        3,
        "carimbos `started_at`/`ended_at` da geração, gravados por `Database.now()`",
    ),
    "src/services/pairing/corrections.py": (
        1,
        "carimbo do desbloqueio pontual (`TIMESTAMP_FORMAT`), gerado pelo programa",
    ),
    "src/services/dashboard_service.py": (
        1,
        "data E hora de agendamento de mensagem: a hora é obrigatória, e o "
        "`parse_date` a descarta por definição",
    ),
}

_LEITURA_DE_DATA = re.compile(r"\bstrptime\(|\b(?:date|datetime)\.fromisoformat\(")


def _leituras_por_arquivo() -> dict[str, int]:
    contagem: dict[str, int] = {}
    for caminho in sorted((RAIZ / "src").rglob("*.py")):
        relativo = caminho.relative_to(RAIZ).as_posix()
        if relativo == "src/domain/dates.py":
            continue
        achados = len(_LEITURA_DE_DATA.findall(caminho.read_text(encoding="utf-8")))
        if achados:
            contagem[relativo] = achados
    return contagem


class VarreduraTest(unittest.TestCase):
    def test_leitura_de_data_so_em_domain_dates(self) -> None:
        encontrados = _leituras_por_arquivo()
        novos = {
            arquivo: quantidade
            for arquivo, quantidade in encontrados.items()
            if quantidade > EXCECOES.get(arquivo, (0, ""))[0]
        }
        self.assertEqual(
            {},
            novos,
            "Leia datas de usuário/arquivo com src.domain.dates.parse_date (RGS-07); "
            "carimbo de tempo do próprio programa entra em EXCECOES com motivo.",
        )

    def test_excecoes_nao_ficam_obsoletas(self) -> None:
        encontrados = _leituras_por_arquivo()
        for arquivo, (quantidade, motivo) in EXCECOES.items():
            with self.subTest(arquivo=arquivo):
                self.assertTrue(motivo)
                self.assertEqual(quantidade, encontrados.get(arquivo, 0), "lista fechada: ajuste a contagem")


if __name__ == "__main__":
    unittest.main()
