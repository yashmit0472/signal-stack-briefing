import hashlib, ipaddress, socket, threading, time
from urllib.parse import urlsplit,urljoin,urldefrag
from urllib.robotparser import RobotFileParser
import requests
from bs4 import BeautifulSoup
from store_db import now
AGENT='SignalStackBot/1.0'
lock=threading.Lock()
last={}
def safe(url):
    p=urlsplit(url)
    if p.scheme not in ('http','https') or not p.hostname or p.username or p.password or p.port not in (None,80,443):
        raise ValueError('Expected a public HTTP(S) URL')
    for addr in socket.getaddrinfo(p.hostname,p.port or 443,type=socket.SOCK_STREAM):
        if not ipaddress.ip_address(addr[4][0]).is_global:
            raise ValueError('Private address refused')
def fetch(url,delay=1):
    safe(url)
    host=urlsplit(url).hostname
    with lock:
        wait=last.get(host,0)+delay-time.monotonic()
        if wait>0: time.sleep(wait)
        last[host]=time.monotonic()
    return requests.get(url,headers={'User-Agent':AGENT},timeout=(6,15),allow_redirects=False,stream=True)
def content(r):
    data=bytearray()
    for chunk in r.iter_content(32768):
        data.extend(chunk)
        if len(data)>3000000: raise ValueError('Document exceeds collection limit')
    return bytes(data)
def allowed(url):
    p=urlsplit(url)
    with fetch(f'{p.scheme}://{p.netloc}/robots.txt') as r:
        if r.status_code in (404,410): return 1
        if r.status_code!=200: raise ValueError('Robots policy unavailable: '+str(r.status_code))
        policy=RobotFileParser()
        policy.parse(content(r).decode(errors='replace').splitlines())
        if not policy.can_fetch(AGENT,url): raise ValueError('Disallowed by robots.txt')
        delay=policy.crawl_delay(AGENT) or 1
        rate=policy.request_rate(AGENT)
        if rate: delay=max(delay,rate.seconds/rate.requests)
        if delay>30: raise ValueError('Required request interval exceeds worker budget')
        return delay
def crawl(url):
    import feedparser
    import re
    from datetime import datetime,timezone
    p=urlsplit(url)
    match=re.match(r'/questions/(\d+)',p.path)
    if match and (p.hostname in ('stackoverflow.com','serverfault.com','superuser.com','askubuntu.com','mathoverflow.net') or p.hostname.endswith('.stackexchange.com')):
        site=p.hostname.split('.')[0]
        r=requests.get('https://api.stackexchange.com/2.3/questions/'+match[1],params={'site':site,'filter':'withbody'},timeout=18)
        r.raise_for_status()
        data=r.json()
        if data.get('backoff'):time.sleep(data['backoff'])
        result=[]
        for e in data['items']:
            text=BeautifulSoup(e['body'],'html.parser').get_text(' ',strip=True)
            d=record(e['link'],e['title'],text,datetime.fromtimestamp(e['creation_date'],timezone.utc).isoformat())
            d['attribution']=e['owner'].get('display_name','Contributor')+' · '+e.get('content_license','')
            result.append(d)
        return result
    for _ in range(4):
        delay=allowed(url)
        with fetch(url,delay) as r:
            if r.is_redirect:
                url=urljoin(url,r.headers['Location'])
                continue
            r.raise_for_status()
            raw=content(r)
            mime=r.headers.get('Content-Type','')
            break
    else: raise ValueError('Too many redirects')
    entries=feedparser.parse(raw).entries if 'xml' in mime or b'<rss' in raw[:500] or b'<feed' in raw[:500] else []
    if entries:
        return [record(urljoin(url,e.get('link') or url),e.get('title','Feed entry'),BeautifulSoup(e.get('summary',''),'html.parser').get_text(' ',strip=True),e.get('published','')) for e in entries[:15]]
    if raw.startswith(b'%PDF'):
        from io import BytesIO
        from pypdf import PdfReader
        return [record(url,url.split('/')[-1],' '.join(p.extract_text() or '' for p in PdfReader(BytesIO(raw)).pages[:25]),'')]
    soup=BeautifulSoup(raw,'html.parser')
    title=soup.title.get_text(' ',strip=True) if soup.title else url
    date=soup.select_one('meta[property="article:published_time"],meta[name="govuk:first-published-at"]')
    published=date.get('content','') if date else ''
    if not published:
        tag=soup.select_one('.gem-c-published-dates time[datetime]')
        if tag:published=tag.get('datetime','')
    for node in soup.select('script,style,nav,footer,header,aside,noscript'): node.decompose()
    main=soup.select_one('article') or soup.select_one('main') or soup
    return [record(url,title,main.get_text(' ',strip=True),published)]
def record(url,title,body,date):
    body=' '.join(body.split())[:30000]
    return dict(url=urldefrag(url)[0],title=title,text=body,published=date,discovered=now(),fingerprint=hashlib.sha256(body.encode()).hexdigest())

