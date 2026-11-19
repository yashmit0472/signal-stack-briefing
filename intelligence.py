"""Auditable, model-independent provenance and priority rules."""
from datetime import datetime, timezone, timedelta, time as datetime_time
import pytz
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit
import re

NEWS_DAYS = 7


def parse_date(value):
    if not value or str(value).strip().lower() in ('unknown','none','n/a','undated'):
        return None
    v = str(value).strip()
    try:
        dt = datetime.fromisoformat(v.replace('Z', '+00:00'))
    except ValueError:
        try:
            dt = parsedate_to_datetime(v)
        except (ValueError, TypeError, IndexError):
            dt = None
            # Public-sector websites commonly emit human-readable dates such as
            # '11 November 2026'. Previous reports silently dropped these dates.
            for fmt in ('%Y-%m-%d', '%d %B %Y', '%d %b %Y',
                        '%B %d, %Y', '%b %d, %Y'):
                try:
                    dt = datetime.strptime(v, fmt)
                    break
                except ValueError:
                    pass
            if dt is None:
                return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def in_window(value, *, days=NEWS_DAYS, at=None):
    dt = parse_date(value)
    at = at or datetime.now(timezone.utc)
    return bool(dt and at-timedelta(days=days) <= dt <= at+timedelta(hours=24))


def credibility(url, category=''):
    """Source reliability is derived from provenance, never from the LLM."""
    if category == 'Internal':
        return 4  # Authenticated as founder-provided input; truth is still not assumed.
    host = (urlsplit(url).hostname or '').lower().removeprefix('www.')
    if not host:
        return 1
    if host.endswith(('.gov', '.gov.uk', '.gov.in', '.gov.au', '.gov.sg')) or host in ('gov.uk',):
        return 5
    if host.endswith(('.edu', '.ac.uk', '.edu.au')) or host == 'arxiv.org':
        return 4
    if 'stackexchange.com' in host or host in ('stackoverflow.com','superuser.com','serverfault.com','askubuntu.com','reddit.com'):
        return 2
    if category == 'Internal':
        return 4  # Origin authenticated by upload; accuracy still requires validation.
    if re.search(r'(^|\.)(yahoo|medium|substack|businessinsider|cbinsights)\.', host):
        return 2
    return 3  # Unverified publisher / corporate website, not government-grade truth.


def strength(quote, content, published='', verification=''):
    """Evidence strength checks literal support and provenance, not persuasiveness."""
    if not quote or quote not in content:
        return 0
    score = 2
    if len(quote) >= 70:
        score += 1
    if parse_date(published):
        score += 1
    if str(verification).lower() in ('verified','official-record'):
        score += 1
    return min(5, score)


def clamp(value):
    try: return max(1, min(5, int(value)))
    except (ValueError, TypeError): return 1


def priority(signal):
    # Each factor has a legible contribution; strength is displayed separately.
    weights = {'relevance':3,'impact':3,'urgency':2,'credibility':2,'recency':2,'novelty':1}
    return sum(weights[k]*clamp(signal.get(k,1)) for k in weights)


def previous_week_window(zone='Asia/Kolkata', at=None):
    """UTC half-open bounds for the last COMPLETED Mon–Sun week in company time.

    For example, a Thursday manual run and the upcoming Monday scheduled run
    both report the previous full calendar week, not the previous seven hours/days
    measured backward from the time the button was clicked.
    """
    timezone_obj = pytz.timezone(zone)
    current = at or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    today = current.astimezone(timezone_obj).date()
    monday = today - timedelta(days=today.weekday() + 7)
    following_monday = monday + timedelta(days=7)
    begin = timezone_obj.localize(datetime.combine(monday, datetime_time.min)).astimezone(timezone.utc)
    finish = timezone_obj.localize(datetime.combine(following_monday, datetime_time.min)).astimezone(timezone.utc)
    return begin, finish, monday.isoformat(), (following_monday - timedelta(days=1)).isoformat()


def date_in_window(value, start, end, zone='UTC'):
    """Use a date-only publisher date as a local calendar date, not UTC midnight.

    Timestamped evidence is converted to the reporting window's UTC boundaries.
    The window is [start, end), so midnight on the next Monday is excluded.
    """
    if not value:
        return False
    raw = str(value).strip()
    # Date-only values have no time-zone semantics. Compare the publisher's
    # calendar date with local reporting dates instead of treating it as UTC.
    if (re.fullmatch(r'\d{4}-\d{2}-\d{2}', raw)
            or re.fullmatch(r'\d{1,2} [A-Za-z]+ \d{4}', raw)
            or re.fullmatch(r'[A-Za-z]+ \d{1,2}, \d{4}', raw)):
        parsed = parse_date(raw)
        if parsed is None:
            return False
        tz = pytz.timezone(zone)
        return start.astimezone(tz).date() <= parsed.date() < end.astimezone(tz).date()
    parsed = parse_date(raw)
    return bool(parsed is not None and start <= parsed < end)


def qualifies_for_brief(signal, start, end, zone='UTC'):
    """Include *all* evidence for the selected week, even if previously briefed.

    Publication/event date determines the week for dated public developments.
    Undated page-change observations and internal uploads use their recorded
    observation date. Discovery time never disqualifies a previously saved,
    dated development. Undated historical pages are not mislabelled as news.
    """
    if signal.get('review_status') in ('rejected', 'needs_review'):
        return False
    if signal.get('observation_type') in ('observed-change', 'internal-upload'):
        return date_in_window(signal.get('discovered'), start, end, zone)
    date = signal.get('event_date') if parse_date(signal.get('event_date')) else signal.get('published')
    return date_in_window(date, start, end, zone)


def host(url):
    return (urlsplit(url).hostname or '').lower().removeprefix('www.')


def is_primary_competitor_url(url, focal=''):
    h = host(url)
    if not h or h == host(focal):
        return False
    forbidden = ('reddit.com','quora.com','yahoo.com','wikipedia.org','linkedin.com','facebook.com','instagram.com',
                 'youtube.com','cbinsights.com','crunchbase.com','businessinsider.com','techcrunch.com',
                 'g2.com','capterra.com','alternativeto.net','forbes.com','medium.com','substack.com')
    if any(h == d or h.endswith('.'+d) for d in forbidden):
        return False
    return True
