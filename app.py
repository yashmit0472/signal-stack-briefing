import os,secrets,base64,json,uuid
from urllib.parse import quote
from pathlib import Path
from fastapi import FastAPI,Request,HTTPException,BackgroundTasks
from fastapi.responses import HTMLResponse,RedirectResponse,PlainTextResponse,Response
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment,FileSystemLoader,select_autoescape
from store_db import init,save,items,get,now
from engine import propose,CATS,analyze,competitor_profiles,evidence_coverage
from collector import record
from jobs import execute,due,DEFAULTS,recover_interrupted
from imports import read_upload,chunks
import threading
import pytz
app=FastAPI(docs_url=None,redoc_url=None)
templates=Environment(loader=FileSystemLoader('templates'),autoescape=select_autoescape())
from presentation import label, readable_date, issue
templates.filters.update(label=label, readable_date=readable_date, issue=issue)
app.mount('/static',StaticFiles(directory='static'),name='static')
scheduler_stop=threading.Event()
scheduler_thread=None
def scheduler_loop():
    while not scheduler_stop.is_set():
        try:
            due()
        except Exception as exc:
            print('Scheduler tick failed:', type(exc).__name__, str(exc)[:150], flush=True)
        scheduler_stop.wait(60)
@app.on_event('startup')
def start():
    init()
    if not os.getenv('EXTERNAL_SCHEDULER'):
        global scheduler_thread
        recover_interrupted()
        scheduler_stop.clear()
        scheduler_thread=threading.Thread(target=scheduler_loop,name='signal-stack-scheduler',daemon=True)
        scheduler_thread.start()
@app.on_event('shutdown')
def stop():
    scheduler_stop.set()
@app.middleware('http')
async def protect(req,call):
    pw=os.getenv('APP_PASSWORD','')
    if os.getenv('RENDER') and not pw:return PlainTextResponse('Set APP_PASSWORD before publishing',503)
    if pw:
        expected='Basic '+base64.b64encode(('founder:'+pw).encode()).decode()
        if not secrets.compare_digest(req.headers.get('authorization',''),expected):return Response(status_code=401,headers={'WWW-Authenticate':'Basic realm="Signal Stack"'})
    return await call(req)
def render(name,**values):return HTMLResponse(templates.get_template(name).render(**values))
def back(c,tab='overview'):return RedirectResponse('/c/'+c+'?tab='+tab,303)
def back_sources(c,category,anchor='source-manager-panel'):
    # Full-page fallback for browsers without JavaScript: stay in the right category,
    # and land at the source list instead of jumping to the page heading.
    category=category if category in CATS else 'Customers'
    safe_anchor=anchor if anchor.replace('-','').replace('_','').isalnum() else 'source-manager-panel'
    return RedirectResponse('/c/'+quote(c,safe='')+'?tab=sources&category='+quote(category)+'#'+safe_anchor,303)
@app.get('/')
def home():return render('home.html',companies=items('root','company'))
@app.post('/company')
async def create(req:Request,bg:BackgroundTasks):
    f=await req.form()
    url=str(f['url']).strip()
    if not url.startswith(('http://','https://')):raise HTTPException(400,'Enter the full website URL')
    c=save('root','company',{'name':str(f['name']).strip(),'url':url,'automation':False})
    bg.add_task(execute,c,'research')
    return back(c,'profile')
@app.get('/c/{c}')
def dashboard(c:str,req:Request,tab:str='overview'):
    p=get('root','company',c)
    data={k:items(c,k) for k in ['source','signal','run','crawl','audit','brief','question','upload','action','revision','document']}
    history={s['id']:[x for x in data['crawl'] if x.get('source_id')==s['id'] or x.get('url')==s['url']] for s in data['source']}
    source_docs={s['id']:[x for x in data['document'] if x.get('source_id')==s['id']] for s in data['source']}
    signals=data['signal']
    for field in ['category','competitor','verification','impact','relevance']:
        value=req.query_params.get(field,'')
        if value:signals=[s for s in signals if str(s.get(field,''))==value]
    day=req.query_params.get('date')
    if day:signals=[s for s in signals if s['discovered'].startswith(day)]
    source_category=req.query_params.get('category','Customers')
    if source_category not in CATS:source_category='Customers'
    return render('dashboard.html',p=p,c=c,tab=tab,data=data,competitors=competitor_profiles(c),signals=signals,cats=CATS,source_category=source_category,history=history,source_docs=source_docs,settings={**DEFAULTS,**p.get('settings',{})},coverage=evidence_coverage(c),request=req)
