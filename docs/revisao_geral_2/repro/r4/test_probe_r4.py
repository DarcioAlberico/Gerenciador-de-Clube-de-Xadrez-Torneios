"""Sondas do revisor 4 (fluxos do árbitro). Não fazem parte do repositório."""
from __future__ import annotations

from typing import Any
from unittest import mock

import pytest

from tests.test_ui_rgs21_25_rodadas import _RodadasBase

pytestmark = pytest.mark.gui


class SondaR4(_RodadasBase):
    def _viewer(self) -> None:
        self.app.security_service._current_user = {"id": 99, "username": "v", "role": "viewer"}

    def _pendente(self) -> dict[str, Any]:
        return self._mesas()[0]

    # 1. Permissão no painel do árbitro
    def test_viewer_lanca_pelo_painel(self) -> None:
        self._viewer()
        self.assertFalse(self.app.security_service.has_permission("tournament_write"))
        self.app.show_arbitration_panel()
        self.app.update()
        with mock.patch.object(self.app, "_show_error") as erro:
            self.app._save_arbitration_panel_result("1-0")
        res = [p["result"] for p in self._mesas()]
        print("VIEWER painel -> resultados:", res, "erro chamado:", erro.called)
        # contraste: Rodadas recusa
        self.app.show_pairings()
        self.app.update()
        with mock.patch.object(self.app, "_show_error") as erro2:
            self.app._selecionar = None
            self._selecionar_mesa(1)
            self.app.result_option.set("0-1")
            self.app._save_selected_result()
        print("VIEWER Rodadas -> resultados:", [p["result"] for p in self._mesas()], "erro:", erro2.call_args)

    def test_viewer_adia_pelo_painel(self) -> None:
        self._viewer()
        self.app.show_arbitration_panel()
        self.app.update()
        with mock.patch("src.ui.screens.pairing_arbitration.pending.reason_dialog", return_value="x"):
            self.app._arbitration_panel_view().pending.postpone()
        print("VIEWER adiou:", self.db.list_postponed_pairings(self.round_id))

    # 2. Auto-atualização rouba o foco da busca
    def test_refresh_rouba_foco_da_busca(self) -> None:
        self.app.show_arbitration_panel()
        self.app.update()
        self.app.focus_force()
        busca = self.app.arbitration_pending_query_entry
        busca._entry.focus_set()
        self.app.update()
        print("foco antes:", self.app.focus_get())
        self.app._arbitration_auto_refresh()._tick()
        self.app.update()
        foco = self.app.focus_get()
        print("foco depois do tick:", foco)
        foco.event_generate("<Key-1>")
        self.app.update()
        print("resultados apos tecla 1:", [p["result"] for p in self._mesas()])

    # 3. Auto-atualização com o diálogo de correção aberto
    def test_refresh_com_dialogo_de_correcao_aberto(self) -> None:
        self.app.show_arbitration_panel()
        self.app.update()
        visto: dict[str, Any] = {}

        def no_dialogo(dialogo: Any) -> None:
            dialogo.focus_force()
            self.app.update()
            visto["antes"] = str(self.app.focus_get())
            self.app._arbitration_auto_refresh()._tick()
            self.app.update()
            foco = self.app.focus_get()
            visto["depois"] = str(foco)
            visto["toplevel_do_foco"] = str(foco.winfo_toplevel()) if foco else None
            visto["grab"] = str(dialogo.grab_current())
            # tecla real cai na janela com foco
            dialogo.event_generate("<Key-1>")
            self.app.update()
            visto["resultados"] = [p["result"] for p in self._mesas()]
            dialogo.close()

        self._quando_abrir(no_dialogo)
        self.app._arbitration_panel_view().pending.correct_selected()
        print("DIALOGO+REFRESH:", visto)

    # 4. Entrada tardia: a tela de Rodadas atualiza?
    def test_refresh_panel_perde_selecao(self) -> None:
        self.app.show_arbitration_panel()
        self.app.update()
        t = self.app.arbitration_pending_tree
        filhos = t.get_children()
        t.selection_set(filhos[2])
        self.app.update()
        self.app._arbitration_auto_refresh()._tick()
        self.app.update()
        t2 = self.app.arbitration_pending_tree
        print("selecao apos tick:", t2.index(t2.selection()[0]), "(antes 2)")


