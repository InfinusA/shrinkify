from .. import config
import pathlib
from . import file
from . import youtube
from . import caching
from . import youtubemusic
from abc import ABC, abstractmethod

class MetadataHandler(ABC):
    @abstractmethod
    def check_valid(self, file: pathlib.Path) -> bool:
        pass
    
    @abstractmethod
    def fetch(self, file: pathlib.Path) -> dict:
        pass

class MetadataParser(object):
    def __init__(self, conf: config.Config) -> None:
        self.conf = conf
        self.cache = caching.CacheConnector(self.conf)
        self.registered_handlers = []
        self.test_file = file.FileMetadata(self.conf)
        self.test_youtube = youtube.YoutubeMetadata(self.conf, self.cache)
    
    def register_defaults(self):
        #self.registered_handlers.append()
        pass
    
    def parse(self, file: pathlib.Path):
        out = None
        if self.test_youtube.check_valid(file):
            out = self.test_youtube.fetch(file)
        if not out:
            out = self.test_file.fetch(file)
        return out