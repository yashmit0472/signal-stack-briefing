"""Discover reusable public material with explicit attribution and monitoring reasons."""
import requests
from store_db import items,save
from engine import propose,context,model
from urllib.parse import urljoin
def candidates(c):
    ctx=context(c)
    plan=model('Generate 4 precise GOV.UK search phrases for regulatory guidance or dated announcements relevant to this company in the UK. Also give 3 one- or two-word searches for relevant customer questions and appropriate Stack Exchange site slugs. Return JSON with gov array of strings and forums array of objects with site and q. Avoid tangential subjects.',ctx,700)
    out={}
    for phrase in plan['gov'][:4]:
        res=requests.get('https://www.gov.uk/api/search.json',params={'q':phrase,'count':9,'fields':'title,link,description,public_timestamp'},timeout=18)
        res.raise_for_status()
        for x in res.json()['results']:
            path=x.get('link','')
            if path.startswith('/') and not path.startswith('//'):
                out['https://www.gov.uk'+path]=('Market',x['title'],x.get('description',''),x.get('public_timestamp',''),'GOV.UK · Open Government Licence v3 unless otherwise stated')
    for term in plan.get('forums',[])[:3]:
        res=requests.get('https://api.stackexchange.com/2.3/search/advanced',params={'site':term['site'],'q':term['q'],'pagesize':7,'sort':'activity','order':'desc'},timeout=15)
        if res.ok:
            for x in res.json().get('items',[]):
                if x.get('content_license'):
                    out[x['link']]=('Customers',x['title'],term['q'],'',x['content_license']+' · '+x.get('owner',{}).get('display_name','Stack Exchange user'))
    rows=list(out.items())
    for start in range(0,len(rows),12):
        group=rows[start:start+12]
        schema={'type':'OBJECT','properties':{'matches':{'type':'ARRAY','items':{'type':'OBJECT','properties':{'index':{'type':'INTEGER'},'reason':{'type':'STRING'}},'required':['index','reason']}}},'required':['matches']}
        choices=model('Select only sources materially relevant to this business and justify specifically. Retain zero-based index. Reject unrelated or weak overlap.',[ctx,[(i,k,v[:3]) for i,(k,v) in enumerate(group)]],1300,schema)
        for x in choices['matches']:
            if 0<=x['index']<len(group):
                url,(cat,title,desc,date,license)=group[x['index']]
                propose(c,cat,url,title,x['reason'],licence=license,discoveryEvidence=desc,published=date)
def approve_open(c):
    for s in items(c,'source'):
        if s.get('licence') and s['status']=='proposed':
            s['status']='approved'
            save(c,'source',s,s['id'])

