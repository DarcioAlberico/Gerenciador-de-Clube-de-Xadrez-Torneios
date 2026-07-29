"""Testes do componente de diálogos temáticos (``src/ui/components/dialogs.py``).

Os diálogos são **bloqueantes** (``wait_window`` dentro do construtor), então cada
teste agenda a interação com ``after`` antes de abrir o diálogo: o callback roda
dentro do laço de eventos do próprio modal, clica/tecla, e o construtor retorna.

Cobre o que o mock de ``confirm_dialog`` nas telas não cobre: retorno de cada
botão, teclado (Esc/Enter), a proteção contra Enter reflexo em ação destrutiva e
a preservação do *grab* ao abrir um modal sobre outro.

A raiz Tk é única para a classe — criar e destruir um ``CTk`` por teste deixa o
interpretador Tcl instável no Windows ("Can't find a usable tk.tcl" no root
seguinte). Cada teste limpa os próprios ``after`` e diálogos remanescentes.
"""
from __future__ import annotations

import unittest
from tkinter import TclError

import customtkinter as ctk
import pytest

from src.ui.components.dialogs import (
    Dialog,
    actions_bar,
    alert_dialog,
    choice_dialog,
    confirm_dialog,
    report_dialog,
    tri_state_dialog,
)
from src.ui.dialog_layout import MIN_SIZE, centered_position, fitted_size, geometry_string
from tests.support.ctk_cleanup import (
    cancel_pending_callbacks,
    create_tk_window,
    release_dead_ctk_windows,
)

# Esta suite abre janela: precisa de display real. Ver o marcador 'gui'
# no pyproject — o gate sem display roda com -m 'not gui'.
pytestmark = pytest.mark.gui

def _find_button(widget, text: str) -> ctk.CTkButton | None:
    """Primeiro ``CTkButton`` com o rótulo dado, em profundidade."""
    for child in widget.winfo_children():
        if isinstance(child, ctk.CTkButton) and child.cget("text") == text:
            return child
        found = _find_button(child, text)
        if found is not None:
            return found
    return None


