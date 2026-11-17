import threading,os
from datetime import datetime,timedelta,timezone
import pytz
from store_db import items,get,save,now
from engine import monitor,brief,audit,discover,research,next_question
BUSY=set()
LOCK=threading.Lock()
DEFAULTS={'zone':'Asia/Kolkata','time':'08:00','monitor_hours':24,'refresh_days':7,'audit_day':1}
def perform(c,job):
    if job=='research': research(c);next_question(c)
    elif job=='interview':next_question(c)
    elif job=='discover':discover(c)
    elif job=='monitor':monitor(c)
    elif job=='brief':monitor(c);brief(c)
    elif job=='audit':audit(c)
    else:raise ValueError('Unknown job')
def execute(c,job,scheduled=False):
    with LOCK:
        if c in BUSY:return
        BUSY.add(c)
    key=save(c,'run',{'job':job,'scheduled':scheduled,'status':'running'})
    row={'job':job,'scheduled':scheduled,'started':now()}
    try:
        perform(c,job)
        row['status']='complete'
        if job in ('brief','monitor') and any(x['status']=='failed' and x['created']>=row['started'] for x in items(c,'crawl')):
            row['status']='partial failure'
    except Exception as e:row.update(status='failed',detail=str(e)[:500])
    finally:
        save(c,'run',dict(row,finished=now()),key)
        with LOCK:BUSY.discard(c)
def due():
    for p in items('root','company'):
        c=p['id']
        st=dict(DEFAULTS,**{}) 
        st.update(p.get('settings',{}))
        local=datetime.now(pytz.timezone(st['zone']))
        runs=items(c,'run')
        for job in ('brief','audit','monitor','discover'):
            last=next((datetime.fromisoformat(x['created']).astimezone(local.tzinfo) for x in runs if x['job']==job),None)
            day=local.date()
            weekly=day-timedelta(days=local.weekday())
            monthly=day.replace(day=int(st['audit_day']))
            if job=='brief':ready=local.strftime('%H:%M')>=st['time'] and (not last or last.date()<weekly)
            elif job=='audit':ready=day>=monthly and (not last or last.date()<monthly)
            else:
                interval=timedelta(hours=int(st['monitor_hours'])) if job=='monitor' else timedelta(days=int(st['refresh_days']))
                ready=not last or local-last>=interval
            if ready and p.get('automation',False):execute(c,job,True)

