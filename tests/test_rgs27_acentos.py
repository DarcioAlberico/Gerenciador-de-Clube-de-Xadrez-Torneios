"""RGS-27: texto de tela acentuado e status da rodada traduzido.

Duas defesas, as duas no lint que o gate já roda
(``scripts/check_ui_accents.py``):

* a **lista fechada** (``PALAVRAS_SEM_ACENTO``): palavras portuguesas comuns
  que nunca se escrevem sem acento, cobradas em todo literal de ``src/ui`` e
  no catálogo — e não só nos ``text=`` que a auto-consistência conhece. Foi por
  essa fresta que "Pre-visualizar proxima rodada" passou;
* o **status da rodada** sai do catálogo (``round.status.*``), num lugar só:
  a tela mostrava "Rodada 3 - closed".
"""
from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("check_ui_accents", RAIZ / "scripts" / "check_ui_accents.py")
lint = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(lint)


class ListaFechadaNoRepositorioTest(unittest.TestCase):
    def test_nenhuma_palavra_da_lista_sem_acento(self) -> None:
        problemas = lint.checar_lista_fechada()
        self.assertEqual([], problemas, "\n".join(problemas))

    def test_a_varredura_le_alguma_coisa(self) -> None:
        """Lint que não lê nada passa sempre."""
        self.assertGreater(len(lint.literais_de_tela()), 2000)

    def test_a_lista_e_fechada_e_coerente(self) -> None:
        for sem, com in lint.PALAVRAS_SEM_ACENTO.items():
            with self.subTest(palavra=sem):
                self.assertEqual(sem, sem.lower())
                self.assertEqual(sem, lint._sem_acento(com), "a grafia certa tem de ser a mesma palavra")
                self.assertNotEqual(sem, com)
                self.assertNotIn(sem, lint.HOMOGRAFOS, "homógrafo não pode entrar na lista fechada")


class ListaFechadaRegraTest(unittest.TestCase):
    """O que entra e o que fica de fora da varredura, sem depender do repo."""

    def _problemas(self, fonte: str) -> list[str]:
        return lint.checar_lista_fechada(lint.literais_do_fonte(fonte, "tela.py"))

    def test_rotulo_em_tupla_reprova(self) -> None:
        # A forma exata que escapou: rótulo numa tupla (texto, comando).
        problemas = self._problemas('ACOES = [("Pre-visualizar proxima rodada", abrir)]\n')
        self.assertEqual(2, len(problemas), problemas)
        self.assertIn("'Pre'", problemas[0])
        self.assertIn("'próxima'", problemas[1])

    def test_fstring_e_maiuscula_reprovam(self) -> None:
        problemas = self._problemas('x = f"NAO foi possivel abrir {nome}"\n')
        self.assertEqual(["NAO", "possivel"], [p.split("'")[1] for p in problemas])

    def test_texto_acentuado_passa(self) -> None:
        self.assertEqual([], self._problemas('rotulo = "Não foi possível abrir a próxima rodada"\n'))

    def test_log_fica_de_fora(self) -> None:
        fonte = (
            'logger.debug("nao foi possivel")\n'
            'self.logger.warning("proxima")\n'
            'logging.getLogger(__name__).info("codigo invalido")\n'
        )
        self.assertEqual([], self._problemas(fonte))

    def test_chave_indice_comparacao_e_sql_ficam_de_fora(self) -> None:
        fonte = (
            'dados = {"Proxima rodada": 1}\n'
            'valor = linha["Codigo novo"]\n'
            'outro = linha.get("Nivel atual")\n'
            'if status == "Nao informado": pass\n'
            'sql = "SELECT codigo FROM nao_existe"\n'
            'chave = "proxima_rodada"\n'
            'arquivo = "_sumulas.pdf"\n'
        )
        self.assertEqual([], self._problemas(fonte))

    def test_docstring_fica_de_fora(self) -> None:
        self.assertEqual([], self._problemas('def f():\n    """Abre a proxima rodada."""\n'))

    def test_placeholder_do_catalogo_fica_de_fora(self) -> None:
        self.assertEqual([], lint.checar_lista_fechada([("cat", "Federação {codigo} adicionada.")]))

    def test_verbo_com_pronome_sem_acento_reprova(self) -> None:
        # "sem grava-lo" chegou à tela: -ar/-er + pronome leva acento (gravá-lo, preenchê-lo).
        problemas = lint.checar_lista_fechada([("cat", "Prévia sem grava-lo; use os dados para preenche-la.")])
        self.assertEqual(2, len(problemas), problemas)
        self.assertIn("'gravá-lo'", problemas[0])
        self.assertIn("'preenchê-la'", problemas[1])

    def test_verbo_com_pronome_certo_passa(self) -> None:
        # -ir não leva acento (emiti-lo); a forma acentuada passa.
        self.assertEqual([], lint.checar_lista_fechada([("cat", "Sem gravá-lo, emiti-lo ou preenchê-las.")]))


