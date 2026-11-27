"""R10: valor em dinheiro com ponto de milhar brasileiro vira centavos, calado."""
import tempfile
from pathlib import Path
from src.core.database import Database
from src.services.finance_service import FinanceService
from src.services.prize_service import validated_prizes

for txt in ("1.500", "1.500,00", "1500", "150,50", "nan", "inf"):
    try:
        print(f"finance {txt!r:12} ->", FinanceService._parse_amount(txt, "inválido"))
    except Exception as exc:
        print(f"finance {txt!r:12} -> {type(exc).__name__}: {exc}")
for txt in ("1.000", "nan"):
    try:
        print(f"prize   {txt!r:12} ->", validated_prizes([{"kind": "overall", "rank_from": 1, "amount": txt, "label": "1º geral"}])[0]["amount"])
    except Exception as exc:
        print(f"prize   {txt!r:12} -> {type(exc).__name__}: {exc}")
