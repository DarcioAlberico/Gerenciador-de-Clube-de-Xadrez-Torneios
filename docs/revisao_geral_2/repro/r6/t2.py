from src.services.pairing.tiebreaks import order_player_standings
import inspect; print(inspect.signature(order_player_standings))
def st(i,pts,rk=None,name=None):
    d={"player_id":i,"points":pts,"rating":1500,"name":name or f"P{i}","tiebreak_values":{},"tiebreak_order":[]}
    if rk is not None: d["_gacrux_rank"]=rk
    return d
stats={1:st(1,5.0,1),2:st(2,4.0,2),3:st(3,0.0,None)}  # 3 sem dado do motor
out=order_player_standings(stats,None)
print([(r["player_id"],r["points"]) for r in out])
