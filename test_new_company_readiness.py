"""Synthetic, isolated tests; no API calls or real company evidence."""
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from jinja2 import Environment, FileSystemLoader

os.environ['DATABASE_URL'] = ''
from store_db import init, save, get, items
from collector import record
from presentation import label, readable_date, issue
import engine

AT = datetime(2026, 11, 19, 12, tzinfo=timezone.utc)


class NewCompanyReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patch_env = patch.dict(os.environ, {
            'DATABASE_URL': '', 'SIGNAL_DB_PATH': self.tmp.name + '/test.db',
            'EXTERNAL_SCHEDULER': '1'})
        self.patch_env.start()
        init()
        self.c = save('root', 'company', {
            'name': 'Example Payments Company (synthetic fixture)',
            'url': 'https://example.org',
            'settings': {'zone': 'Asia/Kolkata'}, 'automation': False})
        self.sid = engine.propose(self.c, 'Market', 'https://example.org/regulation',
                                  'Archived regulation', 'Monitor regulatory updates')

    def tearDown(self):
        self.patch_env.stop()
        self.tmp.cleanup()

    def archive(self):
        source = get(self.c, 'source', self.sid)
        source['status'] = 'approved'
        save(self.c, 'source', source, self.sid)
        doc = record('https://example.org/regulation', 'Archived regulation',
                     'The regulator described a historical change in payments oversight during 2020.',
                     '2020-06-01')
        with patch('engine.crawl', return_value=[doc]):
            engine.monitor(self.c)
        return doc

    def test_proposals_are_not_monitoring_evidence(self):
        coverage = engine.evidence_coverage(self.c)
        self.assertEqual(coverage['candidates'], 1)
        self.assertEqual(coverage['approved_public'], 0)
        self.assertEqual(coverage['checked_public'], 0)
        self.assertEqual(coverage['documents'], 0)
        with patch('engine.model', side_effect=AssertionError('AI not called for empty evidence')):
            key = engine.initial_snapshot(self.c, as_of=AT)
        r = get(self.c, 'brief', key)
        self.assertEqual(r['context_signals'], [])
        self.assertIn('No public sources approved', ' '.join(r['synthesis']['limitations']))

    def test_historical_first_crawl_is_extractable_without_making_weekly_news(self):
        self.archive()
        self.assertEqual(engine.evidence_coverage(self.c)['pending_baseline_analysis'], 1)
        self.assertEqual(engine.evidence_coverage(self.c)['checked_public'], 1)
        quote = 'The regulator described a historical change in payments oversight during 2020.'
        model_output = {'signals': [{
            'index': 0, 'event': 'Historical payments oversight guidance published in 2020',
            'quote': quote, 'event_date': '2020-06-01',
            'verification': 'source-reported', 'area': 'compliance', 'type': 'neutral',
            'why': 'May inform the company’s compliance research',
            'action': 'Check whether the older rule is still operative', 'owner': 'Legal',
            'urgency': 1, 'impact': 3, 'relevance': 4, 'novelty': 1,
        }]}
        with patch('engine.model', return_value=model_output) as llm:
            result = engine.analyze_baseline_context(self.c)
        self.assertEqual(llm.call_count, 1)
        self.assertEqual(result['new_signals'], 1)
        self.assertEqual(engine.evidence_coverage(self.c)['pending_baseline_analysis'], 0)
        snapshot = get(self.c, 'brief', engine.initial_snapshot(self.c, as_of=AT))
        weekly = get(self.c, 'brief', engine.brief(self.c, as_of=AT))
        self.assertEqual(len(snapshot['context_signals']), 1)
        self.assertEqual(weekly['signals'], [])
        self.assertEqual(weekly['context_signals'][0]['event_date'], '2020-06-01')
        self.assertIn(quote, snapshot['context_signals'][0]['quote'])
        self.assertEqual(snapshot['context_signals'][0]['url'], 'https://example.org/regulation')
        html = self.render(snapshot)
        self.assertIn('Initial Intelligence Snapshot', html)
        self.assertNotIn('Reporting week', html)
        self.assertIn('HISTORICAL CONTEXT · NOT NEW', html)

    def test_provider_error_preserves_pending_document_and_is_reported(self):
        self.archive()
        with patch('engine.model', side_effect=RuntimeError('Gemini temporarily unavailable')):
            extraction = engine.analyze_baseline_context(self.c)
        self.assertIn('unavailable', extraction['provider_error'])
        self.assertEqual(engine.evidence_coverage(self.c)['pending_baseline_analysis'], 1)
        snap = get(self.c, 'brief', engine.initial_snapshot(self.c, as_of=AT, context_analysis=extraction))
        self.assertFalse(snap['context_signals'])
        self.assertIn('Baseline extraction could not finish', ' '.join(snap['synthesis']['limitations']))

    def test_snapshot_excludes_unsupported_quotes(self):
        self.archive()
        save(self.c, 'signal', {
            'event': 'A made-up ungrounded claim', 'quote': 'Not present in collected content',
            'url': 'https://example.org/regulation', 'source_id': self.sid,
            'category': 'Market', 'published': '2020-06-01',
            'event_date': '2020-06-01', 'rank': 65, 'verification': 'unconfirmed'})
        snapshot = get(self.c, 'brief', engine.initial_snapshot(self.c, as_of=AT))
        self.assertFalse(snapshot['context_signals'])

    def render(self, report):
        env = Environment(loader=FileSystemLoader(str(Path(__file__).parent / 'templates')))
        env.filters.update(label=label, readable_date=readable_date, issue=issue)
        return env.get_template('report.html').render(
            r=report, c=self.c, download=True, actions={})


if __name__ == '__main__':
    unittest.main(verbosity=2)
