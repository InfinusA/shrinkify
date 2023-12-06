import logging
from .. import config
from .. import songclass
from .. import overrides
import pathlib
from . import file
from . import youtube
from . import caching
from . import youtubemusic
from . import niconico
from . import acoustid_mb
from abc import ABC, abstractmethod
#TODO: Make this not bad
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
        self.handlers: list[file.MetadataParser] = []
        self.handler_list = (
            file.FileMetadata(self.conf),
            youtube.YoutubeMetadata(self.conf, self.cache),
            niconico.NicoNicoMetadata(self.conf, self.cache),
            youtubemusic.YoutubeMusicMetadata(self.conf, self.cache),
            acoustid_mb.AcoustIDMetadata(self.conf, self.cache)
        )
        self.handlers = self.setup_handler_list(self.conf.metadata.identifiers)
    
    def setup_handler_list(self, handlers: list[str] | tuple[str, ...]) -> list[file.MetadataParser]:
        l = []
        for identifier in handlers:
            for handler in self.handler_list:
                if handler.identifier == identifier:
                    l.append(handler)
        return l

    
    def parse(self, song: songclass.Song) -> songclass.Song:
        localhandlers = self.setup_handler_list(overrides.Overrides(self.conf).override('metadata_handlers', song=song, parsers=self.conf.metadata.identifiers)['parsers'])
        for handler in localhandlers:
            if handler.check_valid(song):
                res = handler.fetch(song)
                if res in (None, False):
                    if res is False:
                        logging.warning("Returning `None` from a handler is now preferred to returning `False`.\nThis can be safely ignored by users")
                    continue
                song = res
                break
        #test
        song = overrides.Overrides(self.conf).override('final_metadata', song=song)['song']
        song = overrides.Overrides(self.conf).basic_override(song)
        return song