class DialogsTest(unittest.TestCase):
    root: ctk.CTk

    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.root = create_tk_window(ctk.CTk)
        except TclError as exc:  # pragma: no cover - ambiente sem display
            raise unittest.SkipTest(f"Tk indisponivel para teste de dialogos: {exc}") from exc
        cls.root.geometry("400x300+80+80")
        cls.root.update()

    @classmethod
    def tearDownClass(cls) -> None:
        cancel_pending_callbacks(cls.root)
        try:
            cls.root.destroy()
        except TclError:  # pragma: no cover
            pass
        release_dead_ctk_windows()

    def setUp(self) -> None:
        self._agendados: list[str] = []
        self._falha_agendada: BaseException | None = None

    def tearDown(self) -> None:
        # Exceção dentro de um callback agendado não pode virar teste travado:
        # o Tk a imprime e segue, o diálogo nunca fecha e o `wait_window` espera
        # para sempre. Aqui ela vira falha, com o erro original.
        if self._falha_agendada is not None:
            raise AssertionError(
                f"acao agendada falhou: {self._falha_agendada!r}"
            ) from self._falha_agendada
        for job in self._agendados:
            try:
                self.root.after_cancel(job)
            except Exception:
                pass
        for window in list(self.root.winfo_children()):
            if isinstance(window, ctk.CTkToplevel):
                try:
                    window.destroy()
                except Exception:
                    pass
        release_dead_ctk_windows()

    # -- utilitários ------------------------------------------------------

    def _dialog(self) -> ctk.CTkToplevel:
        """Diálogo aberto mais recente (o topo da pilha de modais)."""
        abertos = [w for w in self.root.winfo_children() if isinstance(w, ctk.CTkToplevel)]
        self.assertTrue(abertos, "nenhum dialogo aberto")
        return abertos[-1]

    def _quando_abrir(self, acao, delay: int = 250) -> None:
        """Agenda ``acao(dialogo)`` para rodar com o modal já na tela.

        Se ``acao`` levantar, o erro é guardado e o diálogo é fechado à força —
        senão o teste ficaria pendurado no ``wait_window`` e o motivo real (um
        botão que mudou de nome, um ``cget`` sem suporte) sumiria no stderr.
        """

        def executar() -> None:
            dialog = None
            try:
                dialog = self._dialog()
                acao(dialog)
            except BaseException as exc:  # noqa: BLE001 - relançado no tearDown
                self._falha_agendada = exc
                if dialog is not None:
                    try:
                        dialog.destroy()
                    except Exception:
                        pass

        self._agendados.append(self.root.after(delay, executar))

    def _clicar(self, texto: str, delay: int = 250) -> None:
        def acao(dialog: ctk.CTkToplevel) -> None:
            botao = _find_button(dialog, texto)
            self.assertIsNotNone(botao, f"botao '{texto}' nao encontrado no dialogo")
            botao.invoke()

        self._quando_abrir(acao, delay)

    def _teclar(self, tecla: str, delay: int = 250) -> None:
        def acao(dialog: ctk.CTkToplevel) -> None:
            dialog.focus_force()
            dialog.event_generate(tecla)

        self._quando_abrir(acao, delay)

    # -- confirm_dialog ---------------------------------------------------

    def test_confirmar_retorna_true(self) -> None:
        self._clicar("Sim")
        self.assertTrue(confirm_dialog(self.root, "Confirmar", "Prosseguir?"))

    def test_cancelar_retorna_false(self) -> None:
        self._clicar("Não")
        self.assertFalse(confirm_dialog(self.root, "Confirmar", "Prosseguir?"))

    def test_rotulo_de_cancelar_e_acentuado(self) -> None:
        rotulos: dict[str, bool] = {}

        def acao(dialog: ctk.CTkToplevel) -> None:
            rotulos["acentuado"] = _find_button(dialog, "Não") is not None
            dialog.event_generate("<Escape>")

        self._quando_abrir(acao)
        confirm_dialog(self.root, "Confirmar", "Prosseguir?")
        self.assertTrue(rotulos.get("acentuado"), "o rotulo padrao deve ser 'Não', acentuado")

    def test_escape_retorna_false(self) -> None:
        self._teclar("<Escape>")
        self.assertFalse(confirm_dialog(self.root, "Confirmar", "Prosseguir?"))

    def test_enter_confirma_dialogo_comum(self) -> None:
        self._teclar("<Return>")
        self.assertTrue(confirm_dialog(self.root, "Confirmar", "Prosseguir?"))

    # -- proteção de ação destrutiva --------------------------------------

    def test_enter_nao_confirma_dialogo_destrutivo(self) -> None:
        """Enter reflexo não pode disparar exclusão.

        O que o código garante (``enter_value = default`` quando ``danger``) é
        que o Enter vale **"Não"**: ele fecha o diálogo, mas nunca confirma. A
        versão anterior deste teste exigia que o Enter fosse totalmente inerte
        (diálogo aberto) — e passava mesmo assim, porque a asserção rodava
        dentro de um callback agendado e o Tk engolia a falha. Com o guard do
        ``_quando_abrir`` a divergência apareceu; a proteção real continua de pé
        e é ela que este teste cobra.
        """
        self._teclar("<Return>")
        self.assertFalse(confirm_dialog(self.root, "Excluir", "Excluir tudo?", danger=True))

    def test_destrutivo_ainda_confirma_pelo_botao(self) -> None:
        """A proteção do Enter não pode inutilizar a confirmação explícita."""
        self._clicar("Sim")
        self.assertTrue(confirm_dialog(self.root, "Excluir", "Excluir tudo?", danger=True))

    # -- tri_state_dialog -------------------------------------------------

    def test_tri_state_sim_nao_cancelar(self) -> None:
        self._clicar("Sim")
        self.assertIs(True, tri_state_dialog(self.root, "Tri", "Escolha"))
        self._clicar("Não")
        self.assertIs(False, tri_state_dialog(self.root, "Tri", "Escolha"))
        self._clicar("Cancelar")
        self.assertIsNone(tri_state_dialog(self.root, "Tri", "Escolha"))

    def test_tri_state_escape_cancela(self) -> None:
        self._teclar("<Escape>")
        self.assertIsNone(tri_state_dialog(self.root, "Tri", "Escolha"))

    # -- alert_dialog e modalidade ----------------------------------------

    def test_alerta_fecha_no_ok_e_libera_o_grab(self) -> None:
        self._clicar("OK")
        alert_dialog(self.root, "Erro", "Falhou", kind="error")
        self.assertIsNone(self.root.grab_current(), "grab deveria ser liberado ao fechar")

    # -- report_dialog (F5.7) ---------------------------------------------

    def test_relatorio_mostra_o_corpo_inteiro_e_fecha_no_botao(self) -> None:
        corpo = "\n".join(f"Criterio {i}: valor" for i in range(30))
        visto: dict[str, str] = {}

        def acao(dialog: ctk.CTkToplevel) -> None:
            visto["texto"] = dialog.corpo.get("1.0", "end").strip()
            # O cget do CTkTextbox nao repassa 'state'; pergunta-se ao Text interno.
            visto["estado"] = str(dialog.corpo._textbox.cget("state"))
            _find_button(dialog, "Fechar").invoke()

        self._quando_abrir(acao)
        report_dialog(self.root, "Desempates", corpo)

        self.assertEqual(corpo, visto["texto"], "o relatorio nao pode ser truncado")
        self.assertEqual("disabled", visto["estado"], "corpo e somente leitura")
        self.assertIsNone(self.root.grab_current(), "grab deveria ser liberado")

    def test_relatorio_copia_o_conteudo_para_a_area_de_transferencia(self) -> None:
        corpo = "http://192.168.0.5:8765\n\nUse este endereco na rede local.\nMesa 1"
        copiado: dict[str, str] = {}

        def acao(dialog: ctk.CTkToplevel) -> None:
            _find_button(dialog, "Copiar").invoke()
            copiado["area"] = dialog.clipboard_get()
            _find_button(dialog, "Fechar").invoke()

        self._quando_abrir(acao)
        report_dialog(self.root, "Servidor QR", corpo)
        self.assertEqual(corpo, copiado["area"])

    def test_relatorio_fecha_com_escape(self) -> None:
        self._teclar("<Escape>")
        report_dialog(self.root, "Relatorio", "a\nb\nc")
        self.assertIsNone(self.root.grab_current())

    def test_modal_sobre_modal_devolve_o_grab_ao_pai(self) -> None:
        estado: dict[str, object] = {}

        def sobre_o_alerta(pai: ctk.CTkToplevel) -> None:
            self._clicar("Sim", delay=200)
            estado["aninhado"] = confirm_dialog(pai, "Aninhado", "Sobre outro modal?")
            estado["grab"] = self.root.grab_current()
            _find_button(pai, "OK").invoke()

        self._quando_abrir(sobre_o_alerta)
        alert_dialog(self.root, "Pai", "Alerta pai")

        self.assertIs(True, estado["aninhado"])
        self.assertIsNotNone(estado["grab"], "o modal pai deveria reaver o grab")
        self.assertIsNone(self.root.grab_current(), "nenhum grab deveria sobrar no fim")


