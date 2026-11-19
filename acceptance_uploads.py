"""Isolated acceptance tests. Test inputs never enter demonstration records."""
import os
os.environ['SIGNAL_DB_PATH']='tmp/acceptance.db'
os.environ['DATABASE_URL']=''
os.environ['EXTERNAL_SCHEDULER']='1'
import asyncio,io,json
from pathlib import Path
import httpx
from store_db import init,items,save
from app import app
from engine import model

RESULTS=[]
async def main():
    init()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        c=save('root','company',{'name':'ISOLATED upload test','url':'https://example.com','research':{}})
        from openpyxl import Workbook
        import xlwt
        from reportlab.pdfgen import canvas
        text='TEST FIXTURE ONLY. Three fictional support cases report difficulty connecting multiple client accounts. A fourth fictional case requests a clearer onboarding checklist. These are software test inputs and must never appear as real company intelligence.'
        fixtures={'fixture.txt':text.encode(),'fixture.csv':('count,feedback\n0,No lost deals recorded\n3,Difficulty connecting multiple client accounts\n1,Request clearer onboarding checklist\n').encode()}
        b=io.BytesIO();w=Workbook();w.active.append(['count','feedback']);w.active.append([0,'No lost deals recorded']);w.save(b);fixtures['fixture.xlsx']=b.getvalue()
        b=io.BytesIO();w=xlwt.Workbook();sh=w.add_sheet('Feedback');sh.write(0,0,'TEST FIXTURE');sh.write(1,0,text);w.save(b);fixtures['fixture.xls']=b.getvalue()
        b=io.BytesIO();pdf=canvas.Canvas(b);pdf.drawString(40,780,'TEST FIXTURE ONLY');pdf.drawString(40,760,'Three fictional cases report difficulty connecting multiple client accounts.');pdf.save();fixtures['fixture.pdf']=b.getvalue()
        for name,raw in fixtures.items():
            res=await client.post('/c/'+c+'/do/upload',files={'file':(name,raw)},data={})
            assert res.status_code==303
            assert any(u['name']==name for u in items(c,'upload'))
            assert any(d['title']==name for d in items(c,'document'))
        RESULTS.append({'test':'CSV XLS XLSX PDF TXT upload endpoints and stored evidence','passed':True,'analysis_runs':items(c,'run')[:5]})
    Path('test-evidence').mkdir(exist_ok=True)
    Path('test-evidence/upload-acceptance.json').write_text(json.dumps(RESULTS,indent=2),encoding='utf-8')
    print('Saved isolated live test results',flush=True)
if __name__=='__main__':
    try:asyncio.run(main())
    finally:
        Path('test-evidence').mkdir(exist_ok=True)
        Path('test-evidence/upload-acceptance.json').write_text(json.dumps(RESULTS,indent=2),encoding='utf-8')
