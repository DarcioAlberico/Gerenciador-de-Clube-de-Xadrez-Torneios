import sys, logging
sys.path.insert(0, r"C:\PythonCurso\Albericus"); sys.path.insert(0, sys.argv[1])
logging.disable(logging.WARNING)
import stress
stress.CFG = {**stress.CFG, "pairing_system": "fide_dutch"}
for sd in range(int(sys.argv[2]), int(sys.argv[3])):
    for n, rounds in ((9, 7), (8, 7), (7, 6)):
        pr = stress.run(sd, n=n, rounds=rounds)
        pr = [p for p in pr if not p.startswith("evento pairing_warning")]
        if pr: print(f"seed {sd} n={n} r={rounds}: {[p[:220] for p in pr]}")
print("fim")