class SondaR4b(_RodadasBase):
    JOGADORES = 7

    def test_excluir_bye_ja_usado(self) -> None:
        jogadores = self.db.list_players(self.tournament_id)
        # R1 gerada no setUp (7 jogadores -> 1 bye PAB). Lança tudo e fecha.
        for mesa in self._mesas():
            if not mesa["is_bye"]:
                self.servico.update_result(self.tournament_id, int(mesa["id"]), "1-0")
        alvo = next(j for j in jogadores if not any(
            m["is_bye"] and int(m["white_player_id"]) == int(j["id"]) for m in self._mesas()))
        self.servico.request_bye(self.tournament_id, int(alvo["id"]), 2, "H", reason="viagem")
        self.servico.close_round(self.tournament_id, self.round_id)
        r2 = int(self.servico.generate_next_round(self.tournament_id)["id"])
        bye_r2 = [p for p in self.db.get_pairings_for_round(r2) if p["is_bye"] and int(p["white_player_id"]) == int(alvo["id"])]
        print("pairing bye R2:", [(p["result"]) for p in bye_r2])
        print("saldo antes:", self.servico.bye_balance(self.tournament_id, int(alvo["id"])))
        self.app.show_requested_byes()
        self.app.update()
        # acha a view: a tree da registry
        from src.ui.screens.pairing_arbitration.registry import RegistryView
        import gc
        views = [o for o in gc.get_objects() if isinstance(o, RegistryView)]
        view = views[-1]
        item = view.tree.get_children()[0]
        view.tree.selection_set(item)
        with mock.patch.object(self.app, "_confirm_action", return_value=True):
            view._delete_selected()
        print("byes depois:", self.db.list_requested_byes(self.tournament_id))
        print("pairing bye R2 depois:", [(p["result"]) for p in self.db.get_pairings_for_round(r2) if p["is_bye"]])
        print("saldo depois:", self.servico.bye_balance(self.tournament_id, int(alvo["id"])))
        ev = [e["action"] for e in self.db.list_audit_events(self.tournament_id, limit=200)]
        print("eventos com bye:", [a for a in ev if "bye" in a])

    def test_viewer_ajuste_de_pontos(self) -> None:
        self.app.security_service._current_user = {"id": 99, "username": "v", "role": "viewer"}
        from src.ui.screens.pairing_arbitration.adjustments import AdjustmentsPage
        ctrl = self.app._arbitration_controller()
        page = AdjustmentsPage(ctrl, int(self.tournament_id), ctrl.tournament(self.tournament_id))
        campos = {c.key: c for c in page.fields()}
        alvo = campos["target"].values[0] if "target" in campos else None
        print("chaves:", list(campos))
        vals = {}
        for c in page.fields():
            if getattr(c, "values", None):
                vals[c.key] = c.values[0]
        vals.update({k: "1" for k in campos if "points" in k})
        vals.update({k: "Penalidade teste" for k in campos if "reason" in k})
        try:
            page.add(vals)
        except Exception as exc:
            print("add erro:", exc)
        print("VIEWER ajustes:", self.db.list_point_adjustments(self.tournament_id))


class SondaR4c(_RodadasBase):
    JOGADORES = 8

    def test_enter_na_tabela_grava_duas_vezes(self) -> None:
        self._abrir_rodadas()
        self._selecionar_mesa(0)
        self.app.result_option.set("1/2-1/2")
        antes = len(self._eventos("result_updated"))
        self._tecla("<Return>")
        print("ENTER -> resultados:", [p["result"] for p in self._mesas()],
              "eventos result_updated:", len(self._eventos("result_updated")) - antes)

    def test_enter_wo_pergunta_duas_vezes(self) -> None:
        self._abrir_rodadas()
        self._selecionar_mesa(0)
        self.app.result_option.set("1F-0F")
        from src.ui.screens.pairing_arbitration import pending
        with mock.patch.object(pending, "confirm_walkover", return_value=True) as conf:
            self._tecla("<Return>")
        print("ENTER W.O. -> confirmacoes:", conf.call_count, [p["result"] for p in self._mesas()])


class SondaR4d(_RodadasBase):
    def test_enter_rodada_fechada_abre_dialogo_duas_vezes(self) -> None:
        for mesa in self._mesas():
            self.servico.update_result(self.tournament_id, int(mesa["id"]), "1-0")
        self.servico.close_round(self.tournament_id, self.round_id)
        self._abrir_rodadas()
        self._selecionar_mesa(0)
        self.app.result_option.set("0-1")
        from src.ui.screens.pairing_results import correction
        with mock.patch.object(correction, "correction_dialog", return_value=None) as dlg:
            self._tecla("<Return>")
        print("ENTER fechada -> dialogos abertos:", dlg.call_count)


class SondaR4e(_RodadasBase):
    def test_todos_presentes_com_desistente(self) -> None:
        tid = self.tournament_id
        # apaga a R1 para voltar à chamada inicial
        self.servico.delete_generated_round(self.round_id)
        js = sorted(self.db.list_players(tid), key=lambda j: j["id"])
        for j in js[:4]:
            self.servico.set_player_participation(tid, int(j["id"]), "absent")
        self.servico.set_player_participation(tid, int(js[2]["id"]), "withdrawn", "desistiu por doença")
        self._abrir_rodadas()
        sec = self.app._initial_call()
        ordem = [sec.row_map[i] for i in sec.tree.get_children()]
        with mock.patch.object(self.app, "_show_error") as erro:
            sec.mark_all_present()
        print("ordem na tabela:", ordem)
        print("status depois:", [(j["id"], j["player_status"]) for j in sorted(self.db.list_players(tid), key=lambda j: j["id"])])
        print("erro:", erro.call_args)
        # seleção depois de alternar presença
        item = sec.tree.get_children()[1]
        sec.tree.selection_set(item); sec.tree.focus(item)
        sec.toggle_selected()
        print("selecao depois do toggle:", sec.tree.selection(), "foco:", sec.tree.focus())
