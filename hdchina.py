# encoding: utf8
import sys
import re
import datetime
import itertools
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
    tds = tr.findAll('td')
    obj['category'] = tds[0].a.img['alt']
    if tr.find(text=u'置顶'):
        obj['sticky'] = True
    else:
        obj['sticky'] = False
    obj['title'] = tds[1].find('b').findAll(text=True)[-1]
    if obj['title'].startswith(u'：'):
        obj['title'] = obj['title'][1:]
    try:
        obj['promote'] = re_promote.search(tds[1].find('a').find('img')['src']).group(1)
    except:
        obj['promote'] = None
    obj['id'] = int(re_id.search(tds[1].find('a')['href']).group(1))
    obj['nfiles'] = int(tds[2].text)
    obj['ncomments'] = int(tds[3].text)
    obj['addtime'] = tds[4].text
    obj['size'] = tds[6].text
    obj['ncomplete'] = int(tds[7].text[:-1])
    obj['nupload'], obj['ndownload'] = [int(x.text) for x in tds[8:10]]
    obj['username'] = tds[10].text
    try:
        obj['userid'] = int(re_id.search(tds[10].find('a')['href']).group(1))
    except:
        obj['userid'] = None
    return obj

def parse_page(res):
    now = datetime.datetime.utcnow()
    # for debug
    with open('hdchina.html','wb') as f:
        f.write(res.get_data())
    soup = BeautifulSoup(res.get_data())

    pagecnt = int(re.search(r'page=(\d+)', list(itertools.takewhile(lambda x: x['href'].startswith('browse.php?page='), soup.find(text=u'1&nbsp;-&nbsp;100').findAllNext('a')))[-1]['href']).group(1))

    table = soup.find('table',{'width':'90%'})
    trs = table.findAll('tr',recursive=False)

    for tr in trs[1:]:
        try:
            obj = parse_tr(tr)
            obj['date'] = now
            yield obj
        except:
            print 'error parsing', tr

if __name__ == '__main__':
    cookies = mechanize.LWPCookieJar(filename='cookie.txt')
    br = mechanize.Browser()
    br.set_handle_robots(False)
    br.set_cookiejar(cookies)

    mongo_conn = Connection()
    mongo_db = mongo_conn.ptmonitor
    mongo_col = mongo_db.hdchina

    try:
        cookies.load()
    except:
        login(br, cookies)

    cnt = 0
    for i in range(6):
        if i == 0:
            res = br.open('https://hdchina.org/browse.php')
            pagecnt = None
        elif i == 5:
            page = random.randint(5, pagecnt)
            res = br.open('https://hdchina.org/browse.php?page=%d' % page)
        else:
            res = br.follow_link(text=u'下页\xa0>>'.encode('utf8'))
        if not br.geturl().startswith('https://hdchina.org/browse.php'):
            print 'wrong torrent page, maybe corupted cookie', br.geturl()
            sys.exit(1)
        for obj in parse_page(res):
            mongo_col.insert(obj)
            cnt += 1
    print "Successful: ", cnt, "objects stored"
