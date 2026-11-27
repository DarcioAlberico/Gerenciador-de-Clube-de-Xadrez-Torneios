import sqlite3,sys
c=sqlite3.connect('file:'+sys.argv[1]+'?mode=ro',uri=True)
for t in ("tournaments","tournament_settings"):
    try:
        print(t, [r[1] for r in c.execute(f"pragma table_info({t})")])
    except Exception as e: print(t, e)
