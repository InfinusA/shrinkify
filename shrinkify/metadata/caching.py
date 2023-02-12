import os
import sqlite3
import typing
from .. import config

class SimpleConnection(object):
    def __init__(self, table: str, cursor: sqlite3.Cursor) -> None:
        self.table = table
        self.cursor = cursor
        self.cursor.row_factory = sqlite3.Row # type: ignore
                
    def load_schema(self, schema: str):
        self.cursor.executescript(schema)
        self.cursor.connection.commit()
            
    def insert(self, data: list[typing.Any] | dict[str, typing.Any]) -> None:
        if isinstance(data, list):
            self.cursor.execute(f"INSERT INTO {self.table} VALUES ({', '.join('?' for _ in data)})", *data)
        elif isinstance(data, dict):
            ks = data.keys()
            self.cursor.execute(f"INSERT INTO {self.table} ({', '.join(k for k in ks)}) VALUES ({', '.join(f':{k}' for k in ks)})", data)
        self.cursor.connection.commit()
    
    def contains(self, **kwargs) -> bool:
        return bool(self.fetch_one(**kwargs))
        
    def fetch(self, **kwargs) -> sqlite3.Cursor:
        return self.cursor.execute(f"SELECT * FROM {self.table} WHERE {' AND '.join(f'{key} = :{key}' for key in kwargs.keys())}", kwargs)
    
    def fetch_multiple(self, **kwargs) -> list[sqlite3.Row]:
        return self.fetch(**kwargs).fetchall()
    
    def fetch_one(self, **kwargs) -> sqlite3.Row:
        return self.fetch(**kwargs).fetchone()

class CacheConnector(object):
    def __init__(self, conf: config.Config):
        self.conf = conf
        self.db = sqlite3.connect(self.conf.general.cache_file)
    
    def get_cursor(self):
        return self.db.cursor()
    
    def create_simple(self, table: str) -> SimpleConnection:
        return SimpleConnection(table, self.get_cursor())