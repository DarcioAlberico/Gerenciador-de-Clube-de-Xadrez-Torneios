import sys
sys.path.insert(0, r"C:\PythonCurso\Albericus")
from src.services.norms.report import build_norm_report
from src.services.rating.tables import fide_dp, fide_performance

# Candidato BRA (federation_id vazio, como o cadastro local), 9 adversarios:
# 7 brasileiros SEM federation_id + 1 ARG + 1 URY. Todos IM/GM com rating FIDE 2450.
def p(pid, fed="", title="IM", intl=2450, rating=None, sex="M"):
    return {"id": pid, "name": f"P{pid}", "surname": "", "given_name": "", "federation_id": fed,
            "title": title, "international_rating": intl, "rating": intl if rating is None else rating,
            "national_rating": 0, "sex": sex}

players = [p(1, fed="", title="", intl=2400)]
players += [p(i) for i in range(2, 9)]          # 7 sem federação (BRA de fato)
players += [p(9, fed="ARG"), p(10, fed="URY")]
pairings = [{"white_player_id": 1, "black_player_id": i, "result": "1/2-1/2" if i % 2 else "1-0", "is_bye": 0, "round_number": i - 1}
            for i in range(2, 11)]
rep = [r for r in build_norm_report(players, pairings) if r["player_id"] == 1][0]
print("A) achieved:", rep["achieved"], "federations:", rep["federations"])
for t in rep["titles"]:
    print("  ", t["title"], t["meets"], "own_fed_opp", t["own_federation_opponents"], "missing", t["missing"])

# B) adversarios sem rating FIDE mas com rating local alto -> contam como ratados
players2 = [p(1, fed="BRA", title="", intl=2400)]
players2 += [p(i, fed=["ARG", "URY", "CHI", "BRA"][i % 4], title="GM", intl=0, rating=2500) for i in range(2, 11)]
rep2 = [r for r in build_norm_report(players2, pairings) if r["player_id"] == 1][0]
print("B) avg_opp", rep2["average_opponent"], "unrated_opponents", rep2["unrated_opponents"], "achieved", rep2["achieved"])

print("dp(5/8)", fide_dp(5/8), "dp(3/8)", fide_dp(3/8), "dp(0.625 half-up=63)->95")
