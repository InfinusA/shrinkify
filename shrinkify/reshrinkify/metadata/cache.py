import os
import sqlite3
from . import config

cache_db: sqlite3.Connection | None = None

def connect(connection: str | os.PathLike):
    cache_db = sqlite3.connect(connection)