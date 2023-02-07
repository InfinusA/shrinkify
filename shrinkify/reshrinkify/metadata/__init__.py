from .. import config
import pathlib
from abc import ABC, abstractmethod

class MetadataHandler(ABC):
    @abstractmethod
    def check_valid(self, file: pathlib.Path) -> bool:
        pass
    
    @abstractmethod
    def parse(self, file: pathlib.Path) -> dict:
        pass

class MetadataParser(object):
    def __init__(self, conf: config.General) -> None:
        self.conf = conf
        self.registered_handlers = []
    
    def register_defaults(self):
        self.registered_handlers.append()
    
    def parse(self, file: pathlib.Path):
        pass