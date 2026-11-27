import sys
sys.path.insert(0, r"C:\PythonCurso\Albericus")
from src.services.tournament_service import TournamentService
print(TournamentService._validated_categories([{"name":"Juvenil","kind":"age","min_value":15,"max_value":12},{"name":"S","kind":"sex","sex":""},{"name":"T","kind":"tag","tag":""}]))
