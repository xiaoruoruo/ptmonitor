# encoding: utf8
import sys
import re
import datetime
import itertools
import random
import ConfigParser

import mechanize
from BeautifulSoup import BeautifulSoup
from pymongo import Connection

def login(br, cookies):
    config = ConfigParser.RawConfigParser()
    config.read('config')
    username = config.get('hdchina','username')
    password = config.get('hdchina','password')

    res = br.open('http://hdchina.org/login.php')
    print br.geturl()
    soup = BeautifulSoup(res.get_data())

    br.select_form(nr=0)
    br['username'] = username
    br['password'] = password
    res2 = br.submit()
#    print br.geturl()
#    soup = BeautifulSoup(res2.get_data())
#    print soup.prettify()

    cookies.save()
    return res2

re_id = re.compile(r'id=(\d+)')
re_promote = re.compile(r'/pic/ico_(\w+)\.gif')
def parse_tr(tr):
    obj = {}
    tds = tr.findAll('td', recursive=False)
    obj['category'] = tds[0].find('img')['alt']
    if tr.find('img', {'src':'images/pin.png'}):
        obj['sticky'] = True
    else:
        obj['sticky'] = False
    try:
        obj['title'] = tds[1].find('b').text.replace('&nbsp;','')
    except:
        obj['title'] = tds[1].text.replace('&nbsp;','')
    if obj['title'].startswith(u'：'):
        obj['title'] = obj['title'][1:]
    try:
        obj['promote'] = tr['style']=='background:#CCF;'
    except:
        obj['promote'] = None
    obj['id'] = int(re_id.search(tds[1].find('a')['href']).group(1))
    obj['ncomments'] = int(tds[2].text)
    obj['nfiles'] = int(tds[3].text)
    s = tds[4].text
    s = s[:s.find('TTL')]
    obj['addtime'] = s
    obj['size'] = tds[5].text
    obj['ncomplete'] = int(tds[6].text[:-1].replace(',',''))
    obj['nupload'], obj['ndownload'] = [int(x.text.replace(',','')) for x in tds[7:9]]
    obj['username'] = tds[9].text
    try:
        obj['userid'] = int(re_id.search(tds[9].find('a')['href']).group(1))
    except:
        obj['userid'] = None
    return obj

pagecnt = None
re_pagenum = re.compile(r'page=(\d+)')
def parse_page(page):
    now = datetime.datetime.utcnow()
    # for debug
    with open('hdchina.html','wb') as f:
        f.write(page)
    soup = BeautifulSoup(page)

    global pagecnt
    pagecnt = max(int(re_pagenum.search(x['href']).group(1)) for x in soup.find(text=u'1&nbsp;-&nbsp;100').findAllNext('a') if x['href'].startswith('browse.php?page='))

    table = soup.find('table',{'class':'torrents_list'})
    trs = table.findAll('tr',recursive=False)

    for tr in trs[1:]:
        try:
            obj = parse_tr(tr)
            obj['date'] = now
            yield obj
        except:
            print 'error parsing', tr
            raise

if __name__ == '__main__':
    cookies = mechanize.LWPCookieJar(filename='cookie.txt')
    br = mechanize.Browser()
    br.set_handle_robots(False)
    br.set_cookiejar(cookies)

    mongo_conn = Connection()
    mongo_db = mongo_conn.ptmonitor
    mongo_col = mongo_db.hdchina

    cookies.load()
    if 'login' in sys.argv:
        login(br, cookies)
        sys.exit(0)

    cnt = 0
    for i in range(6):
        if i == 0:
            res = br.open('https://hdchina.org/browse.php')
        elif i == 5:
            page = random.randint(5, pagecnt)
            res = br.open('https://hdchina.org/browse.php?page=%d' % page)
        else:
            res = br.follow_link(text=u'下页\xa0>>'.encode('utf8'))
        if not br.geturl().startswith('https://hdchina.org/browse.php'):
            print 'wrong torrent page, maybe corupted cookie', br.geturl()
            sys.exit(1)
        for obj in parse_page(res.get_data()):
            mongo_col.insert(obj)
            cnt += 1
    print "Successful: ", cnt, "objects stored"
