#!/usr/bin/env python3
import ytmusicapi
import json
import pathlib
import requests
import logging

from .shrink_utils import data_to_thumbnail
from ..config import ShrinkifyConfig

import sys

class YoutubeMusicMetadata(object):
    '''Find metadata for a youtube music video on youtube music. 
    Note that this does not do fuzzy text matching, but finds the exact corresponding metadata'''
    def __init__(self):
        self.ytm = self.CacheYTMusic(shrinkify_cache=ShrinkifyConfig.cache, override=ShrinkifyConfig.MetadataRuntime.YoutubeMusicMetadata.override_enabled)
    def fetch(self, source_id, no_meta=False, no_thumb=False, no_cache=False):
        """
        source_id: a youtube video id
        no_meta: don't get metadata, only the thumbnail
        no_thumb: don't get thumbnail, only metadata
          note: no_meta and no_thumb should generally not both be true
        no_cache: temporarily disable cache. Useful to update the cache for a specific file
        """
        
        #load override
        original_id = source_id
        if [o for o in ShrinkifyConfig.MetadataRuntime.YoutubeMusicMetadata.override_song if source_id  == o[0]]:
            original_id = source_id
            source_id = [o for o in ShrinkifyConfig.MetadataRuntime.YoutubeMusicMetadata.override_song if source_id in o][0][1]
        # if ShrinkifyConfig.cache and ShrinkifyConfig.MetadataRuntime.YoutubeMusicMetadata.override_enabled:
        #     override_file = pathlib.Path(ShrinkifyConfig.cache, 'ytmusic_overrides.json')
        #     with override_file.open('r') as of:
        #         override = json.loads(of.read())
        #         if source_id in override['song']:
        #             source_id = override['song'][source_id]
        
        self.ytm.set_cache_state(not no_cache)
        
        if no_meta == True and no_thumb == True:
            raise RuntimeWarning("Should not set both meta_only and thumb_only to True. This just returns nothing and is a waste of time and resources")
        '''Given a song id, return either metadata or false if the id is invalid'''
        song_info = self.ytm.get_song(source_id)
        if song_info['playabilityStatus']['status'] in ('UNPLAYABLE', 'ERROR'):
            return False
        
        if [o for o in ShrinkifyConfig.MetadataRuntime.YoutubeMusicMetadata.override_artist if song_info['videoDetails']['channelId']  == o[0]]:
            artist_id = [o for o in ShrinkifyConfig.MetadataRuntime.YoutubeMusicMetadata.override_artist if song_info['videoDetails']['channelId'] in o][0][1]
        else:
            artist_id = song_info['videoDetails']['channelId']
        try:
            artist_info = self.ytm.get_artist(artist_id)
        except (KeyError, ValueError):
            logging.warning("Artist not found, trying different parser")
            return False
        except Exception as e: #artist may be deleted?
            logging.warning(type(e).__name__+str(e)+"\ntrying another parser")
            return False
        
        songfound = False
        target_song = target_album = None
        if 'albums' in artist_info: #most valid artists should have albums
            logging.info(f"{source_id}: Searching albums")
            #long line but basically
            #if params exists, it is a key used to get all the artist's albums, so use it to fetch the artist's albums
            #if not, all are already available and we just use the available ones
            albums = self.ytm.get_artist_albums(artist_id, self.ytm.get_params(artist_id)) \
                if 'params' in artist_info['albums'] else artist_info['albums']['results']
            for album in albums:
                album_songs = self.ytm.get_album(album['browseId'])
                for song in album_songs['tracks']:
                    if song['videoId'] in (source_id, original_id) or (ShrinkifyConfig.MetadataRuntime.YoutubeMusicMetadata.name_match and song_info['videoDetails']['title'] == song['title']): #some songs are strange and the url links to the original, not the yt music ver
                        logging.info(f"{source_id}: Found song in album")
                        songfound = True
                        target_song = song
                        target_album = album
                        break

                #2nd break
                if songfound:
                    break
        
        if not songfound and 'singles' in artist_info:
            logging.info(f"{source_id}: Searching singles")
            if self.ytm.get_params(artist_id, True):
                songs = self.ytm.get_artist_albums(artist_id, self.ytm.get_params(artist_id, True))
            else:
                songs = artist_info['singles']['results']
            for song in songs:
                song_data = self.ytm.get_album(song['browseId'])
                for track in song_data['tracks']: #acts similarly to an album
                    if track['videoId'] in (source_id, original_id) or (ShrinkifyConfig.MetadataRuntime.YoutubeMusicMetadata.name_match and song_info['videoDetails']['title'] == track['title']): #some songs are strange and the url links to the original, not the yt music ver
                        logging.info(f"{source_id}: Found single")
                        songfound = True
                        target_song = track
                        target_album = song
                        break
                    
                if songfound:
                    break
                    
        if not songfound: #no song found at all
            logging.info(f"{source_id}: No song found")
            return False
        
        shrinkify_metadata = {}
        if not no_meta:
           shrinkify_metadata['title'] = target_song['title']
           shrinkify_metadata['artist'] = artist_info['name']
           shrinkify_metadata['album'] = target_album['title'] if target_album is not None else None
           shrinkify_metadata['year'] = target_album['year']
           shrinkify_metadata['date'] = target_album['year']
        if not no_thumb:
            if ShrinkifyConfig.cache:
                cache_file = pathlib.Path(ShrinkifyConfig.cache, f'{source_id}.png')
                if cache_file.is_file() and not no_cache:
                    raw_thumbnail = cache_file.read_bytes()
                else:
                    raw_thumbnail = requests.get(max(target_album['thumbnails'], key=lambda x: x['height']+x['width'])['url']).content
                    cache_file.write_bytes(raw_thumbnail)
            else:
                raw_thumbnail = requests.get(max(target_album['thumbnails'], key=lambda x: x['height']+x['width'])['url']).content

            shrinkify_metadata['_thumbnail_image'] = data_to_thumbnail(raw_thumbnail)
        
        return shrinkify_metadata


    class CacheYTMusic(ytmusicapi.YTMusic):
        '''
        wrapper for YTMusic that automatically handles caching and overrides
        '''
        def __init__(self, *args, shrinkify_cache=None, override=True, **kwargs):
            self.shrinkify_cache = pathlib.Path(shrinkify_cache) if shrinkify_cache is not None else None
            #prepare overrides
            # self.override_file = pathlib.Path(self.shrinkify_cache, 'ytmusic_overrides.json') if self.shrinkify_cache is not None else None
            # self.override = override
            self.cache_state = True if self.shrinkify_cache else False
            # self.overrides = json.loads(self.override_file.read_text()) if self.shrinkify_cache is not None and self.override_file.is_file() else {}
            self.overrides = ShrinkifyConfig.MetadataRuntime.YoutubeMusicMetadata.override_song
            super().__init__(*args, **kwargs)
        
        def set_cache_state(self, state: bool):
            self.cache_state = state
        
        def set_cache_init(self):
            '''
            set cache state to the initial state
            '''
            self.cache_state = True #if self.override_file else False
        
        def get_override(self, key, val):
            if key == "song":
                try:
                    return [o for o in ShrinkifyConfig.MetadataRuntime.YoutubeMusicMetadata.override_song if val == o[0]][0][1]
                except IndexError:
                    return False
            elif key == "artist":
                try:
                    return [o for o in ShrinkifyConfig.MetadataRuntime.YoutubeMusicMetadata.override_artist if val == o[0]][0][1]
                except IndexError:
                    return False
            else:
                return False
        
        def _generic_cache_fetch(self, input_value, override_type, parent_function, parent_args=[], parent_kwargs={}):
            if not self.shrinkify_cache:
                return parent_function(input_value, *parent_args, **parent_kwargs)
            
            if (override_val := self.get_override(override_type, input_value)):
                input_value = override_val
            
            cache = pathlib.Path(self.shrinkify_cache, f'{override_type}_cache.json')
            cache_exists = cache.is_file()
            if cache_exists and self.cache_state:
                json_cache = json.loads(cache.read_text('utf8'))
                if input_value in json_cache:
                    return json_cache[input_value]
            data = parent_function(input_value, *parent_args, **parent_kwargs)
            
            if cache_exists:
                json_cache = json.loads(cache.read_text('utf8'))
                json_cache[input_value] = data
                with cache.open('w') as cache:
                    cache.write(json.dumps(json_cache))
            else:
                cache.parent.mkdir(parents=True, exist_ok=True)
                with cache.open('w+') as cache:
                    cache.write(json.dumps({input_value: data}))
            return data
        
        def get_song(self, videoId: str, signatureTimestamp: int = None) -> dict:
            return self._generic_cache_fetch(videoId, 'song', super().get_song, [signatureTimestamp])

        def get_artist(self, channelId: str) -> dict:
            return self._generic_cache_fetch(channelId, 'artist', super().get_artist)
        
        def get_params(self, channelId: str, singles=False):
            #kind of like get_artist but only returns "params" for their album list
            type_ = 'albums' if not singles else 'singles'
            cd = super().get_artist(channelId)
            if 'params' in cd[type_]:
                return cd[type_]['params']
            else:
                return None
        
        def get_artist_albums(self, channelId: str, params: str):
            return self._generic_cache_fetch(channelId, 'artist_album', super().get_artist_albums, [params])
        
        def get_album(self, browseId: str) -> dict:
            return self._generic_cache_fetch(browseId, 'album', super().get_album)
