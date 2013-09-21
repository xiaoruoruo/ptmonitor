# encoding: utf8
import sys
import re
import datetime
import ConfigParser

import mechanize
from BeautifulSoup import BeautifulSoup

def login(br, cookies):
    config = ConfigParser.RawConfigParser()
    config.read('config')
    username = config.get('pt','username')
    password = config.get('pt','password')

    res = br.open('http://pt.sjtu.edu.cn')
    print br.geturl()
    soup = BeautifulSoup(res.get_data())

    br.select_form(nr=0)
    br['username'] = username
    br['password'] = password
    res2 = br.submit()
    #print br.geturl()
    #soup = BeautifulSoup(res2.get_data())
    #print soup.prettify()

    cookies.save()
    return res2

re_id = re.compile(r'id=(\d+)')
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
    obj['id'] = int(re_id.search(tds[1].find('tr').find('a',{'href':True})['href']).group(1))
    obj['ncomments'] = int(tds[5].text)
    obj['uptime'] = tds[6].text
    obj['size'] = tds[7].text
    obj['nupload'], obj['ndownload'], obj['ncomplete'] = [int(x.text.replace(',','')) for x in tds[8:11]]
    obj['username'] = tds[11].text
    try:
        obj['userid'] = int(re_id.search(tds[11].find('a')['href']).group(1))
    except:
        obj['userid'] = None
    return obj

def parse_page(data):
    now = datetime.datetime.utcnow()
    # for debug
    with open('debug.html','wb') as f:
        f.write(data)
    soup = BeautifulSoup(data)
    table = soup.find('table', {'class':'torrents'})
    trs = table.findAll('tr',recursive=False)

    for tr in trs[1:]:
        try:
            obj = parse_tr(tr)
            obj['date'] = now
            yield obj
        except:
            print 'error parsing', tr

class MongoStore:
    def __init__(self):
        from pymongo import Connection
        print 'Using MongoStore'
        self.mongo_conn = Connection()
        self.mongo_db = self.mongo_conn.ptmonitor
        self.mongo_col = self.mongo_db.pt

    def insert(self, obj):
        self.mongo_col.insert(obj)

    def close(self):
        self.mongo_conn.close()

class FileStore:
    def __init__(self, filename):
        print 'Using FileStore:', filename
        self.output = open(filename, 'a')

    def insert(self, obj):
        import json
        from bson import json_util
        json.dump(obj, self.output, default=json_util.default)
        self.output.write('\n')

    def close(self):
        self.output.close()

if __name__ == '__main__':
    if 'test' in sys.argv:
        import json
        from bson import json_util
        print sys.argv
        with open(sys.argv[2], 'rb') as testfile:
            for obj in parse_page(testfile.read()):
                print json.dumps(obj, indent=4, separators=(',', ': '), default=json_util.default)
        sys.exit(0)

    import socket
    socket.setdefaulttimeout(60000) # in Milliseconds

    cookies = mechanize.LWPCookieJar(filename='cookie.txt')
    br = mechanize.Browser()
    br.set_handle_robots(False)
    br.set_cookiejar(cookies)

    if 'login' in sys.argv:
        login(br, cookies)
        sys.exit(0)
    else:
        cookies.load()

    if 'mongo' in sys.argv:
        store = MongoStore()
    elif 'file' in sys.argv:
        store = FileStore(sys.argv[2])
    else:
        raise Exception('Need a store type')

    cnt = 0
    for i in range(6):
        if i == 0:
            res = br.open('https://pt.sjtu.edu.cn/torrents.php')
        elif i == 5:
            res = br.follow_link(text=u'随便看看'.encode('utf8'))
        else:
            res = br.follow_link(text=u'下一页\xa0>>'.encode('utf8'))
        if not br.geturl().startswith('https://pt.sjtu.edu.cn/torrents.php'):
            print 'wrong torrent page, maybe corupted cookie', br.geturl()
            sys.exit(1)
        print 'parsing', br.geturl()
        for obj in parse_page(res.get_data()):
            store.insert(obj)
            cnt += 1
    print "Successful: ", cnt, "objects stored"
