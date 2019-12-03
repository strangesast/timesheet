import os
import urllib.parse
import sqlite3
import contextlib
from datetime import date, timedelta, datetime, timezone
from win32.win32crypt import CryptUnprotectData
from requests import get, Request, Session
from bs4 import BeautifulSoup


def rewrite_daterange_string(a, b):
    ''' query parameter format for date range. only a single day works
    '''
    return f'1m8!1m3!1i{a.year}!2i{a.month - 1}!3i{a.day}!2m3!1i{a.year}!2i{a.month - 1}!3i{a.day}'

def get_cookies():
    ''' extract cookies for timeline from chrome.  (TODO: fix platform dependency)
    '''
    cookiePath = os.path.join(os.environ['localappdata'], 'Google\\Chrome\\User Data\\Default\\Cookies')
    cookies = {}
    with contextlib.closing(sqlite3.connect(cookiePath)) as con:
        cur = con.execute('''select name, encrypted_value from cookies
                             where host_key like "%google.com"''')
        
        for key, encrypted_value in cur:
            _, value = CryptUnprotectData(encrypted_value, None, None, None, 0)
            cookies[key] = value.decode()

    return cookies


session = Session()
cookies = get_cookies()
localtz = timezone(datetime.fromtimestamp(0) - datetime.utcfromtimestamp(0))

def check_cache(req):
    ''' check if request with same url / query parameters was made before
        if not, make it.  save response content.  return response content
    '''
    prepped = session.prepare_request(req)
    url = urllib.parse.quote(prepped.url, '') # remove slashes etc
    if os.path.exists(path := os.path.join('cache', url)): # cache directory must be present
        with open(path, 'r') as f:
            return f.read()
    res = session.send(prepped)
    content = res.content.decode()
    if (code := res.status_code) >= 200 and code < 400:
        with open(path, 'w') as f:
            f.write(content)
    else:
        raise Exception(f'failed to fetch {url}')
    return content


def round_to(f, frac=4):
    ''' round float to quarters / halves
    '''
    return int(f * frac) / frac


def parse_datetime(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")) 

def get_timeline_for_day(date, filter=lambda s: s.startswith('Work')):
    ''' request timeline kml for date, return Points matching filter
    '''
    a = date
    b = date + timedelta(days=1)
    
    params = 'authuser=0&pb=' + rewrite_daterange_string(a, b)
    req = Request('GET', 'https://www.google.com/maps/timeline/kml', cookies=cookies, params=params)
    content = check_cache(req)
    
    soup = BeautifulSoup(content, 'xml')
    for pm in soup.find_all('Placemark'):
        if (point := pm.find('Point')):
            name = pm.find('name').string
            if filter(name):
                ts = pm.find('TimeSpan')
                start, end = [parse_datetime(ts.find(k).string) for k in ('begin', 'end')]
                yield (start, end)
       

def get_timeline_for_week(date):
    ''' print hours for each day in week of date
    '''
    start = date - timedelta(days=date.weekday())
    days = [start + timedelta(days=i) for i in range(0, 5)]

    print(' - '.join(d.strftime('%a, %m/%d/%y') for d in (days[0], days[-1])))
    print()
    for date in days:
        print(date.strftime('%m/%d/%y'))
        groups = list(get_timeline_for_day(date))
        tot = 0
        for start, end in groups:
            s = ' - '.join(d.astimezone(localtz).strftime('%I:%M%p') for d in (start, end))
            print(s)
            f = (end - start) / timedelta(hours=1)
            g = round_to(f)
            print(f'{g} ({f:.2f})')
            tot += f

        if (l := len(groups)) == 0:
            print(None)
        elif l > 1:
            print(f'total: {round_to(tot)}')
        print()


if __name__ == '__main__':
    now = date.today() - timedelta(7)
    get_timeline_for_week(now)
