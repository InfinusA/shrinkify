import io
import logging
import pathlib
#from . import MetadataHandler
import re
import time
import ytmusicapi
import json
import requests
import base64
from PIL import Image
from . import caching
from .. import config
from . import file
from .. import songclass

class YoutubeMusicMetadata(file.MetadataParser):
    identifier = "YoutubeMusic"
    def __init__(self, conf: config.Config, cache: caching.CacheConnector | None = None) -> None:
        self.conf = conf
        self.cache = cache
        self.ytm = ytmusicapi.YTMusic()
        if self.cache is not None:
            self.song_cache = self.cache.create_simple("ytmSongCache")
            self.song_cache.load_generic_schema("video_id", "raw_data")
            self.artist_cache = self.cache.create_simple("ytmArtistCache")
            self.artist_cache.load_generic_schema("channel_id", "raw_data")
            self.aa_cache = self.cache.create_simple("ytmArtistAlbumCache")
            self.aa_cache.load_schema("""CREATE TABLE IF NOT EXISTS ytmArtistAlbumCache(channel_id STRING NOT NULL, mode STRING NOT NULL, raw_data STRING NOT NULL, PRIMARY KEY (channel_id, mode));""")
            self.album_cache = self.cache.create_simple("ytmAlbumCache")
            self.album_cache.load_generic_schema("browse_id", "raw_data")
            self.search_cache = self.cache.create_simple("ytmSearchCache")
            self.search_cache.load_schema("""CREATE TABLE IF NOT EXISTS ytmSearchCache(query STRING NOT NULL, filter STRING NOT NULL, raw_data STRING NOT NULL, PRIMARY KEY (query, filter));""")
    
    def check_valid(self, song: songclass.Song) -> bool:
        for regex in self.conf.metadata.youtubemusic.filename_regex:
            if re.search(regex, song.path.name):
                return True
        return False
    
    def get_id(self, filename: str):
        for regex in self.conf.metadata.youtube.filename_regex:
            r = re.search(regex, filename)
            if r:
                return r.group(1)
        return False
    
    def fetch(self, song: songclass.Song) -> None | songclass.Song:
        video_id = self.get_id(song.path.name)
        if not video_id:
            return None
        album_id = identifier_info = None
        for res_func in (self.deadsimple_identifier,):
            res = res_func(video_id)
            if res:
                album_id, identifier_info = res
                break
        else:
            return None
        
        album = self.get_album(album_id)
        ytsong = None
        for track in album['tracks']:
            if track['videoId'] == video_id:
                ytsong = track
                break
        else:
            logging.warning("Using name-based rematching")
            song_title = identifier_info['title']
            for track in album['tracks']:
                if track['title'] == song_title:
                    ytsong = track
                    break
            else:
                logging.critical(album)
                raise RuntimeError("Could not find song in identified album (see debug log)")
        song['title'] = ytsong['title']
        song['artist'] = [a['name'] for a in ytsong['artists']]
        song['album'] = album['title']
        song['year'] = album['year']
    
        if tuple(pathlib.Path(self.conf.general.cache_dir).glob(f"{video_id}.*")):
            thumb_data = next(pathlib.Path(self.conf.general.cache_dir).glob(f"{video_id}.*")).read_bytes()
        else:
            thumb_data = requests.get(max(album['thumbnails'], key=lambda t: t['height'])['url']).content
            if pathlib.Path(self.conf.general.cache_dir).is_dir():
                pathlib.Path(self.conf.general.cache_dir, video_id).with_suffix(".jpg").write_bytes(thumb_data)
        song.cover_image = Image.open(io.BytesIO(thumb_data))
        song.parser = "Shrinkify/ytm"
        return song
    
    def deadsimple_identifier(self, video_id: str) -> tuple[str, dict] | None:
        song_info = self.get_song(video_id)
        if song_info['playabilityStatus']['status'] in ('UNPLAYABLE',):
            return None
        try:
            artist_info = self.get_artist(song_info['videoDetails']['channelId'])
        except KeyError:
            #immersivemusicsomethingorother
            return None
        if artist_info is None:
            return None
        true_id = None
        if 'albums' in artist_info:
            temp_album = self.get_album(artist_info['albums']['results'][0]['browseId'])
            for artist in temp_album['artists']:
                try:
                    new_artist = self.get_artist(artist['id'])
                    if new_artist and new_artist['channelId'] == artist_info['channelId']:
                        true_id = artist['id']
                        break
                except AttributeError:#deleted artist??
                    return None
        if not true_id and 'singles' in artist_info:
            temp_album = self.get_album(artist_info['singles']['results'][0]['browseId'])
            for artist in temp_album['artists']:
                new_artist = self.get_artist(artist['id'])
                if new_artist and new_artist['channelId'] == artist_info['channelId']:
                    true_id = artist['id']
                    break
        if not true_id and 'videos' in artist_info:
            for artist in artist_info['videos']['results'][0]['artists']:
                new_artist = self.get_artist(artist['id'])
                if new_artist and new_artist['channelId'] == artist_info['channelId']:
                    true_id = artist['id']
                    break
        if not true_id:
            return None
        
        true_album = None
        if 'albums' in artist_info:
            album_list: list = self.get_artist_albums(true_id, params=None, singles=False) if 'params' in artist_info['albums'] else artist_info['albums']['results'] #type:ignore
            for album_resp in album_list:
                album = self.get_album(album_resp['browseId'])
                for track in album['tracks']:
                    if track['videoId'] == video_id:
                        true_album = album_resp['browseId'], track
                        break
                if true_album:
                    break
                
        if not true_album and 'singles' in artist_info:
            single_list: list = self.get_artist_albums(true_id, params=None, singles=True) if 'params' in artist_info['singles'] else artist_info['singles']['results'] #type:ignore
            for single_resp in single_list:
                single = self.get_album(single_resp['browseId'])
                for track in single['tracks']:
                    if track['videoId'] == video_id:
                        true_album = single_resp['browseId'], track
                        break
                if true_album:
                    break
        
        if not true_album:
            search = self.get_search(f"{artist_info['name']} - {song_info['videoDetails']['title']}", "songs", limit=20)
            for result in search:
                if true_id in [a['id'] for a in result['artists']] and result['videoId'] == video_id:
                    if 'album' not in result: #strange off-case
                        continue
                    return result['album']['id'], result
            if self.conf.metadata.youtubemusic.use_very_inaccurate:
                logging.warning("Using slightly inaccurate guesser")
                for result in search:
                    if true_id in [a['id'] for a in result['artists']] and result['title'] in song_info['videoDetails']['title']:
                        return result['album']['id'], result
            return None
        
        else:
            return true_album
    
    def get_search(self, query: str, filter: str, limit=5):
        if self.cache and self.search_cache.contains(query=query, filter=filter):
            data = json.loads(base64.b64decode(self.search_cache.fetch_one(query=query, filter=filter)['raw_data']))
        else:
            data = self.ytm.search(query, filter, limit=limit)
            if self.cache:
                jsonified = base64.b64encode(json.dumps(data).encode("utf8")).decode("utf8")
                self.search_cache.insert({"query": query, "filter": filter, "raw_data": jsonified}, key=('query', 'filter'))
        return data

    def get_song(self, video_id: str):
        if self.cache and self.song_cache.contains(video_id=video_id):
            data = json.loads(base64.b64decode(self.song_cache.fetch_one(video_id=video_id)['raw_data']))
        else:
            data = self.ytm.get_song(video_id)
            if self.cache:
                jsonified = base64.b64encode(json.dumps(data).encode("utf8")).decode("utf8")
                self.song_cache.insert({"video_id": video_id, "raw_data": jsonified}, key='video_id')
        return data

    def get_artist(self, channel_id: str) -> dict | None:
        if not isinstance(channel_id, str):
            return None
        if self.cache and self.artist_cache.contains(channel_id=channel_id):
            data = json.loads(base64.b64decode(self.artist_cache.fetch_one(channel_id=channel_id)['raw_data']))
        else:
            data = self.ytm.get_artist(channelId=channel_id)
            if self.cache:
                jsonified = base64.b64encode(json.dumps(data).encode("utf8")).decode("utf8")
                self.artist_cache.insert({"channel_id": channel_id, "raw_data": jsonified}, key='channel_id')
        return data
    
    def get_artist_albums(self, channel_id: str, params: str | None = None, singles: bool = False):
        mode = 'singles' if singles else 'albums'
        if self.cache and self.aa_cache.contains(channel_id=channel_id, mode=mode):
            data = json.loads(base64.b64decode(self.aa_cache.fetch_one(channel_id=channel_id, mode=mode)['raw_data']))
        else:
            artistdata = self.ytm.get_artist(channel_id) #don't use cache for params as it will likely be invalid
            browse_id = artistdata[mode]['browseId']
            if 'params' in artistdata[mode]:
                params = artistdata[mode]['params']
            else:
                params = None
            try:
                data = self.ytm.get_artist_albums(browse_id, params) #type:ignore
            except KeyError:
                logging.critical("The dreaded KeyError: gridRenderer has occurred. Returning an empty list")
                return []
            if self.cache:
                jsonified = base64.b64encode(json.dumps(data).encode("utf8")).decode("utf8")
                self.aa_cache.insert({"channel_id": channel_id, "mode": mode, "raw_data": jsonified}, key=('channel_id', 'mode'))
        return data

    def get_album(self, browse_id: str):
        if self.cache and self.album_cache.contains(browse_id=browse_id):
            data = json.loads(base64.b64decode(self.album_cache.fetch_one(browse_id=browse_id)['raw_data']))
        else:
            data = self.ytm.get_album(browseId=browse_id)
            if self.cache:
                jsonified = base64.b64encode(json.dumps(data).encode("utf8")).decode("utf8")
                self.album_cache.insert({"browse_id": browse_id, "raw_data": jsonified}, key='browse_id')
        return data
        