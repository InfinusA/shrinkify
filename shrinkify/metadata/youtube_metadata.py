#!/usr/bin/env python3
#fetch metadata for youtube-related services
import pathlib
import json
import re
import requests

from .shrink_utils import data_to_thumbnail
from ..config import ShrinkifyConfig

def match_yt_id(filename):
    yt_match = re.search('(?<=\-)[a-zA-Z0-9\-_]{11}(?=\.|$)', str(filename))
    if not yt_match:
        return yt_match
    else:
        yt_id = yt_match.group(0)
        return yt_id

class YoutubeMetadata(object):
    def __init__(self) -> None:
        self.ytc = self.YoutubeCache(ShrinkifyConfig.MetadataRuntime.YoutubeMetadata.api_key, ShrinkifyConfig.cache)

    def fetch(self, video_id, no_meta=False, no_thumb=False, no_cache=False):
        self.ytc.set_cache_state(not no_cache)
            
        if no_meta == True and no_thumb == True:
            raise RuntimeWarning("Should not set both meta_only and thumb_only to True. This just returns nothing and is a waste of time and resources")
        video_data = self.ytc.get_video_data(video_id)
        try:
            snippet = video_data['items'][0]['snippet']
        except IndexError:
            return False #usually because video is now unavailable
        except KeyError as e: #usually invalid api key
            print(video_data)
            raise e
        shrinkify_metadata = {}
        if not no_meta:
           shrinkify_metadata['title'] = snippet['title']
           shrinkify_metadata['album'] = snippet['title']
           shrinkify_metadata['artist'] = snippet['channelTitle']
           shrinkify_metadata['year'] = snippet['publishedAt'][:4]
           shrinkify_metadata['date'] = snippet['publishedAt'][:4]
           shrinkify_metadata['comment'] = snippet['description']
        if not no_thumb:
            if ShrinkifyConfig.cache:
                cache_file = pathlib.Path(ShrinkifyConfig.cache, f'{video_id}.png')
                if cache_file.is_file():
                    raw_thumbnail = cache_file.read_bytes()
                else:
                    raw_thumbnail = requests.get(max(snippet['thumbnails'].values(), key=lambda x: x['height']+x['width'])['url']).content
                    cache_file.write_bytes(raw_thumbnail)
            else:
                raw_thumbnail = requests.get(max(snippet['thumbnails'].values(), key=lambda x: x['height']+x['width'])['url']).content

            shrinkify_metadata['_thumbnail_image'] = data_to_thumbnail(raw_thumbnail)
            
        return shrinkify_metadata
        
    class YoutubeCache(object):
        '''get youtube data and automatically use/update cache'''
        def __init__(self, api_key, cachedir):
            self.api_key = api_key
            self.cache_file = pathlib.Path(cachedir, 'youtube_cache.json')
            self.cache_state = True if self.cache_file else False
            
        def set_cache_state(self, state: bool):
            self.cache_state = state
        
        def set_cache_init(self):
            '''
            set cache state to the initial state
            '''
            self.cache_state = True if self.cache_file else False
            
        def get_video_data(self, video_id):
            if self.cache_file is None:
                print(f"https://youtube.googleapis.com/youtube/v3/videos?part=snippet%2CcontentDetails%2Cstatistics&id={video_id}&key={self.api_key}")
                video_resp = requests.get(f"https://youtube.googleapis.com/youtube/v3/videos?part=snippet%2CcontentDetails%2Cstatistics&id={video_id}&key={self.api_key}", headers={'Accept': 'application/json'})
                return json.loads(video_resp.content)
            
            cache_exists = self.cache_file.is_file()
            if cache_exists and self.cache_state:
                json_cache = json.loads(self.cache_file.read_text())
                if video_id in json_cache:
                    return json_cache[video_id]
            video_resp = requests.get(f"https://youtube.googleapis.com/youtube/v3/videos?part=snippet%2CcontentDetails%2Cstatistics&id={video_id}&key={self.api_key}", headers={'Accept': 'application/json'})
            video_data = json.loads(video_resp.content)
            if 'error' in video_data: #don't save this to cache because it screws up everything else
                return video_data
            
            elif cache_exists:
                jc = json.loads(self.cache_file.read_text())
                jc[video_id] = video_data
                with self.cache_file.open('w') as cache:
                    cache.write(json.dumps(jc))
            else:
                self.cache_file.parent.mkdir(parents=True, exist_ok=True)
                with self.cache_file.open('w+') as cache:
                    cache.write(json.dumps({video_id: video_data}))
            return video_data