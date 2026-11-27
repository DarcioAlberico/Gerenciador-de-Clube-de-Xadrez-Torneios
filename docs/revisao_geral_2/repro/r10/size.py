import sqlite3,sys
c=sqlite3.connect('file:'+sys.argv[1]+'?mode=ro',uri=True)
rows=[]
for (n,) in c.execute("select name from sqlite_master where type='table'"):
    try: rows.append((c.execute(f'select count(*) from "{n}"').fetchone()[0], n))
    except Exception: pass
print(sorted(rows, reverse=True)[:6])
try: print('dbstat', c.execute("select name, sum(pgsize)/1048576.0 from dbstat group by name order by 2 desc limit 5").fetchall())
except Exception as e: print('dbstat indisponivel', e)
print('snapshots', c.execute("select count(*) from official_rating_snapshots").fetchall() if c.execute("select 1 from sqlite_master where name='official_rating_snapshots'").fetchone() else '-')
