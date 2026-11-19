"""Regression tests: full calendar-week snapshots do not exclude previously briefed signals.

All fixtures are synthetic and only enter an isolated temporary test database.
"""
import os
import tempfile
import unittest
from datetime import datetime, date, timedelta, timezone
from unittest.mock import patch

os.environ['DATABASE_URL'] = ''

from store_db import init, save, get, items
from intelligence import previous_week_window, date_in_window, qualifies_for_brief
from collector import record
import engine

NOW = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)


class WeeklyBriefTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='weekly-brief-tests-')
        self.env = patch.dict(os.environ, {'DATABASE_URL': '', 'SIGNAL_DB_PATH': self.tmp.name + '/isolated.db'})
        self.env.start()
        init()
        self.company = save('root', 'company', {
            'name': 'Weekly Test Company', 'url': 'https://example.org',
            'settings': {'zone': 'Asia/Kolkata'}, 'automation': False})

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def signal(self, published, discovered='2026-11-19T04:00:00+00:00', **overrides):
        body = {'event': 'Evidence of a material policy change in the relevant market',
                'quote': 'Source evidence confirms a change to the relevant market policy',
                'why': 'The company needs to review compliance impact',
                'action': 'Review the compliance roadmap', 'owner': 'Operations',
                'source': 'Public regulator', 'url': 'https://example.org/notice',
                'category': 'Market', 'type': 'threat', 'published': published,
                'discovered': discovered, 'event_date': 'unknown',
                'observation_type': 'recent-publication',
                'verification': 'source-reported', 'rank': 50, 'impact': 4,
                'urgency': 4, 'credibility': 3, 'strength': 4}
        body.update(overrides)
        key = save(self.company, 'signal', body)
        return key

    def test_previous_completed_week_uses_local_calendar_boundaries(self):
        start, end, monday, sunday = previous_week_window('Asia/Kolkata', at=NOW)
        self.assertEqual((monday, sunday), ('2026-11-09', '2026-11-15'))
        self.assertEqual(start.isoformat(), '2026-11-08T18:30:00+00:00')
        self.assertEqual(end.isoformat(), '2026-11-15T18:30:00+00:00')
        self.assertTrue(date_in_window('2026-11-09', start, end, 'Asia/Kolkata'))
        self.assertTrue(date_in_window('2026-11-15', start, end, 'Asia/Kolkata'))
        self.assertFalse(date_in_window('2026-11-16', start, end, 'Asia/Kolkata'))
        self.assertTrue(date_in_window('2026-11-15T18:29:59+00:00', start, end, 'Asia/Kolkata'))
        self.assertFalse(date_in_window('2026-11-15T18:30:00+00:00', start, end, 'Asia/Kolkata'))

    def test_date_only_publication_respects_negative_utc_offset(self):
        start, end, monday, sunday = previous_week_window('America/Los_Angeles', at=NOW)
        self.assertEqual((monday, sunday), ('2026-11-09', '2026-11-15'))
        self.assertTrue(date_in_window('2026-11-09', start, end, 'America/Los_Angeles'))
        self.assertFalse(date_in_window('2026-11-08', start, end, 'America/Los_Angeles'))

    def test_repeat_brief_includes_same_signal_and_reuses_ai_synthesis(self):
        old_discovery = '2026-11-10T08:00:00+00:00'
        current_discovery = '2026-11-19T08:00:00+00:00'
        # Discovered during previous brief, and again after end of the reporting week.
        first_id = self.signal('2026-11-11', old_discovery)
        second_id = self.signal('2026-11-12', current_discovery, category='Competitors')
        result = {'summary': 'Weekly synthesis covers both items.',
                  'top_ids': [first_id, second_id], 'watch_ids': [], 'limitations': []}
        with patch('engine.model', return_value=result) as llm:
            first = get(self.company, 'brief', engine.brief(self.company, as_of=NOW))
            second = get(self.company, 'brief', engine.brief(self.company, as_of=NOW))
            self.assertEqual(llm.call_count, 1)
        self.assertNotEqual(first['id'], second['id'])
        self.assertEqual({s['id'] for s in first['signals']}, {first_id, second_id})
        self.assertEqual({s['id'] for s in second['signals']}, {first_id, second_id})
        self.assertEqual(second['comparison']['repeated_from_previous_brief'], 2)
        self.assertEqual(second['comparison']['not_in_previous_brief'], 0)
        self.assertEqual((second['week_start'], second['week_end']), ('2026-11-09', '2026-11-15'))
        self.assertEqual(second['synthesis']['summary'], 'Weekly synthesis covers both items.')
        self.assertTrue(second['synthesis_reused'])

    def test_new_week_never_automatically_carries_prior_week_events(self):
        saved_id = self.signal('2026-11-11')
        first = get(self.company, 'brief', engine.brief(self.company, as_of=NOW))
        week_later = get(self.company, 'brief', engine.brief(
            self.company, as_of=NOW + timedelta(days=7)))
        self.assertEqual([s['id'] for s in first['signals']], [saved_id])
        self.assertEqual(week_later['signals'], [])
        self.assertEqual(week_later['week_start'], '2026-11-16')
        self.assertTrue(week_later['synthesis']['limitations'])

    def test_observed_changes_count_in_week_but_undated_historical_articles_do_not(self):
        observation = self.signal('', '2026-11-13T10:00:00+00:00',
                                  observation_type='observed-change')
        internal = self.signal('', '2026-11-14T06:00:00+00:00',
                               observation_type='internal-upload', category='Internal')
        old = self.signal('', '2026-11-11T04:00:00+00:00',
                          observation_type='historical')
        rejected = self.signal('2026-11-10', review_status='rejected')
        needs_review = self.signal('2026-11-14', review_status='needs_review')
        start, end, *_ = previous_week_window(at=NOW)
        for eligible in (observation, internal):
            self.assertTrue(qualifies_for_brief(get(self.company, 'signal', eligible),
                                                start, end, 'Asia/Kolkata'))
        for excluded in (old, rejected, needs_review):
            self.assertFalse(qualifies_for_brief(get(self.company, 'signal', excluded),
                                                 start, end, 'Asia/Kolkata'))

    def test_edited_company_context_triggers_fresh_synthesis(self):
        self.signal('2026-11-11')
        result = {'summary': 'New context-aware summary',
                  'top_ids': [], 'watch_ids': [], 'limitations': []}
        with patch('engine.model', return_value=result) as llm:
            engine.brief(self.company, as_of=NOW)
            company = get('root', 'company', self.company)
            company['operator_context'] = 'We are now targeting enterprise buyers.'
            save('root', 'company', company, self.company)
            new_brief = get(self.company, 'brief', engine.brief(self.company, as_of=NOW))
            self.assertEqual(llm.call_count, 2)
        self.assertFalse(new_brief['synthesis_reused'])

    def test_monitor_analyses_last_week_publication_on_first_collection(self):
        start, end, monday, sunday = previous_week_window('Asia/Kolkata')
        pub = (date.fromisoformat(monday) + timedelta(days=2)).isoformat()
        source_id = engine.propose(self.company, 'Market', 'https://example.org/notice',
                                   'Public regulator', 'Regulation relevant to the company')
        source = get(self.company, 'source', source_id)
        source['status'] = 'approved'
        save(self.company, 'source', source, source_id)
        d = record('https://example.org/notice', 'New rule',
                   'The rule changes compliance obligations for market participants', pub)
        with patch('engine.crawl', return_value=[d]), patch('engine.analyze', return_value=1) as analyse:
            engine.monitor(self.company)
            analyse.assert_called_once()
        docs = items(self.company, 'document')
        self.assertEqual(docs[0]['baseline'], False)
        self.assertEqual(docs[0]['observation_type'], 'recent-publication')


if __name__ == '__main__':
    unittest.main(verbosity=2)
