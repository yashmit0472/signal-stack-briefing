"""Export reviewed public demonstration briefs and measurable collection counts."""
from pathlib import Path
import json
from app import templates
from engine import competitor_profiles
from store_db import items
def export():
    out=Path('samples');out.mkdir(exist_ok=True)
    counts=[]
    for p in items('root','company'):
        c=p['id']
        if p['name'] not in ('MeetUniversity','Fairphone','Ghost'):continue
        rs=items(c,'brief')
        if rs:
            (out/(p['name']+'.html')).write_text(templates.get_template('report.html').render(r=rs[0],actions={},c=c,download=True),encoding='utf-8')
        counts.append({'company':p['name'],'approved':sum(s['status']=='approved' for s in items(c,'source')),'competitor_candidates':len(competitor_profiles(c)),'collected_documents':len(items(c,'document')),'signals_in_latest_brief':len(rs[0]['signals']) if rs else 0,'briefs':len(rs),'saved_questions':len(items(c,'question'))})
    (out/'evidence-counts.json').write_text(json.dumps(counts,indent=2))
    print(counts)
if __name__=='__main__':export()
