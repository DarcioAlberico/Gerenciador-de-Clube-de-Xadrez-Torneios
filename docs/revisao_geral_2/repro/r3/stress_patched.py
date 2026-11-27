import sys
sys.path.insert(0, r"C:\PythonCurso\Albericus")
sys.path.insert(0, sys.argv[1])
from src.services.pairing import gacrux_trf
from src.services.trf_layout import cell_start, ROUND_CELL_WIDTH
def with_round_cells(line, letters_by_round):
    if not letters_by_round:
        return line
    patched = line
    for number, letter in letters_by_round.items():
        start = cell_start(number)
        if start > len(patched):
            continue
        patched = patched[:start] + f"0000 - {letter}  " + patched[start + ROUND_CELL_WIDTH:]
    return patched
gacrux_trf.with_round_cells = with_round_cells
import stress
for sd in range(0, 3):
    pr = stress.run(sd)
    print(f"seed {sd}: {len(pr)}"); [print("   ", p[:250]) for p in pr]
