import pathlib
#from . import MetadataHandler
import re
from .. import config

class YoutubeMusicMetadata(object):#MetadataHandler):
    def __init__(self, conf: config.Config) -> None:
        self.conf = conf
    
    def check_valid(self, file: pathlib.Path) -> bool:
        for regex in self.conf.metadata.youtubemusic.filename_regex:
            if re.search(regex, file.name):
                return True
        return False