class TamanhoEPosicaoTest(unittest.TestCase):
    """A conta do ``dialog_layout`` — pura, sem abrir janela.

    Marcada fora do ``gui`` de propósito: é aritmética, e é ela que decide se o
    rodapé do diálogo fica dentro da tela a 160%.
    """

    def test_a_160_por_cento_o_pedido_encolhe_para_caber(self) -> None:
        # O caso concreto do P3-10: `geometry("900x700")` num notebook 1366x768.
        # A 160%, o customtkinter entrega 1440x1120 ao Tk — maior que a tela.
        largura, altura = fitted_size((900, 700), scale=1.6, screen=(1366, 768))
        self.assertLessEqual(largura * 1.6, 1366)
        self.assertLessEqual(altura * 1.6, 768)

    def test_a_100_por_cento_um_dialogo_pequeno_passa_intacto(self) -> None:
        self.assertEqual((420, 320), fitted_size((420, 320), scale=1.0, screen=(1920, 1080)))

    def test_nunca_encolhe_abaixo_do_piso_de_legibilidade(self) -> None:
        # Tela minuscula: e melhor o modal vazar um pouco do que virar faixa.
        self.assertEqual(MIN_SIZE, fitted_size((900, 700), scale=4.0, screen=(320, 240)))

    def test_modal_sobre_janela_na_borda_nao_sai_da_tela(self) -> None:
        # Centralizar sobre uma janela encostada na borda jogaria metade do
        # modal para fora — e a metade que sai e sempre a de baixo, a dos botoes.
        x, y = centered_position((600, 400), owner=(1300, 700, 600, 400), screen=(1366, 768))
        self.assertLessEqual(x + 600, 1366)
        self.assertLessEqual(y + 400, 768)
        self.assertGreaterEqual(min(x, y), 0)

    def test_geometria_sai_no_formato_do_tk(self) -> None:
        self.assertEqual("600x400", geometry_string((600, 400)))
        self.assertEqual("600x400+10+20", geometry_string((600, 400), (10, 20)))


