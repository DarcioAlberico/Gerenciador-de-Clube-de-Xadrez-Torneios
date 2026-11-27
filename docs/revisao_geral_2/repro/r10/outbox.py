import sqlite3,sys
for p in sys.argv[1:]:
    c=sqlite3.connect('file:'+p+'?mode=ro',uri=True)
    def q(s):
        try: return c.execute(s).fetchall()
        except Exception as e: return str(e)
    print(p.split('\\')[-1], 'outbox',q('select count(*), sum(length(payload_json)) from sync_outbox'), 'audit',q('select count(*), sum(length(before_json)+length(after_json)) from audit_events'), 'status', q('select status,count(*) from sync_outbox group by status'), 'tourn', q('select count(*) from tournaments'), 'orphan', q('select count(*) from sync_outbox where tournament_id is not null and tournament_id not in (select id from tournaments)'))
