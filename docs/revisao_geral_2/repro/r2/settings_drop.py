import tempfile
from pathlib import Path
from src.core.database import Database
from src.services.import_service import ImportService
tmp = Path(tempfile.mkdtemp())
db = Database(tmp / "a.db", backup_dir=tmp / "b")
svc = ImportService(db)
svc.save_mapping_profile("Forms do clube", {"name": "Nome completo", "rating": "Rating"})
print("perfis depois de salvar:", svc.list_mapping_profiles())
db.save_app_settings({"registration_form_prefill_base": "https://docs.google.com/forms/x", "registration_form_tournament_entry": "entry.1"})
s = db.get_app_settings()
print("form base:", repr(s.get("registration_form_prefill_base")), "entry:", repr(s.get("registration_form_tournament_entry")))
