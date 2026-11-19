import threading,os
from datetime import datetime,timedelta,timezone
import pytz
from store_db import items,get,save,now
from engine import monitor,brief,initial_snapshot,audit,discover,research,next_question,analyze_baseline_context,PartialDiscoveryError
BUSY=set()
LOCK=threading.Lock()
DEFAULTS={'zone':'Asia/Kolkata','time':'08:00','monitor_hours':24,'refresh_days':7,'audit_day':1}
def perform(c,job):
    if job.startswith('upload:'):
        from engine import analyze
        uid=job.split(':',1)[1]
        source=get(c,'source',uid)
        pending=[d for d in items(c,'document') if d.get('source_id')==uid and not d.get('analysed')]
        for start in range(0,len(pending),4):
            batch=pending[start:start+4]
            analyze(c,source,batch)
            for document in batch:
                document['analysed']=True
                save(c,'document',document,document['id'])
        return
    if job=='research': research(c);next_question(c)
    elif job=='interview':next_question(c)
    elif job=='discover':discover(c)
    elif job=='monitor':monitor(c)
    elif job=='brief':
        monitor(c)
        baseline_status = analyze_baseline_context(c)
        brief(c, context_analysis=baseline_status)
    elif job=='snapshot':
        monitor(c)
        baseline_status = analyze_baseline_context(c)
        initial_snapshot(c, context_analysis=baseline_status)
    elif job=='audit':
        result = get(c, 'audit', audit(c))
        if result.get('limitations'):
            raise PartialDiscoveryError('Audit saved with limitations. ' + ' | '.join(result['limitations']))
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
    except PartialDiscoveryError as e:
        row.update(status='partial failure',detail=str(e)[:1000])
    except Exception as e:
        row.update(status='failed',detail=str(e)[:1000])
    finally:
        save(c,'run',dict(row,finished=now()),key)
        with LOCK:BUSY.discard(c)
def recover_interrupted():
    """Call once on single-worker app startup after the old process has stopped."""
    for company in items('root','company'):
        for run in items(company['id'],'run'):
            if run['status']=='running':
                run.update(status='failed',detail='Application stopped before this job finished. It will be eligible for retry.',finished=now())
                save(company['id'],'run',run,run['id'])

def job_due(job,st,local,runs):
    matching=[r for r in runs if r['job']==job]
    latest=matching[0] if matching else None
    if latest and latest['status']=='running':
        return False
    if latest and latest['status'] in ('failed','partial failure'):
        finished=datetime.fromisoformat(latest.get('finished',latest['created']))
        if local-finished<timedelta(minutes=30):
            return False
    successful=next((r for r in matching if r['status']=='complete'),None)
    last=datetime.fromisoformat(successful['created']).astimezone(local.tzinfo) if successful else None
    if job=='brief':
        hour,minute=map(int,st['time'].split(':'))
        target=local.replace(hour=hour,minute=minute,second=0,microsecond=0)-timedelta(days=local.weekday())
        return local>=target and (last is None or last<target)
    if job=='audit':
        target=local.replace(day=int(st['audit_day']),hour=0,minute=0,second=0,microsecond=0)
        return local>=target and (last is None or last<target)
    interval=timedelta(hours=int(st['monitor_hours'])) if job=='monitor' else timedelta(days=int(st['refresh_days']))
    return last is None or local-last>=interval

def due():
    for p in items('root','company'):
        c=p['id']
        st=DEFAULTS.copy()
        st.update(p.get('settings',{}))
        local=datetime.now(pytz.timezone(st['zone']))
        runs=items(c,'run')
        for job in ('brief','audit','monitor','discover'):
            ready=job_due(job,st,local,runs)
            if ready and p.get('automation',False):execute(c,job,True)