@pytest.mark.gui
class DialogCanonicoTest(unittest.TestCase):
    """O ``Dialog`` da F5.8: Esc, saída e ordem dos botões."""

    root: ctk.CTk

    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.root = create_tk_window(ctk.CTk)
        except TclError as exc:  # pragma: no cover - ambiente sem display
            raise unittest.SkipTest(f"Tk indisponivel: {exc}") from exc
        cls.root.geometry("400x300+80+80")
        cls.root.update()

    @classmethod
    def tearDownClass(cls) -> None:
        cancel_pending_callbacks(cls.root)
        try:
            cls.root.destroy()
        except TclError:  # pragma: no cover
            pass
        release_dead_ctk_windows()

    def tearDown(self) -> None:
        for window in list(self.root.winfo_children()):
            if isinstance(window, ctk.CTkToplevel):
                try:
                    window.destroy()
                except Exception:
                    pass
        release_dead_ctk_windows()

    def test_escape_fecha_o_dialogo(self) -> None:
        # ~16 dos 21 dialogos ad-hoc nao tinham este binding (P3-10).
        dialogo = Dialog(self.root, "Teste", size=(400, 300))
        # O Tk **nao entrega evento de teclado a janela ainda nao mapeada**, e
        # um `update()` solto nao garante o mapeamento: sozinho o teste passa,
        # na suite inteira (maquina ocupada) falha. `wait_visibility()` seria a
        # espera certa, mas **bloqueia para sempre** se o gerenciador de
        # janelas nao mapear — trocar uma falha intermitente por um travamento
        # e pior. Dai a espera limitada.
        for _ in range(50):
            if dialogo.winfo_ismapped():
                break
            dialogo.update()
        dialogo.focus_force()
        dialogo.update()
        dialogo.event_generate("<Escape>")
        self.root.update()
        self.assertFalse(dialogo.winfo_exists())

    def test_fechar_devolve_o_grab_ao_modal_pai(self) -> None:
        pai = Dialog(self.root, "Pai", size=(400, 300))
        self.root.update()
        filho = Dialog(pai, "Filho", size=(300, 200))
        self.root.update()
        filho.close()
        self.root.update()
        self.assertIsNotNone(self.root.grab_current(), "o pai deveria reaver o grab")
        pai.close()
        self.root.update()

    def test_ordem_dos_botoes_e_canonica_independente_da_chamada(self) -> None:
        """[secundário…][perigo][primário] — mesmo declarando fora de ordem."""
        dialogo = Dialog(self.root, "Ordem", size=(400, 300))
        barra = actions_bar(
            dialogo,
            primary=("Salvar", lambda: None),
            danger=("Excluir", lambda: None),
            secondary=[("Revisar", lambda: None)],
            close_text="Fechar",
        )
        self.root.update()
        rotulos = [w.cget("text") for w in barra.winfo_children()]
        self.assertEqual(["Fechar", "Revisar", "Excluir", "Salvar"], rotulos)

    def test_saida_segura_pode_ser_pedida_sozinha(self) -> None:
        """O conserto do "diálogo sem botão de saída": só ``close_text`` basta."""
        dialogo = Dialog(self.root, "Só fechar", size=(400, 300))
        barra = actions_bar(dialogo, close_text="Fechar")
        self.root.update()
        self.assertEqual(["Fechar"], [w.cget("text") for w in barra.winfo_children()])
        barra.winfo_children()[0].invoke()
        self.root.update()
        self.assertFalse(dialogo.winfo_exists())

    def test_dialogo_cabe_na_tela(self) -> None:
        tela = (self.root.winfo_screenwidth(), self.root.winfo_screenheight())
        dialogo = Dialog(self.root, "Grande", size=(4000, 3000))
        self.root.update()
        self.assertLessEqual(dialogo.winfo_width(), tela[0])
        self.assertLessEqual(dialogo.winfo_height(), tela[1])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
