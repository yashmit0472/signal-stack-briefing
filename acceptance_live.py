"""Isolated acceptance tests. Test inputs never enter demonstration records."""
import os
os.environ.setdefault('SIGNAL_DB_PATH','tmp/acceptance.db')
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
        existing=next((p for p in items('root','company') if p.get('research') and p['name']=='TEST ONLY — Buffer'),None)
        if existing:
            c=existing['id']
            await client.post('/c/'+c+'/do/interview')
        else:
            response=await client.post('/company',data={'name':'TEST ONLY — Buffer','url':'https://buffer.com/'})
            c=response.headers['location'].split('/')[2].split('?')[0]
        assert items(c,'question'),items(c,'run')
        questions=[q['question'] for q in items(c,'question') if 'answer' in q]
        for n in range(len(questions),10):
            pending=next(q for q in items(c,'question') if 'answer' not in q)
            questions.append(pending['question'])
            answers=[
                'TEST SCENARIO ONLY: evaluate subscription publishing tools for independent bakeries. No private revenue figures are supplied.',
                'TEST SCENARIO ONLY: target small bakery owners scheduling their own social posts, with limited time.',
                '',
                'TEST SCENARIO ONLY: assess whether ease of scheduling is valued more than advanced analytics.',
                'TEST SCENARIO ONLY: alternatives include doing the work manually and other publishing tools; discover their names from evidence.',
                'TEST SCENARIO ONLY: check public evidence for changes in channel integration requirements.',
                'TEST SCENARIO ONLY: investigate connection failures as a possible onboarding risk; frequency is unknown.',
                'TEST SCENARIO ONLY: prioritise understanding onboarding friction over adding another channel.',
                'TEST SCENARIO ONLY: internal reports are unavailable. Do not infer performance metrics.',
                'TEST SCENARIO ONLY: help decide which onboarding documentation to investigate first.'
            ]
            answer=answers[n]
            response=await client.post('/c/'+c+'/do/answer',data={'id':pending['id'],'answer':answer})
            assert response.status_code==303
        assert len(set(questions))==10
        assert any(q['answer']=='Skipped as confidential' for q in items(c,'question'))
        q=items(c,'question')[-1]
        await client.post('/c/'+c+'/do/answer',data={'id':q['id'],'answer':'TEST SCENARIO EDIT: focus on marketing agencies managing multiple client accounts.'})
        assert items(c,'revision')
        assert len(items(c,'question'))==10
        RESULTS.append({'test':'ten-question interview, skip, edit, no duplicate questions','passed':True,'questions':questions,'company':c})
        from openpyxl import Workbook
        import xlwt
        from reportlab.pdfgen import canvas
        text='TEST FIXTURE ONLY. Three fictional support cases report difficulty connecting multiple client accounts. A fourth fictional case requests a clearer onboarding checklist. These are software test inputs and must never appear as real company intelligence.'
        fixtures={'fixture.txt':text.encode(),'fixture.csv':('count,feedback\n0,No lost deals recorded\n3,Difficulty connecting multiple client accounts\n1,Request clearer onboarding checklist\n').encode()}
        b=io.BytesIO();w=Workbook();w.active.append(['count','feedback']);w.active.append([0,'No lost deals recorded']);w.save(b);fixtures['fixture.xlsx']=b.getvalue()
        b=io.BytesIO();w=xlwt.Workbook();sh=w.add_sheet('Feedback');sh.write(0,0,'TEST FIXTURE');sh.write(1,0,text);w.save(b);fixtures['fixture.xls']=b.getvalue()
        b=io.BytesIO();pdf=canvas.Canvas(b);pdf.drawString(40,780,'TEST FIXTURE ONLY');pdf.drawString(40,760,'Three fictional cases report difficulty connecting multiple client accounts.');pdf.save();fixtures['fixture.pdf']=b.getvalue()
        for name,raw in fixtures.items():
            res=await client.post('/c/'+c+'/do/upload',files={'file':(name,raw)},data={'consent':'on'})
            assert res.status_code==303
            assert any(u['name']==name for u in items(c,'upload'))
            assert any(d['title']==name for d in items(c,'document'))
        RESULTS.append({'test':'CSV XLS XLSX PDF TXT upload endpoints and stored evidence','passed':True,'analysis_runs':items(c,'run')[:5]})
        await client.post('/c/'+c+'/do/discover')
        assert items(c,'source')
        await client.post('/c/'+c+'/do/context',data={'context':'TEST CONTEXT CHANGE: focus exclusively on agencies managing client approvals and collaboration, instead of independent bakeries.'})
        assert items(c,'audit')
        RESULTS.append({'test':'unfamiliar company discovery and context reassessment','sources':len(items(c,'source')),'audits':items(c,'audit'),'runs':items(c,'run')[:3]})
    Path('test-evidence').mkdir(exist_ok=True)
    Path('test-evidence/live-acceptance.json').write_text(json.dumps(RESULTS,indent=2),encoding='utf-8')
    print('Saved isolated live test results',flush=True)
if __name__=='__main__':
    try:asyncio.run(main())
    finally:
        Path('test-evidence').mkdir(exist_ok=True)
        Path('test-evidence/live-acceptance.json').write_text(json.dumps(RESULTS,indent=2),encoding='utf-8')
