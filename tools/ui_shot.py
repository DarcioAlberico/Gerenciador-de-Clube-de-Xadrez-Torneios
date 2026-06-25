"""Launcher de screenshots de UI (utilitário de dev / QA visual).

Abre o AlbericusApp sobre uma CÓPIA DESCARTÁVEL do banco, contornando a tela de
login (opera como admin — `current_operator` já trata admin por padrão), para
capturar telas reais SEM alterar dados de produção nem exigir senha.

Uso:
    python tools/ui_shot.py [metodo_show]      ex.: python tools/ui_shot.py show_pairings

Smoke test (sobe, espera 2.5s e fecha sozinho, sem mainloop infinito):
    SHOT_SMOKE=1 python tools/ui_shot.py show_pairings
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.core.database import Database  # noqa: E402
from src.ui.app import AlbericusApp  # noqa: E402


def main() -> None:
    src_db = ROOT / "data" / "albericus.db"
    tmp = Path(tempfile.mkdtemp(prefix="albericus_shot_"))
    tmp_db = tmp / "albericus.db"
    if src_db.exists():
        shutil.copy2(src_db, tmp_db)

    db = Database(db_path=tmp_db, backup_dir=tmp / "backups")
    app = AlbericusApp(db=db)

    # --- Bypass de login: opera como admin sem tocar na tabela users ---
    app.security_service._current_user = {
        "id": "0",
        "username": "Administrador",
        "role": "admin",
    }
    try:
        app.login_frame.destroy()
    except Exception:
        pass

    app.resizable(True, True)
    app.minsize(980, 640)
    try:
        app.state("zoomed")
    except Exception:
        pass
    app._build_menu()
    app._build_statusbar()
    app._build_content()
    app._register_shortcuts()

    # Seleciona um torneio com dados para telas que exigem torneio ativo.
    try:
        tournaments = app.db.list_tournaments()
        chosen = next(
            (t for t in tournaments if t.get("status") == "running"),
            tournaments[0] if tournaments else None,
        )
        if chosen:
            app._set_current_tournament(int(chosen["id"]))
    except Exception:
        pass

    target = sys.argv[1] if len(sys.argv) > 1 else "show_visual_dashboard"
    try:
        getattr(app, target, app.show_club)()
    except Exception:
        try:
            app.show_club()
        except Exception:
            pass
    try:
        app._refresh_statusbar()
    except Exception:
        pass

    if os.environ.get("SHOT_SMOKE"):
        app.after(2500, app.destroy)

    app.mainloop()


if __name__ == "__main__":
    main()
