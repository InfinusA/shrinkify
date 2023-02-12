import pathlib
import json
import re
import requests
from .. import config

class YoutubeMetadata(object):
    def __init__(self, conf: config.Config) -> None:
        self.conf = conf

    def check_valid(self, file: pathlib.Path):
        if not self.conf.metadata.youtube.api_key:
            return False
        for regex in self.conf.metadata.youtube.filename_regex:
            if re.search(regex, file.name):
                return True
        return False
    
    def fetch(self, file: pathlib.Path):
        pass
        