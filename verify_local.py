"""Read-only live dashboard and isolated parser checks for the local rehearsal."""
import io,json,sys
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from store_db import items
from imports import read_upload
from openpyxl import Workbook
from engine import competitor_profiles
def main():
    base='http://127.0.0.1:8076'
    companies=items('root','company')
    assert requests.get(base,timeout=5).ok
    book=Workbook()
    book.active.append(['reported issue','evidence'])
    buf=io.BytesIO();book.save(buf)
    assert read_upload('example.xlsx',buf.getvalue())[0][1]=='reported issue | evidence'
    assert read_upload('example.csv',b'a,b\n1,2')[1][1]=='1 | 2'
    assert read_upload('example.txt',b'parser check')[0][1]=='parser check'
    rows=[]
    for p in companies:
        c=p['id'];url=base+'/c/'+c
        for tab in ['overview','profile','sources','feed','reports','activity','settings']:
            assert requests.get(url,params={'tab':tab},timeout=10).ok,tab
        r=items(c,'brief')[0]
        res=requests.get(url+'/report/'+r['id'],timeout=10);res.raise_for_status()
        assert len(BeautifulSoup(res.content,'html.parser').select('h2'))==10
        docs=items(c,'document')
        for s in r['signals']:
            assert any(s['quote'] in d['text'] and s['url']==d['url'] for d in docs),s['id']
        rows.append({'company':p['name'],'tabs_checked':7,'report_sections':10,'report_citations_matched':len(r['signals']),'competitor_candidates':len(competitor_profiles(c))})
    print(json.dumps(rows,indent=2))
if __name__=='__main__':main()