class TextoDeTelaDoServicoTest(unittest.TestCase):
    """O que a varredura de ``src/services`` lê como texto de tela."""

    def _problemas(self, fonte: str, nome: str = "src/services/x.py") -> list[str]:
        return lint.checar_lista_fechada(lint.literais_de_servico_do_fonte(fonte, nome))

    def test_motivo_da_recusa_do_gacrux_e_texto_de_tela(self) -> None:
        # A lista de problemas vira a mensagem de `GacruxOutputRejected`, que a
        # tela de Rodadas mostra — mas não passa por `AppError(...)` literal.
        fonte = 'problems.append(f"par ilegivel: {item}")\n'
        nome = "src/services/pairing/gacrux_engine.py"
        self.assertEqual(["ilegivel"], [p.split("'")[1] for p in self._problemas(fonte, nome)])

    def test_sinonimos_de_importacao_ficam_de_fora(self) -> None:
        # Sinônimo e o que vem no CABEÇALHO do arquivo do usuário, sem acento
        # muitas vezes: e termo de busca, como o `.keywords` do catálogo.
        fonte = 'CAMPOS = [{"label": "Nome próprio", "synonyms": ["nome proprio", "genero"]}]\n'
        self.assertEqual([], self._problemas(fonte))

    def test_rotulo_ao_lado_do_sinonimo_continua_cobrado(self) -> None:
        fonte = 'CAMPOS = [{"label": "Nome proprio", "synonyms": ["nome proprio"]}]\n'
        self.assertEqual(["proprio"], [p.split("'")[1] for p in self._problemas(fonte)])


class TextoSemeadoNoBancoTest(unittest.TestCase):
    """As sementes do banco (níveis, modelos de certificado) vão para a tela e
    para o certificado impresso: entram na lista fechada também."""

    def test_as_sementes_do_banco_sao_lidas(self) -> None:
        textos = [texto for _origem, texto in lint.literais_de_semente()]
        self.assertIn("Certificado de Participação", textos)
        self.assertIn("Intermediário", textos)
        # Assinatura da galeria de modelos (`model_to_template`).
        self.assertIn("Arbitragem / Direção", textos)

    def test_semente_sem_acento_reprova(self) -> None:
        fonte = (
            'DEFAULT_LEARNING_LEVELS = (("Intermediario", "Reconhece taticas e principios."),)\n'
            'CERTIFICATE_BACKGROUND_PRESETS = (("Xadrez classico", "assets/x/xadrez_classico.png", 0.1),)\n'
        )
        problemas = lint.checar_lista_fechada(lint.literais_de_servico_do_fonte(fonte, "src/core/database.py"))
        self.assertEqual(
            ["Intermediario", "taticas", "principios", "classico"], [p.split("'")[1] for p in problemas]
        )

    def test_caminho_de_arquivo_da_semente_fica_de_fora(self) -> None:
        fonte = 'PRESETS = (("Xadrez clássico", "assets/certificates/backgrounds/xadrez_classico.png"),)\n'
        self.assertEqual(
            [], lint.checar_lista_fechada(lint.literais_de_servico_do_fonte(fonte, "src/core/database.py"))
        )


class StatusDaRodadaTest(unittest.TestCase):
    """O status cru do banco não chega à tela (``view.py``: "Rodada 3 - closed")."""

    def setUp(self) -> None:
        from src.ui.i18n import load_catalog, set_catalog

        set_catalog(load_catalog())

    def test_rodada_encerrada(self) -> None:
        from src.ui.support import round_option_label

        self.assertEqual("Rodada 3 - encerrada", round_option_label({"number": 3, "status": "closed"}))

    def test_rodada_gerada(self) -> None:
        from src.ui.support import round_option_label

        self.assertEqual("Rodada 1 - em andamento", round_option_label({"number": 1, "status": "generated"}))

    def test_todo_status_gravado_tem_rotulo_no_catalogo(self) -> None:
        """Os dois valores que o banco grava em ``rounds.status``."""
        catalogo = json.loads((RAIZ / "i18n" / "pt_BR.json").read_text(encoding="utf-8"))
        for status in ("generated", "closed"):
            with self.subTest(status=status):
                chave = f"round.status.{status}"
                self.assertTrue(chave in catalogo, f"{chave} ausente do catálogo")

    def test_nenhuma_tela_monta_o_rotulo_com_status_cru(self) -> None:
        cru = " - {round_data['status']}"
        telas = [p for p in (RAIZ / "src" / "ui").rglob("*.py") if cru in p.read_text(encoding="utf-8")]
        self.assertEqual([], [p.relative_to(RAIZ).as_posix() for p in telas])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
