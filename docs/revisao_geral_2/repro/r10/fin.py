from src.services.finance_service import FinanceService
import inspect
fn = [n for n, _ in inspect.getmembers(FinanceService) if "amount" in n or "money" in n or "parse" in n]
print(fn)
