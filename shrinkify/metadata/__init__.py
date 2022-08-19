#!/usr/bin/env python3
from functools import cache
import pathlib
from ..config import ShrinkifyConfig
from . import youtube_music_metadata
from . import youtube_metadata
from . import file_metadata
from . import shrink_utils

class AutoFail(object):
    '''automatically fail metadata check. Used to disable modules'''
    def fetch(*args, **kwargs):
        return False

class MetadataProcessor(object):
    def __init__(self):
        # default_parser_args = {'ytm': {}, 'yt': {'youtube_api_key': None}, 'file': {'thumbnail_generator_args': {'font': '3ds Light', 'base_image': '/media/ext1/music/not-music/no-image.png'}}}
        # default_parser_args.update(parser_arguments)
        # self.enabled_parsers = enabled_parsers
        self.ytm_parser = youtube_music_metadata.YoutubeMusicMetadata() if ShrinkifyConfig.MetadataRuntime.YoutubeMusicMetadata.enabled else AutoFail()
        self.yt_parser = youtube_metadata.YoutubeMetadata() if ShrinkifyConfig.MetadataRuntime.YoutubeMetadata.enabled else AutoFail()
        self.fm_parser = file_metadata.FileMetadata()
        self.ytm_comments = ShrinkifyConfig.MetadataRuntime.YoutubeMetadata.enabled and ShrinkifyConfig.MetadataRuntime.youtube_comments
        
        #create cache directory if one is specified
        if isinstance(ShrinkifyConfig.cache, pathlib.Path):
            ShrinkifyConfig.cache.mkdir(parents=True, exist_ok=True)
        
    def parse(self, file, no_cache=False):
        file_yt = shrink_utils.match_yt_id(file.name)
        file_metadata = False
        if file_yt:
            music_res = self.ytm_parser.fetch(file_yt, no_cache=no_cache)
            if not music_res:
                file_metadata = self.yt_parser.fetch(file_yt, no_cache=no_cache)
                if file_metadata:
                    print('Using YouTube parser')
            elif self.ytm_comments:
                file_metadata = music_res
                file_metadata['comment'] = self.yt_parser.fetch(file_yt, no_thumb=True, no_cache=no_cache)['comment']
                print('Using YT Music parser with YouTube comments')
            else:
                file_metadata = music_res
                print('Using YT Music parser')
                
        
        if not file_metadata: #nothing's worked so far, so fallback to default file parser
            file_metadata = self.fm_parser.fetch(file) #Note that files have no cache, as the extra cpu time isn't worth the storage space
            print('Using file parser')
            
        return file_metadata    
        

# if __name__ == '__main__':
#     ytm = youtube_music_metadata.YoutubeMusicMetadata('/media/ext1/music/cache/')
#     ytm.fetch('--41OGPMurU')
#     fm = file_metadata.FileMetadata('/media/ext1/music/cache/')
#     fm.fetch('/media/ext1/music/vocaloid/KIRA - Digital Girl ft. Hatsune Miku (Original Song)-_fC4gB841VI.mkv')