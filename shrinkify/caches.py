import sqlite3 
import os

class CacheDatabase(object):
    '''
    THIS IS NOT SECURE, CLIENTS CAN ACCESS ANY TABLE IN THE DATABASE
    '''
    def __init__(self, db_file: os.PathLike | str) -> None:
        self.db = sqlite3.connect(db_file)
    
    def initialize(self, category: str, schema: tuple[str]):
        cursor = self.db.cursor()
        cursor.execute(f"CREATE TABLE IF NOT EXISTS {category}, ({' ,'.join(schema)})")
    
    def fetch(self, category: str, id: str):
        cursor = self.db.cursor()
        cursor.fetchone(f"SELECT * FROM {category} WHERE id=?", (id,))

