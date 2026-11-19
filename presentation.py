"""Readable labels for stored research and monitoring results."""
from datetime import datetime

LABELS = {
    'products': 'Products and services', 'segments': 'Who the company serves',
    'positioning': 'How the company describes itself',
    'company_claims': 'Claims made by the company',
    'assumptions': 'Assumptions to confirm', 'unknowns': 'Questions still to answer',
    'source-reported': 'Reported by the source', 'unconfirmed': 'Needs verification',
    'proposed': 'Waiting for your approval', 'approved': 'Approved for monitoring',
    'removed': 'Removed', 'ok': 'Checked successfully', 'failed': 'Could not finish',
    'complete': 'Finished', 'running': 'In progress',
    'partial failure': 'Finished with some issues',
    'research': 'Company research', 'discover': 'Finding useful sources',
    'monitor': 'Checking sources for updates', 'brief': 'Preparing your brief',
    'audit': 'Reviewing source quality', 'interview': 'Preparing your next question',
    'relevance': 'Fit with your business', 'impact': 'Potential business impact',
    'urgency': 'How soon to act', 'credibility': 'Source reliability',
    'recency': 'How recent the information is', 'novelty': 'How much is new',
    'strength': 'Strength of the evidence',
}

def label(value):
    text = str(value)
    if text.startswith('upload:'):
        return 'Analysing an uploaded document'
    return LABELS.get(text, text.replace('_', ' ').capitalize())

def readable_date(value):
    if not value:
        return 'Date unavailable'
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return parsed.strftime('%d %b %Y')
    except ValueError:
        return str(value)

def issue(value):
    text = str(value or '')
    if not text:
        return ''
    if '429' in text:
        return 'The service reached its request limit. Try again after the allowance resets.'
    if '503' in text:
        return 'The external service is temporarily unavailable. Try again later.'
    if 'robots' in text.lower() or 'disallowed' in text.lower():
        return 'We could not confirm permission to read this website automatically. Choose another source or check its access rules.'
    if 'timeout' in text.lower() or 'timed out' in text.lower():
        return 'The website or AI service took too long to respond. Try the check again.'
    return 'This step could not finish. Try again or review the technical details below.'
