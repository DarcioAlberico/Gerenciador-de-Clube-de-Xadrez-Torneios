"""
stress_monitor.py
=================
Janela de status do teste de stress 10k.

Lê ``tests/stress_progress.json`` (gravado por ``tools/stress_runner.py``) e
exibe o andamento em tempo real: progresso, falhas, timeouts, throughput, ETA
e os últimos torneios concluídos. A janela é redimensionável e pode ser
minimizada/maximizada normalmente pela barra de título.

O botão "Encerrar teste" cria ``tests/stress_stop.flag``, pedindo ao runner que
pare graciosamente (salvando relatório parcial). "Fechar janela" fecha apenas
o monitor — a corrida continua em segundo plano.

Uso:
    .venv\\Scripts\\python.exe tools\\stress_monitor.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import customtkinter as ctk

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
ROOT          = Path(__file__).resolve().parent.parent
PROGRESS_PATH = ROOT / "tests" / "stress_progress.json"
STOP_FLAG     = ROOT / "tests" / "stress_stop.flag"

REFRESH_MS    = 750     # intervalo de atualização da janela
STALE_SECONDS = 30      # sem atualização além disso ⇒ alerta de travamento

STATUS_STYLE = {
    "running": ("⏳ Em execução…", "#f9a93a"),
    "done":    ("✅ Concluído",    "#3ad17a"),
    "stopped": ("⏹ Encerrado",     "#e0a030"),
    "error":   ("❌ Erro",          "#e55"),
}


# ---------------------------------------------------------------------------
# Camada PURA — leitura e formatação (sem widgets, testável)
# ---------------------------------------------------------------------------

def read_progress(path: Path = PROGRESS_PATH) -> dict[str, Any] | None:
    """Lê o json de progresso. Devolve None se ausente/ilegível."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def fmt_secs(seconds: float | None) -> str:
    """Formata segundos como '1h 02m 03s' / '4m 05s' / '6s'."""
    if seconds is None:
        return "—"
    s = int(seconds)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"


def fmt_recent_line(r: dict[str, Any]) -> str:
    """Uma linha monoespaçada descrevendo um torneio concluído."""
    mark = "✓" if r.get("ok") else "✗"
    idx = int(r.get("index", 0))
    j = int(r.get("players", 0))
    rnd = int(r.get("rounds", 0))
    ms = int(r.get("ms", 0) or 0)
    head = f"#{idx:>5}  {j:>2}j {rnd}r  {mark}  {ms:>6}ms"
    if not r.get("ok"):
        phase = r.get("phase", "") or "?"
        ftype = r.get("ftype", "") or "?"
        return f"{head}  ✗ {phase}/{ftype}"
    return f"{head}  {r.get('rounds_done', 0)}r ok"


def derive_view(prog: dict[str, Any] | None, now: float) -> dict[str, Any]:
    """Transforma o json de progresso em valores prontos para a tela.

    Pura: recebe o payload + o instante atual e devolve strings/cores/flags.
    Não toca em widgets, então pode ser testada isoladamente.
    """
    if not prog:
        return {
            "waiting": True,
            "status_text": "Aguardando o teste gravar progresso…",
            "status_color": "gray",
            "bar": 0.0,
            "count_text": "0 / 0  (0%)",
            "metrics": {},
            "recent_lines": [],
            "freshness_text": "Aguardando início…",
            "freshness_color": "gray",
            "finished": False,
        }

    status = str(prog.get("status", "running"))
    total = int(prog.get("total", 0) or 0)
    completed = int(prog.get("completed", 0) or 0)
    pct = (100.0 * completed / total) if total else 0.0
    bar = min(1.0, max(0.0, completed / total)) if total else 0.0

    if status == "error":
        status_text = STATUS_STYLE["error"][0]
        status_color = STATUS_STYLE["error"][1]
    else:
        status_text, status_color = STATUS_STYLE.get(status, ("…", "gray"))

    eta_val = prog.get("eta_s")
    metrics = {
        "Falhas":     (f"{int(prog.get('failures', 0)):,}  "
                       f"({float(prog.get('failure_pct', 0.0)):.2f}%)",
                       "#e55" if int(prog.get("failures", 0)) else "gray80"),
        "Timeouts":   (f"{int(prog.get('timeouts', 0)):,}",
                       "#e55" if int(prog.get("timeouts", 0)) else "gray80"),
        "Warnings":   (f"{int(prog.get('warnings', 0)):,}", "gray80"),
        "Throughput": (f"{float(prog.get('throughput', 0.0)):.2f}/s", "gray80"),
        "Decorrido":  (fmt_secs(prog.get("elapsed_s")), "gray80"),
        "Restante":   (fmt_secs(eta_val) if status == "running" else "—", "gray80"),
        "Workers":    (f"{int(prog.get('workers', 0))}", "gray80"),
    }

    recent_lines = [fmt_recent_line(r) for r in prog.get("recent", [])]

    finished = status in ("done", "stopped", "error")
    ts = float(prog.get("ts", now) or now)
    age = max(0.0, now - ts)
    if finished:
        freshness_text = "Teste finalizado."
        freshness_color = "gray"
    elif age > STALE_SECONDS:
        freshness_text = f"⚠ Sem atualização há {int(age)}s — possível travamento."
        freshness_color = "#e55"
    else:
        freshness_text = f"Atualizado há {int(age)}s."
        freshness_color = "gray"

    return {
        "waiting": False,
        "status_text": status_text,
        "status_color": status_color,
        "bar": bar,
        "count_text": f"{completed:,} / {total:,}  ({pct:.1f}%)",
        "metrics": metrics,
        "recent_lines": recent_lines,
        "freshness_text": freshness_text,
        "freshness_color": freshness_color,
        "finished": finished,
        "error": prog.get("error"),
    }


