"""FED-05 — lista FIDE: nascimento e robustez do download.

A lista oficial da FIDE publica **só o ano** de nascimento. O importador gravava
esse ano no `birth_date` (certo), mas a validação do TRF tratava ano-só como data
quebrada — então **todo** jogador importado da FIDE disparava aviso de nascimento
inválido no arquivo da federação: o plantel inteiro envenenado por uma checagem
errada.

O leitor do arquivo também vivia dentro do método que baixa o ZIP, com três
consequências: linha aceita a partir de 120 caracteres enquanto o ano mora em
127-131 (jogador entrava sem nascimento), linha malformada descartada em silêncio
(a lista de erros existia e nunca recebia nada) e download em `http://` sem
tratamento de falha.
"""

from __future__ import annotations

import unittest

from src.services.export_federation import FederationReportsMixin
from src.services.fide_list import (
    MIN_LINE_LENGTH,
    birth_year,
    is_header,
    parse_line,
    parse_rating_list,
)
from tests.support.core_service_base import CoreServiceTestCase

# Linha real da lista da FIDE, montada nas colunas do arquivo oficial:
# ID(0-14) Nome(15-75) Fed(76-79) Sex(80-83) Tit(84-88) ... SRtng(113-118) ...
# B-day(126-130).
CABECALHO = (
    "ID Number      Name".ljust(76)
    + "Fed Sex Tit  WTit OTit".ljust(50)
    + "B-day Flag"
)


def _linha(
    fide_id: str = "2900001",
    nome: str = "Silva, Joao",
    fed: str = "BRA",
    sexo: str = "M",
    titulo: str = "FM",
    rating: str = "2350",
    nascimento: str = "1985",
) -> str:
    linha = list(" " * 136)

    def por(inicio: int, texto: str) -> None:
        linha[inicio:inicio + len(texto)] = list(texto)

    por(0, fide_id)
    por(15, nome)
    por(76, fed)
    por(80, sexo)
    por(84, titulo)
    por(113, rating.rjust(6))
    por(126, nascimento)
    return "".join(linha)


class LeitorDaListaTest(unittest.TestCase):
    def test_le_os_campos_da_linha(self) -> None:
        jogador = parse_line(_linha())
        assert jogador is not None
        self.assertEqual("2900001", jogador["fide_id"])
        self.assertEqual("Silva, Joao", jogador["name"])
        self.assertEqual("BRA", jogador["federation"])
        self.assertEqual("M", jogador["sex"])
        self.assertEqual("FM", jogador["title"])
        self.assertEqual(2350, jogador["international_rating"])
        self.assertEqual("1985", jogador["birth_date"])

    def test_nascimento_e_gravado_como_ANO(self) -> None:
        """A FIDE só publica o ano; completar com 01/01 inventaria aniversário."""
        self.assertEqual("1985", birth_year(_linha(nascimento="1985")))
        self.assertEqual("", birth_year(_linha(nascimento="")))
        self.assertEqual("", birth_year(_linha(nascimento="19")))

    def test_linha_curta_demais_para_o_nascimento_e_recusada(self) -> None:
        """O corte antigo (120) ficava ANTES do campo de nascimento."""
        curta = _linha()[:125]
        self.assertGreater(MIN_LINE_LENGTH, 120)
        self.assertIsNone(parse_line(curta))

    def test_cabecalho_nao_vira_jogador(self) -> None:
        self.assertTrue(is_header(CABECALHO))
        self.assertIsNone(parse_line(CABECALHO))

    def test_lista_reporta_o_que_ignorou(self) -> None:
        """Descartar em silêncio fazia arquivo truncado parecer importação boa."""
        jogadores, erros = parse_rating_list(
            [CABECALHO, _linha(), "linha quebrada", _linha(fide_id="2900002")]
        )
        self.assertEqual(2, len(jogadores))
        self.assertEqual(1, len(erros))
        self.assertIn("Linha 3", erros[0])

    def test_lista_limpa_nao_gera_erro(self) -> None:
        jogadores, erros = parse_rating_list([CABECALHO, _linha(), ""])
        self.assertEqual(1, len(jogadores))
        self.assertEqual([], erros)

    def test_muitas_linhas_ruins_viram_resumo(self) -> None:
        ruins = ["x"] * 30
        _jogadores, erros = parse_rating_list([CABECALHO, *ruins])
        self.assertLess(len(erros), 30)
        self.assertIn("mais 10 linha(s)", erros[-1])


class NascimentoNoTRFTest(unittest.TestCase):
    """Ano-só é data VÁLIDA no TRF — a spec aceita `YYYY` no campo 70-79."""

    def test_ano_so_e_valido(self) -> None:
        self.assertTrue(FederationReportsMixin._trf_date_is_valid("1985"))

    def test_ano_com_mes_e_dia_zerados_tambem(self) -> None:
        """`1985-00-00` é como outros programas dizem "só o ano"."""
        self.assertTrue(FederationReportsMixin._trf_date_is_valid("1985-00-00"))
        self.assertEqual("1985", FederationReportsMixin._trf_date("1985-00-00", long_year=True))

    def test_data_completa_continua_valida(self) -> None:
        self.assertTrue(FederationReportsMixin._trf_date_is_valid("1985-03-17"))
        self.assertEqual(
            "1985/03/17", FederationReportsMixin._trf_date("1985-03-17", long_year=True)
        )

    def test_vazio_e_lixo_seguem_invalidos(self) -> None:
        self.assertFalse(FederationReportsMixin._trf_date_is_valid(""))
        self.assertFalse(FederationReportsMixin._trf_date_is_valid("nao sei"))

    def test_ano_so_sai_como_ano_no_arquivo(self) -> None:
        self.assertEqual("1985", FederationReportsMixin._trf_date("1985", long_year=True))
        self.assertEqual("85", FederationReportsMixin._trf_date("1985", long_year=False))


class PlantelImportadoDaFideTest(CoreServiceTestCase):
    """O que a tarefa promete: importar da FIDE não polui o TRF de avisos."""

    def test_jogador_com_ano_de_nascimento_nao_gera_aviso(self) -> None:
        jogador = parse_line(_linha())
        assert jogador is not None
        self.db.create_player(
            self.tournament_id,
            name=jogador["name"],
            rating=jogador["international_rating"],
            club="Clube",
            category="Absoluto",
            fide_id=jogador["fide_id"],
            federation_id=jogador["federation"],
            birth_date=jogador["birth_date"],
        )
        avisos = self.export_service.validate_chess_results_trf(self.tournament_id)
        self.assertEqual(
            [], [aviso for aviso in avisos if "nascimento" in aviso.lower()]
        )

    def test_jogador_sem_nascimento_continua_avisando(self) -> None:
        self.db.create_player(
            self.tournament_id, name="Sem Data", rating=1800, club="Clube", category="Absoluto"
        )
        avisos = self.export_service.validate_chess_results_trf(self.tournament_id)
        self.assertTrue(any("nascimento" in aviso.lower() for aviso in avisos))


if __name__ == "__main__":
    unittest.main()
