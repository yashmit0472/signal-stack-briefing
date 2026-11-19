"""Offline source-approval regression tests. Never use real API keys or source data."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

os.environ['DATABASE_URL'] = ''
os.environ['EXTERNAL_SCHEDULER'] = '1'
from store_db import init, save, get
from engine import propose
from app import app

class BulkSourceApprovalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            'DATABASE_URL': '', 'SIGNAL_DB_PATH': self.tmp.name + '/test.db',
            'EXTERNAL_SCHEDULER': '1', 'APP_PASSWORD': '', 'RENDER': ''})
        self.env.start()
        init()
        self.c = save('root', 'company', {'name': 'Synthetic Acme', 'url':'https://example.org', 'automation':False})
        self.customer_1 = propose(self.c, 'Customers', 'https://example.org/forum1', 'Forum 1', 'Customer feedback')
        self.customer_2 = propose(self.c, 'Customers', 'https://example.org/forum2', 'Forum 2', 'Customer pain points')
        self.customer_removed = propose(self.c, 'Customers', 'https://example.org/removed', 'Removed', 'Not relevant')
        rem = get(self.c, 'source', self.customer_removed)
        rem['status']='removed'; save(self.c, 'source', rem, rem['id'])
        self.market = propose(self.c, 'Market', 'https://example.org/market', 'Market 1', 'Market regulations')
        self.internal = propose(self.c, 'Internal', 'https://example.org/private', 'Internal 1', 'Private file')
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.env.stop()
        self.tmp.cleanup()

    def test_bulk_approves_only_proposed_sources_in_chosen_category(self):
        response = self.client.post(f'/c/{self.c}/do/approve-all', data={'category':'Customers'}, follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertIn('tab=sources&category=Customers#source-manager-panel', response.headers['location'])
        self.assertEqual(get(self.c, 'source', self.customer_1)['status'], 'approved')
        self.assertEqual(get(self.c, 'source', self.customer_2)['status'], 'approved')
        self.assertEqual(get(self.c, 'source', self.customer_removed)['status'], 'removed')
        self.assertEqual(get(self.c, 'source', self.market)['status'], 'proposed')
        self.assertEqual(get(self.c, 'source', self.internal)['status'], 'proposed')
        self.client.post(f'/c/{self.c}/do/approve-all', data={'category':'Customers'})
        self.assertEqual(get(self.c, 'source', self.customer_1)['status'], 'approved')

    def test_bulk_rejects_invalid_and_internal_categories(self):
        for category in ['Internal', 'NotReal', '']:
            response = self.client.post(f'/c/{self.c}/do/approve-all', data={'category':category}, follow_redirects=False)
            self.assertEqual(response.status_code, 400)
        self.assertEqual(get(self.c, 'source', self.internal)['status'], 'proposed')

    def test_single_approval_stays_on_source_and_does_not_approve_neighbors(self):
        response = self.client.post(f'/c/{self.c}/do/source', data={'id': self.customer_1, 'status':'approved'}, follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertIn(f'#source-{self.customer_1}', response.headers['location'])
        self.assertEqual(get(self.c, 'source', self.customer_1)['status'], 'approved')
        self.assertEqual(get(self.c, 'source', self.customer_2)['status'], 'proposed')

    def test_render_contains_bulk_button_and_inplace_script(self):
        r = self.client.get(f'/c/{self.c}?tab=sources&category=Customers')
        self.assertEqual(r.status_code, 200)
        self.assertIn('Approve all proposed (2)', r.text)
        self.assertIn('data-source-action="bulk"', r.text)
        self.assertIn('data-source-action="single"', r.text)
        self.assertIn('/static/source_manager.js', r.text)
        self.assertIn(f'id="source-{self.customer_1}"', r.text)
        js = self.client.get('/static/source_manager.js')
        self.assertEqual(js.status_code, 200)
        self.assertIn('event.preventDefault()', js.text)
        self.assertIn('window.scrollTo(0, beforeY)', js.text)
        internal = self.client.get(f'/c/{self.c}?tab=sources&category=Internal')
        self.assertNotIn('data-source-action="bulk"', internal.text)

if __name__ == '__main__':
    unittest.main(verbosity=2)
