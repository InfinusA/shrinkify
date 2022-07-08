#!/usr/bin/env python3
from ..config import ShrinkifyConfig
from .shrink_utils import data_to_thumbnail
class NicoMetadata(object):
    def __init__(self):
        pass
    
    def fetch(self, video_id, no_meta=False, no_thumb=False, no_cache=False):
        return False #curl won't respond to me 