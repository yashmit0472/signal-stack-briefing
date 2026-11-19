"""Geography-aware discovery using permitted public APIs and primary sources."""
from datetime import datetime, timedelta, timezone
import requests
from engine import context, model, propose, search


def candidates(company):
    ctx=context(company)
    shape={'type':'OBJECT','properties':{
        'geography':{'type':'STRING'},'uk_relevant':{'type':'BOOLEAN'},
        'official_queries':{'type':'ARRAY','items':{'type':'STRING'}},
        'forums':{'type':'ARRAY','items':{'type':'OBJECT','properties':{
            'site':{'type':'STRING'},'q':{'type':'STRING'}},'required':['site','q']}},
        'gov_queries':{'type':'ARRAY','items':{'type':'STRING'}}},
        'required':['geography','uk_relevant','official_queries','forums','gov_queries']}
    plan=model('From company evidence and answers, identify its actual served geography. Return relevant regulatory or industry agency search queries for that geography; use UK government search only if UK operations or UK customer markets are supported. Also generate recent, topical customer-problem queries for Stack Exchange when suitable. Never use forum threads merely because they mention the company.',ctx,1000,shape)
    candidates=[]
    for phrase in plan.get('official_queries',[])[:3]:
        for hit in search(phrase)[:8]:
            candidates.append(('Market',hit['url'],hit.get('title','Government or industry update'),
                               hit.get('content','')[:500],'Public industry or policy source; jurisdiction '+str(plan.get('geography','unknown')),''))
    if plan.get('uk_relevant'):
        for phrase in plan.get('gov_queries',[])[:3]:
            response=requests.get('https://www.gov.uk/api/search.json',params={
                'q':phrase,'count':8,'order':'-public_timestamp','fields':'title,link,description,public_timestamp'},timeout=18)
            response.raise_for_status()
            for row in response.json().get('results',[]):
                path=row.get('link','')
                if path.startswith('/') and not path.startswith('//'):
                    candidates.append(('Market','https://www.gov.uk'+path,row.get('title','GOV.UK update'),
                                       row.get('description','')[:500],'UK public sector primary source','Open Government Licence v3; verify page terms'))
    earliest=int((datetime.now(timezone.utc)-timedelta(days=365)).timestamp())
    for term in plan.get('forums',[])[:3]:
        site=str(term.get('site','')).strip()
        query=str(term.get('q','')).strip()
        if not site or not query or len(site)>60:continue
        response=requests.get('https://api.stackexchange.com/2.3/search/advanced',params={
            'site':site,'q':query,'pagesize':10,'sort':'creation','order':'desc','fromdate':earliest},timeout=18)
        if not response.ok:
            continue
        for item in response.json().get('items',[]):
            if item.get('content_license') and item.get('link'):
                candidates.append(('Customers',item['link'],item.get('title','Community discussion'),query,
                                   'Recent public customer question about '+query,item['content_license']))
    seen=set()
    for start in range(0,len(candidates),12):
        group=candidates[start:start+12]
        schema={'type':'OBJECT','properties':{'matches':{'type':'ARRAY','items':{'type':'OBJECT','properties':{
            'index':{'type':'INTEGER'},'reason':{'type':'STRING'}},'required':['index','reason']}}},'required':['matches']}
        selected=model('Choose only sources that materially relate to company decisions and target geography. Reject stale, unrelated and vague pages. Write a company-specific reason. Use supplied zero-based indexes.',
                       [ctx,[(i,x[0],x[2],x[3]) for i,x in enumerate(group)]],1300,schema)
        for row in selected.get('matches',[]):
            i=row.get('index')
            if not isinstance(i,int) or not 0<=i<len(group):continue
            cat,url,title,excerpt,source_reason,licence=group[i]
            if url in seen:continue
            seen.add(url)
            propose(company,cat,url,title,row.get('reason') or source_reason,
                    discoveryEvidence=excerpt,licence=licence)


def approve_open(company):
    """Explicit approval remains a user operation, never a side effect of discovery."""
    return 0
