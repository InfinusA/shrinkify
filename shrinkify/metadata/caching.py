import os
import sqlite3
import typing
import pathlib
from .. import config

class SimpleConnection(object):
    def __init__(self, table: str, cursor: sqlite3.Cursor, use_cache=True) -> None:
        self.table = table
        self.cursor = cursor
        self.cursor.row_factory = sqlite3.Row # type: ignore
        self.use_cache = use_cache
                
    def load_schema(self, schema: str):
        self.cursor.executescript(schema)
        self.cursor.connection.commit()
        
    def load_generic_schema(self, keyName: str, dataName: str):
        self.cursor.executescript(f"""
            CREATE TABLE IF NOT EXISTS {self.table} (
                {keyName} STRING PRIMARY KEY NOT NULL,
                {dataName} STRING NOT NULL
            );""")
        self.cursor.connection.commit()
        
            
    def insert(self, data: list[typing.Any] | dict[str, typing.Any], key: typing.Optional[str | tuple] = None) -> None:
        '''Will also update if already exists'''
        if isinstance(data, list):
            try:
                self.cursor.execute(f"INSERT INTO {self.table} VALUES ({', '.join('?' for _ in data)})", *data)
            except sqlite3.IntegrityError:
                raise RuntimeError("A dict is required for updating tables")
        elif isinstance(data, dict):
            ks = data.keys()
            try:
                self.cursor.execute(f"INSERT INTO {self.table} ({', '.join(k for k in ks)}) VALUES ({', '.join(f':{k}' for k in ks)})", data)
            except sqlite3.IntegrityError:
                if key is None:
                    raise RuntimeError("Tried to update table but key is not set")
                self.cursor.execute(f"UPDATE {self.table} SET {', '.join(f'{k} = :{k}' for k in ks)} WHERE {' AND '.join(f'{k} = :{k}' for k in key) if not isinstance(key, str) else f'{key} = :{key}'}", data)
        self.cursor.connection.commit()
    
    def contains(self, **kwargs) -> bool:
        #if cache use is disabled, return false no matter what
        if self.use_cache:
            return bool(self.fetch_one(**kwargs))
        else:
            return False 
        
    def fetch(self, **kwargs) -> sqlite3.Cursor:
        return self.cursor.execute(f"SELECT * FROM {self.table} WHERE {' AND '.join(f'{key} = :{key}' for key in kwargs.keys())}", kwargs)
    
    def fetch_multiple(self, **kwargs) -> list[sqlite3.Row]:
        return self.fetch(**kwargs).fetchall()
    
    def fetch_one(self, **kwargs) -> sqlite3.Row:
        return self.fetch(**kwargs).fetchone()

class CacheConnector(object):
    def __init__(self, conf: config.Config):
        self.conf = conf
        pathlib.Path(self.conf.general.cache_file).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.conf.general.cache_file)
    
    def get_cursor(self):
        return self.db.cursor()
    
    def create_simple(self, table: str) -> SimpleConnection:
        return SimpleConnection(table, self.get_cursor(), self.conf.general.use_cache)