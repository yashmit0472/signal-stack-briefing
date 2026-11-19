"""Offline audit regressions: no Gemini dependency, no silent source edits."""
import unittest
from unittest.mock import patch
from store_db import init, save, get, items
import engine
from jobs import execute


class AuditRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init()

    def setUp(self):
        self.company = save('root', 'company', {
            'name': 'Audit fixture (test only)', 'url': 'https://example.com',
            'operator_context': 'student visas and university admissions',
            'research': {'segments': 'international students'}, 'automation': False,
        })
        self.sid = engine.propose(self.company, 'Market',
                                  'https://regulator.example/news', 'Student visa agency',
                                  'Public international student visa guidance for university admissions')
        source = get(self.company, 'source', self.sid)
        source['status'] = 'approved'
        save(self.company, 'source', source, self.sid)

    def _offline_audit(self):
        with patch('collector.allowed', return_value=1), patch('collector.fetch') as fetch, \
             patch('engine.model', side_effect=AssertionError('Audit must not call Gemini')) as ai, \
             patch('engine.discover', side_effect=AssertionError('Audit must not launch full discovery')) as discovery, \
             patch('engine.search', return_value=[]):
            fetch.return_value.__enter__.return_value.status_code = 200
            result = engine.audit(self.company)
            ai.assert_not_called()
            discovery.assert_not_called()
            return result

    def test_audit_survives_provider_outage_and_saves_source_health(self):
        with patch('collector.allowed', return_value=1), patch('collector.fetch') as fetch, \
             patch('engine.model', side_effect=RuntimeError('Gemini HTTP 503')):
            fetch.return_value.__enter__.return_value.status_code = 200
            execute(self.company, 'audit', False)
        run = next(r for r in items(self.company, 'run') if r['job'] == 'audit')
        self.assertEqual(run['status'], 'complete')
        report = items(self.company, 'audit')[0]
        self.assertEqual(report['checks'][0]['health'], 'HTTP 200')
        self.assertIn('Rule-based', report['review_method'])
        self.assertIn('relevance', report['reviews'][0])
        self.assertEqual(get(self.company, 'source', self.sid)['status'], 'approved')

    def test_context_change_flags_old_source_without_removing_it(self):
        self._offline_audit()
        p = get('root', 'company', self.company)
        p['operator_context'] = 'domestic scholarship opportunities for working adults'
        save('root', 'company', p, self.company)
        save(self.company, 'revision', {'kind': 'business-context',
             'previous': 'student visas and university admissions',
             'current': p['operator_context']})
        self._offline_audit()
        latest = items(self.company, 'audit')[0]
        decision = next(r for r in latest['reviews'] if r['source_id'] == self.sid)
        self.assertEqual(decision['recommendation'], 'review')
        self.assertLessEqual(decision['relevance'], 2)
        self.assertEqual(get(self.company, 'source', self.sid)['status'], 'approved')
        self.assertTrue(latest['changed_relevance'])

    def test_context_discovery_proposes_new_sources_and_respects_deprioritization(self):
        self._offline_audit()
        p = get('root', 'company', self.company)
        p['operator_context'] = 'Prioritize domestic scholarships. Deprioritize student visa guidance.'
        save('root', 'company', p, self.company)
        save(self.company, 'revision', {'kind': 'business-context',
             'previous': 'student visas and university admissions',
             'current': p['operator_context']})
        new_url = 'https://funding.example/scholarships'
        hits = [
            {'url': new_url, 'title': 'Domestic scholarships', 'content': 'Eligibility for domestic scholarships'},
            {'url': new_url + '?utm_source=search', 'title': 'Domestic scholarships',
             'content': 'Eligibility for domestic scholarships'},
            {'url': 'https://other.example/visa', 'title': 'Domestic scholarships and visa guidance',
             'content': 'Student visa guidance and domestic scholarships'},
        ]
        with patch('collector.allowed', return_value=1), patch('collector.fetch') as fetch, \
             patch('engine.search', return_value=hits) as search:
            fetch.return_value.__enter__.return_value.status_code = 200
            engine.audit(self.company)
            latest = items(self.company, 'audit')[0]
            self.assertEqual([x['url'] for x in latest['new_candidate_details']], [new_url])
            self.assertNotIn('visa', search.call_args.args[0])
            engine.audit(self.company)
            search.assert_called_once()
        source = get(self.company, 'source', self.sid)
        self.assertEqual(source['status'], 'approved')
        self.assertEqual(source['relevance_review']['recommendation'], 'review')
        self.assertIn('Deprioritized topics', source['relevance_review']['reason'])

    def test_candidates_are_only_new_to_audit_and_duplicates_reported(self):
        first = engine.propose(self.company, 'Customers', 'https://forum.example/thread?utm_source=a',
                               'Candidate A', 'Students discussing course admissions')
        second = engine.propose(self.company, 'Customers', 'https://forum.example/thread?utm_source=b',
                                'Candidate B', 'Students discussing course admissions')
        self._offline_audit()
        latest = items(self.company, 'audit')[0]
        self.assertEqual({x['id'] for x in latest['new_candidate_details']}, {first, second})
        self.assertEqual(len(latest['duplicate_groups']), 1)
        self._offline_audit()
        latest = items(self.company, 'audit')[0]
        self.assertFalse(latest['new_candidate_details'])
        third = engine.propose(self.company, 'Customers', 'https://forum.example/new',
                               'Candidate C', 'Newly proposed issue')
        self._offline_audit()
        latest = items(self.company, 'audit')[0]
        self.assertEqual([x['id'] for x in latest['new_candidate_details']], [third])

    def test_single_url_error_is_a_health_result_not_failed_audit(self):
        with patch('collector.allowed', side_effect=RuntimeError('robots.txt blocked')):
            engine.audit(self.company)
        latest = items(self.company, 'audit')[0]
        self.assertIn('robots.txt blocked', latest['checks'][0]['health'])
        self.assertEqual(latest['reviews'][0]['recommendation'], 'review')


if __name__ == '__main__':
    unittest.main(verbosity=2)