@app.post('/c/{c}/do/{action}')
async def change(c:str,action:str,req:Request,bg:BackgroundTasks):
    p=get('root','company',c)
    f=await req.form()
    if action in ('research','discover','monitor','brief','snapshot','audit','interview'):
        bg.add_task(execute,c,action)
        return back(c,'activity')
    if action=='answer':
        q=get(c,'question',f['id'])
        previous=q.get('answer')
        q['answer']=str(f.get('answer','')).strip() or 'Skipped as confidential'
        if previous is not None and previous!=q['answer']:
            save(c,'revision',{'kind':'interview-answer','question':q['question'],'number':q.get('number'),'previous':previous,'current':q['answer']})
        save(c,'question',q,q['id'])
        bg.add_task(execute,c,'interview')
        return back(c,'profile')
    if action=='context':
        before=p.get('operator_context','')
        updated=str(f['context']).strip()
        if updated!=before:
            p['operator_context']=updated
            save('root','company',p,c)
            save(c,'revision',{'kind':'business-context','previous':before,'current':updated})
        bg.add_task(execute,c,'audit')
        return back(c,'activity')
    if action=='add':
        if f['category'] not in CATS:raise HTTPException(400)
        propose(c,f['category'],f['url'],f['title'],f['reason'])
        return back_sources(c,str(f['category']))
    if action=='approve-all':
        # Bulk approval is deliberately restricted to *proposed* public sources
        # in the selected category. It never restores removed sources, approves
        # internal uploads, or launches a crawl without an explicit monitor run.
        category=str(f.get('category',''))
        if category not in CATS[:3]:
            raise HTTPException(400,'Select Customers, Competitors or Market')
        for source in items(c,'source'):
            if source.get('category')==category and source.get('status')=='proposed':
                source['status']='approved'
                save(c,'source',source,source['id'])
        return back_sources(c,category)
    if action=='source':
        s=get(c,'source',f['id'])
        if f['status'] not in ('approved','removed','proposed'):raise HTTPException(400)
        s['status']=f['status'];save(c,'source',s,s['id'])
        return back_sources(c,s['category'],'source-'+s['id'] if s['status']!='removed' else 'source-manager-panel')
    if action=='review':
        sig=get(c,'signal',str(f['id']))
        state=str(f.get('review_status',''))
        if state not in ('approved','needs_review','rejected','unreviewed'):raise HTTPException(400,'Invalid editorial review status')
        original=sig.get('review_status','unreviewed')
        sig['review_status']=state
        sig['review_note']=str(f.get('note','')).strip()[:500]
        save(c,'signal',sig,sig['id'])
        save(c,'editorial_review',{'signal':sig['id'],'previous':original,'current':state,'note':sig['review_note']})
        return back(c,'feed')
    if action=='settings':
        zone=f['zone'];pytz.timezone(zone)
        from datetime import datetime
        datetime.strptime(f['time'],'%H:%M')
        p['settings']={'zone':zone,'time':f['time'],'monitor_hours':max(1,int(f['monitor_hours'])),'refresh_days':max(1,int(f['refresh_days'])),'audit_day':min(28,max(1,int(f['audit_day'])))}
        p['automation']='enabled' in f;save('root','company',p,c)
        return back(c,'settings')
    if action=='upload':
        file=f['file'];raw=await file.read(5000001)
        if len(raw)>5000000:raise HTTPException(413,'File limit is 5 MB')
        try:
            rows=read_upload(file.filename,raw)
            parts=chunks(rows)
        except (ValueError,UnicodeDecodeError,ImportError) as exc:
            raise HTTPException(400,str(exc)[:220]) from exc
        if not parts:raise HTTPException(400,'No readable text in this upload')
        uid=save(c,'upload',{'name':file.filename,'rows':rows,'chunks':len(parts)})
        url='/c/'+c+'/upload/'+uid
        source_id=uid+'-source'
        src={'id':source_id,'category':'Internal','title':file.filename,'url':url,
             'reason':'Founder-provided internal evidence; not externally corroborated','status':'approved'}
        save(c,'source',src,source_id)
        for i,part in enumerate(parts,1):
            d=record(url,file.filename+' · part '+str(i)+'/'+str(len(parts)),part,'')
            d.update(source_id=source_id,observation_type='internal-upload',baseline=False)
            save(c,'document',d)
        if f.get('consent'):
            bg.add_task(execute,c,'upload:'+source_id)
        return back_sources(c,'Internal')
    if action=='track':
        get(c,'signal',f['id'])
        save(c,'action',{'signal':f['id'],'status':f['status']},c+f['id'])
        return back(c,'reports')
    raise HTTPException(404)
@app.get('/c/{c}/upload/{uid}')
def upload(c:str,uid:str):return PlainTextResponse('\n'.join(k+' '+v for k,v in get(c,'upload',uid)['rows']))
@app.get('/c/{c}/report/{key}')
def report(c:str,key:str,download:bool=False):
    r=get(c,'brief',key)
    response=render('report.html',r=r,c=c,actions={a['signal']:a['status'] for a in items(c,'action')},download=download)
    if download:response.headers['Content-Disposition']='attachment; filename="monday-brief.html"'
    return response

