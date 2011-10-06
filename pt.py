import sys
import os
import re
import datetime

import mechanize
from BeautifulSoup import BeautifulSoup
from pymongo import Connection

cookies = mechanize.LWPCookieJar(filename='cookie.txt')
br = mechanize.Browser()
br.set_handle_robots(False)
br.set_cookiejar(cookies)
re_id = re.compile(r'id=(\d+)')

mongo_conn = Connection()
mongo_db = mongo_conn.ptmonitor
mongo_col = mongo_db.pt

def login():
    res = br.open('http://pt.sjtu.edu.cn')
    print br.geturl()
    soup = BeautifulSoup(res.get_data())
    img_src = None
    for img in soup.findAll('img'):
        if img['src'].startswith('getcheckcode'):
            img_src = img['src']
    if not img_src:
        sys.exit(1)
    print img_src
    image_response = br.open_novisit(img_src)
    image = image_response.read()
    with open('checkcode.png','wb') as f:
        f.write(image)

    print 'Enter checkcode: ',
    code = sys.stdin.readline()

    print 'entered',code

    br.select_form(nr=0)
    br['username'] = os.environ['USERNAME']
    br['password'] = os.environ['PASSWORD']
    br['checkcode'] = code
    res2 = br.submit()
#    print br.geturl()
#    soup = BeautifulSoup(res2.get_data())
#    print soup.prettify()

    cookies.save()

try:
    cookies.load()
except:
    login()

res = br.open('https://pt.sjtu.edu.cn/torrents.php')
if br.geturl() != 'https://pt.sjtu.edu.cn/torrents.php':
    print 'wrong torrent page, maybe corupted cookie', br.geturl()
    sys.exit(1)
# for debug
with open('torrents.html','wb') as f:
    f.write(res.get_data())
soup = BeautifulSoup(res.get_data())
table = soup.find('table', {'class':'torrents'})
trs = table.findAll('tr',recursive=False)

def parse_tr(tr):
    obj = {}
    try:
        obj['promote'] = tr['class']
    except:
        obj['promote'] = None
    tds = tr.findAll('td')
    obj['category'] = tds[0].find('a')['title']
    if tds[1].find('img',{'alt':'Sticky'}):
        obj['sticky'] = True
    else:
        obj['sticky'] = False
    obj['title'] = tds[1].find('tr').find('a').text
    obj['id'] = int(re_id.search(tds[1].find('tr').find('a')['href']).group(1))
    obj['ncomments'] = int(tds[4].text)
    obj['uptime'] = tds[5].text
    obj['size'] = tds[6].text
    obj['nupload'], obj['ndownload'], obj['ncomplete'] = [int(x.text) for x in tds[7:10]]
    obj['username'] = tds[10].text
    try:
        obj['userid'] = int(re_id.search(tds[10].find('a')['href']).group(1))
    except:
        obj['userid'] = None
    return obj

for tr in trs[1:]:
    try:
        obj = parse_tr(tr)
        obj['date'] = datetime.datetime.utcnow()
    except:
        print 'error parsing', tr
    mongo_col.insert(obj)

