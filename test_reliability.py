import os
os.environ['SIGNAL_DB_PATH']='tmp/reliability.db'
os.environ['DATABASE_URL']=''
import unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
from store_db import init,save,items
from jobs import job_due,DEFAULTS,execute,recover_interrupted

class Reliability(unittest.TestCase):
    def test_monday_catchup_before_tuesday_brief_time(self):
        moment=datetime(2026,11,17,6,tzinfo=timezone.utc)
        self.assertTrue(job_due('brief',DEFAULTS,moment,[]))
    def test_success_prevents_duplicate(self):
        moment=datetime(2026,11,17,6,tzinfo=timezone.utc)
        row={'job':'brief','status':'complete','created':'2026-11-16T08:05:00+00:00'}
        self.assertFalse(job_due('brief',DEFAULTS,moment,[row]))
    def test_failed_weekly_retry(self):
        moment=datetime(2026,11,17,6,tzinfo=timezone.utc)
        row={'job':'brief','status':'failed','created':(moment-timedelta(hours=1)).isoformat()}
        self.assertTrue(job_due('brief',DEFAULTS,moment,[row]))
        row['created']=moment.isoformat()
        self.assertFalse(job_due('brief',DEFAULTS,moment,[row]))
    def test_monthly_independent_of_weekly(self):
        moment=datetime(2026,11,18,6,tzinfo=timezone.utc)
        row={'job':'brief','status':'complete','created':moment.isoformat()}
        self.assertTrue(job_due('audit',DEFAULTS,moment,[row]))
    def test_interrupt_and_failure_visible(self):
        init()
        c=save('root','company',{'name':'Isolated scheduler fixture'})
        save(c,'run',{'job':'audit','status':'running'})
        recover_interrupted()
        self.assertEqual(items(c,'run')[0]['status'],'failed')
        with patch('jobs.perform',side_effect=RuntimeError('intentional isolated failure')):
            execute(c,'brief',True)
        self.assertTrue(any(r.get('detail')=='intentional isolated failure' for r in items(c,'run')))
    def test_saved_data_survives_reopen(self):
        init()
        c=save('root','company',{'name':'Persistence fixture','settings':DEFAULTS})
        init()
        self.assertTrue(any(p['id']==c for p in items('root','company')))
    def test_restart_in_new_process(self):
        import subprocess,sys
        init()
        c=save('root','company',{'name':'Process restart fixture','settings':DEFAULTS})
        save(c,'run',{'job':'brief','status':'running'})
        subprocess.run([sys.executable,'-c','from store_db import init; from jobs import recover_interrupted; init(); recover_interrupted()'],check=True)
        self.assertEqual(items(c,'run')[0]['status'],'failed')

if __name__=='__main__':unittest.main(verbosity=2)
