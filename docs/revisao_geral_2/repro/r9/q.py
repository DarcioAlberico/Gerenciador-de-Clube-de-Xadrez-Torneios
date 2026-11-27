import sqlite3,sys
c=sqlite3.connect(sys.argv[1])
for t,col in [("certificate_templates","name"),("learning_levels","name"),("certificate_backgrounds","name")]:
    try: print(t,[r[0] for r in c.execute(f"select {col} from {t}")])
    except Exception as e: print(t,e)
