"""Idempotently load real, historical demo records into an empty database.

Never invents evidence or overwrites user records. Must be explicitly enabled.
"""
import gzip
import json
import os
import sys
from pathlib import Path
from store_db import init,db,URL


def seed():
    if '--seed' not in sys.argv and os.getenv('SEED_DEMO_ON_START')!='1':
        print('Demo snapshot seeding disabled; set SEED_DEMO_ON_START=1 or pass --seed')
        return
    init()
    archive=Path(__file__).parent/'samples'/'demo_snapshot.json.gz'
    if not archive.exists():
        raise FileNotFoundError('Historical demo snapshot was not packaged: '+str(archive))
    with gzip.open(archive,'rt',encoding='utf-8') as f:
        rows=json.load(f)['records']
    inserted=0
    with db() as connection:
        cursor=connection.cursor()
        cursor.execute('SELECT id FROM records')
        existing={row[0] for row in cursor.fetchall()}
        placeholder='%s' if URL else '?'
        sql='INSERT INTO records(id,company,kind,stamp,body) VALUES('+','.join([placeholder]*5)+') ON CONFLICT(id) DO NOTHING'
        for row in rows:
            if row['id'] in existing:
                continue
            cursor.execute(sql,(row['id'],row['company'],row['kind'],row['stamp'],json.dumps(row['body'],ensure_ascii=False)))
            inserted+=1
    print(f'Historical public-source demo snapshot ready: {inserted} records imported, {len(rows)-inserted} already present.')
    print('IMPORTANT: Past signals are archived; the new brief pipeline filters by actual publication/event date.')

if __name__=='__main__':
    seed()
