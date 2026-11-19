"""Regression tests for truthful, useful evidence-backed reports.

Synthetic test data is isolated and is never included in a user's saved report.
"""
import os
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

os.environ['DATABASE_URL'] = ''

from store_db import init, save, get
from intelligence import parse_date, date_in_window, previous_week_window
from collector import record
import engine
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from presentation import readable_date, label

NOW = datetime(2026, 11, 19, 8, tzinfo=timezone.utc)


class ContextualBriefTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='contextual-weekly-')
        self.env = patch.dict(os.environ, {'DATABASE_URL': '', 'SIGNAL_DB_PATH': self.temp.name + '/test.db'})
        self.env.start()
        init()
        self.company = save('root', 'company', {
            'name': 'Hypothetical Testing University', 'url': 'https://example.com',
            'settings': {'zone': 'Asia/Kolkata'}, 'automation': False})

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def add(self, day, event, *, text=None, category='Market', review_status=None, type='neutral', discovered='2026-11-18T12:00:00+00:00'):
        text = text or 'Literal supporting statement from an approved public source'
        url = 'https://example.com/' + event.lower().replace(' ', '-')
        document = record(url, event, text + ' and other contextual information', '')
        source_id = 'source-' + event.lower().replace(' ', '-')
        document['source_id'] = source_id
        save(self.company, 'document', document)
        return save(self.company, 'signal', {
            'event': event, 'event_date': day, 'published': '', 'discovered': discovered,
            'quote': text, 'why': 'Possible impact requires review.', 'action': 'Review the source',
            'owner': 'Operations', 'source': event, 'url': url, 'source_id': source_id,
            'category': category, 'rank': 21, 'credibility': 4, 'strength': 4,
            'verification': 'source-reported', 'type': type,
            'review_status': review_status,
        })

    def test_human_readable_publication_date_is_in_local_week(self):
        start, end, *_ = previous_week_window('Asia/Kolkata', at=NOW)
        self.assertEqual(parse_date('11 November 2026').date().isoformat(), '2026-11-11')
        self.assertEqual(parse_date('9 Oct 2026').date().isoformat(), '2026-10-09')
        self.assertTrue(date_in_window('11 November 2026', start, end, 'Asia/Kolkata'))
        self.assertFalse(date_in_window('17 November 2026', start, end, 'Asia/Kolkata'))
        self.assertFalse(date_in_window('1 January 2027', start, end, 'Asia/Kolkata'))
        self.assertFalse(date_in_window('not a date', start, end, 'Asia/Kolkata'))

    def test_brief_separates_weekly_signal_from_dated_history(self):
        current = self.add('11 November 2026', 'New policy guidance')
        old = self.add('13 Aug 2023', 'Prior student objection', category='Customers')
        later = self.add('17 November 2026', 'Later-week policy notice')
        with patch('engine.model', side_effect=RuntimeError('Provider unavailable')):
            report = get(self.company, 'brief', engine.brief(self.company, as_of=NOW))
        self.assertEqual([row['id'] for row in report['signals']], [current])
        self.assertEqual([row['id'] for row in report['context_signals']], [old])
        self.assertNotIn(later, [x['id'] for x in report['context_signals']])
        self.assertEqual(report['week_start'], '2026-11-09')
        self.assertEqual(report['week_end'], '2026-11-15')

    def test_background_must_be_supported_by_original_crawled_document(self):
        good = self.add('2023-05-20', 'Documented older risk')
        unsupported = self.add('2022-01-01', 'Bad quote')
        row = get(self.company, 'signal', unsupported)
        row['quote'] = 'This is not in the original document'
        save(self.company, 'signal', row, unsupported)
        excluded = self.add('2020-01-01', 'Needs editorial review', review_status='needs_review')
        with patch('engine.model', side_effect=AssertionError('should never call AI for zero new signals')):
            report = get(self.company, 'brief', engine.brief(self.company, as_of=NOW))
        self.assertEqual([s['id'] for s in report['context_signals']], [good])
        self.assertFalse(report['signals'])
        self.assertNotIn(unsupported, [x['id'] for x in report['context_signals']])
        self.assertNotIn(excluded, [x['id'] for x in report['context_signals']])

    def test_regenerating_reuses_same_week_and_preserves_history(self):
        current = self.add('11 November 2026', 'Relevant weekly finding')
        old = self.add('2023-04-05', 'Relevant prior finding')
        result = {'summary': 'New guidance matters because it changes oversight expectations.',
                  'top_ids': [current], 'watch_ids': [], 'limitations': []}
        with patch('engine.model', return_value=result) as llm:
            old_brief = get(self.company, 'brief', engine.brief(self.company, as_of=NOW))
            new_brief = get(self.company, 'brief', engine.brief(self.company, as_of=NOW))
        self.assertEqual(llm.call_count, 1)
        self.assertEqual([s['id'] for s in new_brief['signals']], [current])
        self.assertEqual([s['id'] for s in new_brief['context_signals']], [old])
        self.assertTrue(new_brief['synthesis_reused'])
        self.assertEqual(new_brief['comparison']['repeated_from_previous_brief'], 1)

    def test_report_template_marks_history_as_not_new(self):
        self.add('11 November 2026', 'Current policy')
        self.add('10 October 2023', 'Older customer feedback', category='Customers')
        with patch('engine.model', side_effect=RuntimeError('Unavailable')):
            report = get(self.company, 'brief', engine.brief(self.company, as_of=NOW))
        env = Environment(loader=FileSystemLoader(str(Path(__file__).parent / 'templates')))
        env.filters.update(label=label, readable_date=readable_date)
        rendered = env.get_template('report.html').render(r=report, c=self.company, actions={}, download=True)
        self.assertIn('This week', rendered)
        self.assertIn('HISTORICAL CONTEXT · NOT NEW', rendered)
        self.assertIn('Current policy', rendered)
        self.assertIn('Older customer feedback', rendered)
        self.assertIn('11 November 2026', rendered)
        self.assertIn('This week', rendered)

if __name__ == '__main__':
    unittest.main()
