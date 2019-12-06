''' scrape google timeline location xml for work start / end
'''
import os
import math
import urllib.parse
import sqlite3
import contextvars
import argparse
import contextlib
from datetime import date, timedelta, datetime, timezone
from win32.win32crypt import CryptUnprotectData
from requests import Request, Session
from bs4 import BeautifulSoup

TIMELINE_URL = 'https://www.google.com/maps/timeline/kml'
USE_CACHE = contextvars.ContextVar('USE_CACHE', default=False)

def valid_date(date_s: str):
    ''' parse date from args
    '''
    try:
        return datetime.strptime(date_s, '%m/%d/%y')
    except ValueError:
        pass
    try:
        return datetime.strptime(date_s, '%m/%d/%Y')
    except ValueError:
        msg = f'Not a valid date: "{date_s}""'
        raise argparse.ArgumentTypeError(msg)


def rewrite_daterange_string(from_date, to_date):
    ''' generate valid params for maps request
    '''
    return (
        f'1m8!1m3!1i{from_date.year}!2i{from_date.month - 1}!3i'
        f'{from_date.day}!2m3!1i{to_date.year}!2i{to_date.month - 1}'
        f'!3i{to_date.day}'
        )


def set_cookies(session: Session):
    ''' read cookies from chrome sqlite db
    '''
    cookie_path = os.path.join(
        os.environ['localappdata'],
        'Google\\Chrome\\User Data\\Default\\Cookies')
    with contextlib.closing(sqlite3.connect(cookie_path)) as con:
        cur = con.execute('''
            select name, encrypted_value from cookies
            where host_key like "%google.com"''')

        for name, encrypted_value in cur:
            value = CryptUnprotectData(encrypted_value, None, None, None, 0)[1]
            if name is bytes:
                name = name.decode()
            cookie = {
                "name": name,
                "value": value.decode()
                }
            session.cookies.set(**cookie)


SESSION = Session()
set_cookies(SESSION)
LOCALTZ = timezone(datetime.fromtimestamp(0) - datetime.utcfromtimestamp(0))
PARSER = argparse.ArgumentParser(description="scrape google timeline for work hours")
PARSER.add_argument(
        '--date',
        metavar='D',
        help="Date in week of requested timeline (MM/DD/YYYY)",
        required=False,
        type=valid_date)
PARSER.add_argument('--cache', help="Cache timeline responses", required=False, type=bool)


def make_request(params) -> str:
    ''' make an http request with params to timeline url
    '''
    cache = USE_CACHE.get()
    req = Request('GET', TIMELINE_URL, params=params)
    prepped = SESSION.prepare_request(req)
    if cache:
        url = urllib.parse.quote(prepped.url, '')
        path = os.path.join('cache', url)
        if os.path.exists(path):
            with open(path, 'r') as fobj:
                return fobj.read()

    res = SESSION.send(prepped)
    if (code := res.status_code) < 200 or code > 400:
        raise Exception(f'failed to fetch {url}')

    content = res.content.decode()
    if cache:
        with open(path, 'w') as fobj:
            fobj.write(content)
    return content


def parse_date_str(date_s):
    ''' parse date like 2019-11-26T01:35:36.088Z
    '''
    return datetime.fromisoformat(date_s.replace("Z", "+00:00"))


def round_to(num: float, frac=4):
    ''' round to quarters / halfs etc
    '''
    return (math.floor(num * frac) / frac, num)


def get_timeline(target_date):
    ''' get timeline for a day
    '''
    params = 'authuser=0&pb=' + rewrite_daterange_string(
        target_date,
        target_date + timedelta(days=1))
    content = make_request(params)
    soup = BeautifulSoup(content, 'lxml-xml')
    for x_placemark in soup.find_all('Placemark'):
        if x_placemark.find('Point'):
            name = x_placemark.find('name').string
            x_time_span = x_placemark.find('TimeSpan')
            start, end = [parse_date_str(x_time_span.find(s).string) for s in ('begin', 'end')]
            yield (name, start, end)


def get_timeline_for_week(target_date, sub=0.5):
    ''' print start, duration for each day in target week.
        remove break time over threshold
    '''
    start = target_date - timedelta(days=target_date.weekday())
    days = [start + timedelta(days=i) for i in range(0, 5)]

    print(' - '.join(d.strftime('%a, %m/%d/%y') for d in (days[0], days[-1])))
    print()
    cum = 0
    for each_date in days:
        print(each_date.strftime('%m/%d/%y'))
        timeline = get_timeline(each_date)
        tot = 0
        for name, start, end in timeline:
            if name.startswith('Work'):
                print(' - '.join(d.astimezone(LOCALTZ).strftime('%I:%M%p') for d in (start, end)))
                delta = (end - start) / timedelta(hours=1)
                rounded, exact = round_to(delta)
                tot += exact
                print(f'{rounded} ({exact:.2f})')
        if tot > 6:
            tot -= sub
        cum += tot
        rounded, exact = round_to(tot)
        print(f'total: {rounded} ({exact:.2f})')
        print()

    rounded, exact = round_to(cum)
    print(f'CUMULATIVE: {rounded} ({exact:.2f})')


if __name__ == '__main__':
    ARGS = PARSER.parse_args()
    USE_CACHE.set(ARGS.cache or False)
    TARGET_DATE = ARGS.date or (date.today() - timedelta(7))
    get_timeline_for_week(TARGET_DATE)
