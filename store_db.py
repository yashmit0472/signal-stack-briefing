import os, json, uuid, sqlite3, sys
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime, timezone
sys.path.insert(0,str(Path(__file__).parent/'.packages'))
from dotenv import load_dotenv
load_dotenv()
URL=os.getenv('DATABASE_URL')
def now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')
@contextmanager
def db():
    if URL:
        import psycopg2
        conn=psycopg2.connect(URL)
    else:
        db_file=Path(os.getenv('SIGNAL_DB_PATH','data/signals.db'))
        db_file.parent.mkdir(parents=True,exist_ok=True)
        conn=sqlite3.connect(str(db_file),timeout=30)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
def query(sql,args=(),read=False):
    with db() as conn:
        cur=conn.cursor()
        cur.execute(sql.replace('?','%s') if URL else sql,args)
        return cur.fetchall() if read else []
def init():
    query('CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, company TEXT NOT NULL, kind TEXT NOT NULL, stamp TEXT NOT NULL, body TEXT NOT NULL)')
    query('CREATE INDEX IF NOT EXISTS by_company ON records(company,kind,stamp)')
def save(company,kind,body,key=None):
    key=key or uuid.uuid4().hex
    query('INSERT INTO records(id,company,kind,stamp,body) VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body', (key,company,kind,now(),json.dumps(body)))
    return key
def items(company,kind):
    return [dict(json.loads(b),id=i,created=t) for i,t,b in query('SELECT id,stamp,body FROM records WHERE company=? AND kind=? ORDER BY stamp DESC,id',(company,kind),True)]
def get(company,kind,key):
    return next(x for x in items(company,kind) if x['id']==key)

