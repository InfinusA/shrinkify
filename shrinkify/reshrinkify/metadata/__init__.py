from .. import config
import pathlib
from . import file
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
        self.registered_handlers = []
        self.test_file = file.FileMetadata(self.conf)
    
    def register_defaults(self):
        #self.registered_handlers.append()
        pass
    
    def parse(self, file: pathlib.Path):
        return self.test_file.fetch(file)