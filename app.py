import os,secrets,base64,json,uuid
from pathlib import Path
from fastapi import FastAPI,Request,HTTPException,BackgroundTasks
from fastapi.responses import HTMLResponse,RedirectResponse,PlainTextResponse,Response
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment,FileSystemLoader,select_autoescape
from store_db import init,save,items,get,now
from engine import propose,CATS,analyze
from collector import record
from jobs import execute,due,DEFAULTS
from imports import read_upload
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
app=FastAPI(docs_url=None,redoc_url=None)
templates=Environment(loader=FileSystemLoader('templates'),autoescape=select_autoescape())
app.mount('/static',StaticFiles(directory='static'),name='static')
scheduler=BackgroundScheduler()
@app.on_event('startup')
def start():
    init()
    if not os.getenv('EXTERNAL_SCHEDULER'):
        scheduler.add_job(due,'interval',minutes=1,max_instances=1)
        scheduler.start()
@app.on_event('shutdown')
def stop():
    if scheduler.running:scheduler.shutdown(wait=False)
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
    data={k:items(c,k) for k in ['source','signal','run','crawl','audit','brief','question','upload','action']}
    signals=data['signal']
    for field in ['category','competitor','verification','impact','relevance']:
        value=req.query_params.get(field,'')
        if value:signals=[s for s in signals if str(s.get(field,''))==value]
    day=req.query_params.get('date')
    if day:signals=[s for s in signals if s['discovered'].startswith(day)]
    return render('dashboard.html',p=p,c=c,tab=tab,data=data,signals=signals,cats=CATS,settings=dict(DEFAULTS,**p.get('settings',{})) if not p.get('settings') else {**DEFAULTS,**p['settings']})
@app.post('/c/{c}/do/{action}')
async def change(c:str,action:str,req:Request,bg:BackgroundTasks):
    p=get('root','company',c)
    f=await req.form()
    if action in ('research','discover','monitor','brief','audit','interview'):
        bg.add_task(execute,c,action)
        return back(c,'activity')
    if action=='answer':
        q=get(c,'question',f['id']);q['answer']=str(f.get('answer','')).strip() or 'Skipped as confidential'
        save(c,'question',q,q['id'])
        bg.add_task(execute,c,'interview')
        return back(c,'profile')
    if action=='add':
        if f['category'] not in CATS:raise HTTPException(400)
        propose(c,f['category'],f['url'],f['title'],f['reason'])
        return back(c,'sources')
    if action=='source':
        s=get(c,'source',f['id'])
        if f['status'] not in ('approved','removed','proposed'):raise HTTPException(400)
        s['status']=f['status'];save(c,'source',s,s['id'])
        return back(c,'sources')
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
        rows=read_upload(file.filename,raw)
        uid=save(c,'upload',{'name':file.filename,'rows':rows})
        url='/c/'+c+'/upload/'+uid
        src={'id':uid,'category':'Internal','title':file.filename,'url':url,'reason':'Founder-provided internal evidence','status':'approved'}
        save(c,'source',src,uid)
        if f.get('consent'):
            docs=[record(url,file.filename,' '.join(loc+' '+txt for loc,txt in rows),'')]
            bg.add_task(analyze,c,src,docs)
        return back(c,'sources')
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