# ---------------------------------------------------------------------------
# Janela
# ---------------------------------------------------------------------------

class StressMonitor(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Albericus — Stress 10k (monitor)")
        self.geometry("580x560")
        self.minsize(460, 420)          # redimensionável: min/maximizar livres
        self._metric_values: dict[str, ctk.CTkLabel] = {}
        self._stopping = False
        self._build()
        self._refresh()

    # -- construção da UI ---------------------------------------------------
    def _build(self) -> None:
        pad = {"padx": 14}

        self._status = ctk.CTkLabel(
            self, text="Aguardando início…",
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        self._status.pack(anchor="w", pady=(14, 4), **pad)

        self._bar = ctk.CTkProgressBar(self, height=18)
        self._bar.set(0.0)
        self._bar.pack(fill="x", pady=4, **pad)

        self._count = ctk.CTkLabel(self, text="0 / 0  (0%)",
                                   font=ctk.CTkFont(size=14))
        self._count.pack(anchor="w", pady=(0, 8), **pad)

        # métricas em grade 2 colunas (rótulo : valor)
        metrics = ctk.CTkFrame(self, fg_color="transparent")
        metrics.pack(fill="x", **pad)
        names = ["Falhas", "Timeouts", "Warnings", "Throughput",
                 "Decorrido", "Restante", "Workers"]
        for i, name in enumerate(names):
            row, col = divmod(i, 2)
            cell = ctk.CTkFrame(metrics, fg_color="transparent")
            cell.grid(row=row, column=col, sticky="w", padx=(0, 24), pady=2)
            ctk.CTkLabel(cell, text=f"{name}:", text_color="gray",
                         width=92, anchor="w").pack(side="left")
            val = ctk.CTkLabel(cell, text="—", anchor="w",
                               font=ctk.CTkFont(size=13, weight="bold"))
            val.pack(side="left")
            self._metric_values[name] = val

        ctk.CTkLabel(self, text="Torneios recentes:", text_color="gray",
                     anchor="w").pack(anchor="w", pady=(10, 0), **pad)
        self._recent = ctk.CTkTextbox(
            self, height=170, font=ctk.CTkFont(family="Consolas", size=12),
            activate_scrollbars=True,
        )
        self._recent.pack(fill="both", expand=True, pady=4, **pad)
        self._recent.configure(state="disabled")

        self._freshness = ctk.CTkLabel(self, text="", text_color="gray",
                                       font=ctk.CTkFont(size=12))
        self._freshness.pack(anchor="w", pady=(0, 4), **pad)

        # rodapé: botões
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(side="bottom", fill="x", pady=(0, 12), **pad)
        self._stop_btn = ctk.CTkButton(
            footer, text="Encerrar teste", fg_color="#a33", hover_color="#c44",
            command=self._stop,
        )
        self._stop_btn.pack(side="left")
        ctk.CTkButton(footer, text="Fechar janela", command=self.destroy).pack(side="right")

    # -- ações --------------------------------------------------------------
    def _stop(self) -> None:
        """Pede parada graciosa criando o flag que o runner observa."""
        try:
            STOP_FLAG.write_text("stop", encoding="utf-8")
        except Exception:
            pass
        self._stopping = True
        self._stop_btn.configure(text="Encerrando…", state="disabled")

    # -- atualização periódica ---------------------------------------------
    def _set_recent(self, lines: list[str]) -> None:
        self._recent.configure(state="normal")
        self._recent.delete("1.0", "end")
        self._recent.insert("1.0", "\n".join(lines) if lines else "—")
        self._recent.configure(state="disabled")

    def _refresh(self) -> None:
        view = derive_view(read_progress(), time.time())

        self._status.configure(text=view["status_text"], text_color=view["status_color"])
        self._bar.set(view["bar"])
        self._count.configure(text=view["count_text"])

        for name, label in self._metric_values.items():
            if name in view["metrics"]:
                text, color = view["metrics"][name]
                label.configure(text=text, text_color=color)

        self._set_recent(view["recent_lines"])
        self._freshness.configure(text=view["freshness_text"],
                                  text_color=view["freshness_color"])

        if view["finished"] and not self._stopping:
            self._stop_btn.configure(state="disabled")

        self.after(REFRESH_MS, self._refresh)


def main() -> None:
    ctk.set_appearance_mode("dark")
    StressMonitor().mainloop()


if __name__ == "__main__":
    main()
