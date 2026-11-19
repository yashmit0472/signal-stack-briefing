"""Offline integration and provenance tests; synthetic fixtures never enter shipped data."""
import os
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import patch

TMP=tempfile.TemporaryDirectory(prefix='signal-tests-')
os.environ['DATABASE_URL']=''
os.environ['SIGNAL_DB_PATH']=TMP.name+'/tests.db'
os.environ['EXTERNAL_SCHEDULER']='1'

from store_db import init,save,items,get,now
from intelligence import credibility,priority,in_window,qualifies_for_brief,is_primary_competitor_url
import engine
from collector import record
from imports import chunks

class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): init()
    def setUp(self):
        self.c=save('root','company',{'name':'Fabricated Test Company (TEST ONLY)',
                       'url':'https://test-company.example','research':{'segments':'enterprise customers'},'automation':False})
        self.s=engine.propose(self.c,'Market','https://gov.uk/test','Test Agency', 'Public policy affecting the test segment')
        src=get(self.c,'source',self.s);src['status']='approved';save(self.c,'source',src,self.s)

    def test_rules_separate_provenance_and_model_confidence(self):
        self.assertEqual(credibility('https://gov.uk/policy','Market'),5)
        self.assertEqual(credibility('https://stackoverflow.com/questions/100','Customers'),2)
        self.assertEqual(credibility('https://example.com','Internal'),4)
        self.assertFalse(is_primary_competitor_url('https://reddit.com/r/example','https://test-company.example'))
        self.assertFalse(is_primary_competitor_url('https://test-company.example/about','https://test-company.example'))
        self.assertTrue(is_primary_competitor_url('https://provider.example/pricing','https://test-company.example'))
        self.assertEqual(priority({'relevance':5,'impact':5,'urgency':5,'credibility':5,'recency':5,'novelty':5}),65)

    def test_baseline_deduplication_recent_events_and_historical_filter(self):
        historical=record('https://gov.uk/test','Test Agency','This policy was issued many years ago and is now historical.', '2019-02-01')
        with patch('engine.crawl',return_value=[historical]), patch('engine.analyze') as analyse:
            engine.monitor(self.c)
            analyse.assert_not_called()
            self.assertEqual(items(self.c,'document')[0]['observation_type'],'historical')
            engine.monitor(self.c)
            self.assertTrue(any(x.get('duplicates',0)>=1 for x in items(self.c,'crawl')))
        fresh=record('https://gov.uk/test/current','Test Agency',
            'The agency published a materially new change to the test rules today.', now())
        signal={'index':0,'event':'The agency changed the rules for the test sector',
                'quote':'The agency published a materially new change to the test rules today.',
                'event_date':'unknown','verification':'source-reported','area':'compliance','type':'threat',
                'why':'The test company may need to update internal plans','action':'Confirm whether this applies',
                'owner':'Operations','urgency':5,'impact':4,'relevance':5,'novelty':5}
        with patch('engine.crawl',return_value=[fresh]), patch('engine.model',return_value={'signals':[signal]}):
            engine.monitor(self.c)
        signals=items(self.c,'signal')
        self.assertEqual(len(signals),1)
        self.assertEqual(signals[0]['credibility'],5)
        self.assertEqual(signals[0]['strength'],3)
        self.assertEqual(signals[0]['observation_type'],'recent-publication')
        now_dt=datetime.now(timezone.utc)
        self.assertTrue(qualifies_for_brief(signals[0],now_dt-timedelta(days=7),now_dt))
        stale=dict(signals[0],published='2019-01-01',event_date='unknown',observation_type='historical')
        self.assertFalse(qualifies_for_brief(stale,now_dt-timedelta(days=7),now_dt))
        self.assertFalse(in_window('2019-01-01'))

    def test_missing_quote_is_rejected(self):
        d=record('https://gov.uk/new','New record','The only real document quote is here and nowhere else.',now())
        d.update(source_id=self.s,key='fixture')
        signal={'index':0,'event':'The agency changed a policy relevant to customer demand','quote':'completely fabricated evidence',
                'event_date':'unknown','verification':'source-reported','area':'commercial','type':'neutral',
                'why':'May affect planning','action':'Review','owner':'CEO','urgency':4,'impact':4,'relevance':4,'novelty':4}
        with patch('engine.model',return_value={'signals':[signal]}):
            self.assertEqual(engine.analyze(self.c,get(self.c,'source',self.s),[d]),0)
        self.assertFalse(items(self.c,'signal'))

    def test_interview_adapts_and_never_sends_all_questions_at_once(self):
        def response(instruction,payload,limit=0,schema=None):
            if isinstance(payload,dict) and 'eligible_topics' in payload:
                chosen=next(iter(payload['eligible_topics']))
                return {'topic':chosen,'question':f'Which {chosen} issue matters most to your customers now?', 'followup_to':''}
            return {'signals':[]}
        with patch('engine.model',side_effect=response):
            for n in range(10):
                engine.next_question(self.c)
                qs=items(self.c,'question')
                self.assertEqual(len(qs),n+1)
                engine.next_question(self.c)
                self.assertEqual(len(items(self.c,'question')),n+1)
                current=get(self.c,'question',self.c+'-question-'+str(n+1))
                current['answer']='Test answer '+str(n+1)
                save(self.c,'question',current,current['id'])
            engine.next_question(self.c)
            self.assertEqual(len(items(self.c,'question')),10)
        self.assertEqual(len({q['question'] for q in items(self.c,'question')}),10)
        self.assertEqual(len({q['topic'] for q in items(self.c,'question')}),10)

    def test_chunked_upload_keeps_end_of_file(self):
        body='Earlier feedback. '*500+'FINAL IMPORTANT REQUEST: searchable exports'
        out=chunks([('row 1',body)])
        self.assertGreater(len(out),1)
        self.assertIn('FINAL IMPORTANT REQUEST',out[-1])

    def test_monthly_audit_uses_stackexchange_api_not_html_robots(self):
        s=engine.propose(self.c,'Customers','https://stackoverflow.com/questions/987654/test','A dated user discussion','Users discuss onboarding')
        src=get(self.c,'source',s);src['status']='approved';save(self.c,'source',src,s)
        with patch('engine.crawl',return_value=[record('https://stackoverflow.com/questions/987654/test','Question','A mock Stack API question','2026-11-18')]),patch('engine.model',return_value={'recommendations':[]}),patch('engine.discover',return_value=None),patch('collector.allowed',return_value=1),patch('collector.fetch') as fetch:
            fetch.return_value.__enter__.return_value.status_code=200
            engine.audit(self.c)
        result=items(self.c,'audit')[0]
        self.assertIn('API reachable',[x['health'] for x in result['checks']])

    def test_report_generation_does_not_invent_opportunities(self):
        key=engine.brief(self.c)
        r=get(self.c,'brief',key)
        self.assertEqual(r['signals'],[])
        self.assertTrue(any('Fewer than three' in s for s in r['synthesis']['limitations']))

if __name__=='__main__':
    unittest.main(verbosity=2)
