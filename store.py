import os.path
import sqlite3

class Store:
    def __init__(self, dbpath):
        self.dbpath = dbpath
        if not os.path.exists(dbpath):
            self.create_db(dbpath)
        else:
            self.conn = sqlite3.connect(dbpath)
            self.cur = self.conn.cursor()

    def create_db(self, dbpath):
        self.conn = sqlite3.connect(dbpath)
        self.cur = self.conn.cursor()
        self.cur.execute("CREATE TABLE v(tid INTEGER, time TIMESTAMP, field text, value text)")

    def close(self):
        self.conn.commit()
        self.cur.close()
        self.conn.close()

