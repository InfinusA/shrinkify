import ytmusicapi
import json
import pathlib
import requests
import logging
import re

from .shrink_utils import data_to_thumbnail
from ..config import ShrinkifyConfig
from .. import utils

import sys

class YoutubeMusicMetadata(object):
    '''
    known broken songs:
    X inabakumori - lagtrain (broken cache)
    pinnochiop - reincarnation apple
    pinnochiop - i just hate people
    
    '''
    def __init__(self):
        self.ytm = self.CacheYTMusic(shrinkify_cache=ShrinkifyConfig.cache, override=ShrinkifyConfig.Metadata.YoutubeMusicMetadata.override_enabled)

    def fetch(self, source_id, no_meta=False, no_thumb=False, no_cache=False):
        original_id = source_id
        try:
            if [o for o in ShrinkifyConfig.Metadata.YoutubeMusicMetadata.override_song if source_id  == o[0]]:
                source_id = [o for o in ShrinkifyConfig.Metadata.YoutubeMusicMetadata.override_song if source_id in o][0][1]
        except KeyError:
            return False
        self.ytm.set_cache_state(not no_cache)
        yt_song = self.ytm.get_song(source_id)
        if yt_song['playabilityStatus']['status'] in ('ERROR', 'LOGIN_REQUIRED'):
            logging.error("ytm errored or requires login.")
            return False
        elif yt_song['playabilityStatus']['status'] in ('UNPLAYABLE',):
            logging.error("ytm not playable. giving it a shot anyways")
        
        #get ytm entry by the music footer on the video
        #if it doesn't exist, there is no exact (non-fuzzy and not guessing) way to get the ytm video from the yt video
        #some of the techniques should be considered fuzzy, but they're accurate enough that they're basically exact
        data = requests.get(f"https://youtube.com/watch?v={original_id}").content.decode("utf8")
        real_data = json.loads(re.search("ytInitialData\s*=\s*(\{.*?)\s*;\s*</script>", data).group(1))
        description_meta = next(filter(lambda d: d['engagementPanelSectionListRenderer']['targetId']=='engagement-panel-structured-description', real_data['engagementPanels']))['engagementPanelSectionListRenderer']
        try:
            music_meta = next(filter(lambda d: 'videoDescriptionMusicSectionRenderer' in d, description_meta['content']['structuredDescriptionContentRenderer']['items']))
        except StopIteration:
            logging.warning("using innacurate artist/title detection")
            title = yt_song['videoDetails']['title']
            artist = yt_song['videoDetails']['author']
        else:
            try:
                title = next(filter(lambda d: d['infoRowRenderer']['title']['simpleText'] == "SONG", music_meta['videoDescriptionMusicSectionRenderer']['carouselLockups'][0]['carouselLockupRenderer']['infoRows']))["infoRowRenderer"]["defaultMetadata"]["simpleText"]
            except KeyError:
                title = next(filter(lambda d: d['infoRowRenderer']['title']['simpleText'] == "SONG", music_meta['videoDescriptionMusicSectionRenderer']['carouselLockups'][0]['carouselLockupRenderer']['infoRows']))["infoRowRenderer"]["defaultMetadata"]['runs'][0]['text']
            try:
                artist = next(filter(lambda d: d['infoRowRenderer']['title']['simpleText'] == "ARTIST", music_meta['videoDescriptionMusicSectionRenderer']['carouselLockups'][0]['carouselLockupRenderer']['infoRows']))["infoRowRenderer"]["defaultMetadata"]['simpleText']
            except KeyError:
                artist = next(filter(lambda d: d['infoRowRenderer']['title']['simpleText'] == "ARTIST", music_meta['videoDescriptionMusicSectionRenderer']['carouselLockups'][0]['carouselLockupRenderer']['infoRows']))["infoRowRenderer"]["defaultMetadata"]['runs'][0]['text']
        
        #search filtering (let ytm do the work)
        ytm_song = ytm_album = None
        for result in self.ytm.search(f"{title} - {artist}", filter="songs", limit=5):
            #ideal
            if result['videoId'] == source_id or result['videoId'] == original_id:
                ytm_song = result
                break
            #artist name/id and song name
            elif set((yt_song["videoDetails"]["author"], artist, yt_song['videoDetails']['channelId'])).intersection([a["name"]for a in result['artists']]+[a["id"]for a in result['artists']]) and result['title'] == yt_song['videoDetails']["title"]:
                ytm_song = result
                break
            #artist name/id and song name and song's alternate intersect
            elif set((yt_song["videoDetails"]["author"], artist, yt_song['videoDetails']['channelId'])).intersection([a["name"] for a in result['artists']]+[a["id"]for a in result['artists']]) and set(e['title'] for e in yt_song['microformat']['microformatDataRenderer']['linkAlternates'] if 'title' in e).intersection(set(e['title'] for e in self.ytm.get_song(result['videoId'])['microformat']['microformatDataRenderer']['linkAlternates'] if 'title' in e)):
                ytm_song = result
                break
            #risky searching, relying on the fact that yt names are often longer than ytm names
            elif set((yt_song["videoDetails"]["author"], artist, yt_song['videoDetails']['channelId'])).intersection([a["name"] for a in result['artists']]+[a["id"]for a in result['artists']]) and result['title'] in yt_song['videoDetails']["title"]:
                ytm_song = result
                logging.warning("using possibly risky song detector")
                break
            #riskier searching, this time also trying to guess the author
            elif set((yt_song["videoDetails"]["author"], artist, self.ytm.get_artist(yt_song['videoDetails']['channelId'])['name'])).intersection(a["name"] for a in result['artists']) and result['title'] in yt_song['videoDetails']["title"]:
                ytm_song = result
                logging.warning("using possibly risky song detector")
                break
        else:
            logging.warning("trying slow matching")
            res = self.slow_match(yt_song, source_id, original_id)
            if not res:
                logging.warning("could not find ytm entry")
                return False
            ytm_song, ytm_album = res
        
        if not ytm_song:
            logging.warning("could not find ytm entry")
            return False
        
        if not ytm_album:
            ytm_album = self.ytm.get_album(ytm_song['album']['id'])
        
        shrinkify_metadata = {}
        if not no_meta:
            shrinkify_metadata['title'] = ytm_song['title']
            #TODO: handle multiple artists
            try:
                shrinkify_metadata['artist'] = ytm_album['artists'][0]['name']
            except KeyError:
                shrinkify_metadata['artist'] = ytm_song['artists'][0]['name']
            shrinkify_metadata['album'] = ytm_album['title'] if ytm_album is not None else None
            shrinkify_metadata['year'] = ytm_album['year']
            shrinkify_metadata['date'] = ytm_album['year']
        if not no_thumb:
            if ShrinkifyConfig.cache:
                cache_file = pathlib.Path(ShrinkifyConfig.cache, f'{source_id}.png')
                if cache_file.is_file() and not no_cache:
                    raw_thumbnail = cache_file.read_bytes()
                else:
                    raw_thumbnail = requests.get(max(ytm_album['thumbnails'], key=lambda x: x['height']+x['width'])['url']).content
                    cache_file.write_bytes(raw_thumbnail)
            else:
                raw_thumbnail = requests.get(max(ytm_album['thumbnails'], key=lambda x: x['height']+x['width'])['url']).content

            shrinkify_metadata['_thumbnail_image'] = data_to_thumbnail(raw_thumbnail)
        
        return shrinkify_metadata
        
    def slow_match(self, song_info, source_id, original_id):
        #extremely precise but slow and low hit rate
        try:
            if [o for o in ShrinkifyConfig.Metadata.YoutubeMusicMetadata.override_artist if song_info['videoDetails']['channelId']  == o[0]]:
                artist_id = [o for o in ShrinkifyConfig.Metadata.YoutubeMusicMetadata.override_artist if song_info['videoDetails']['channelId'] in o][0][1]
            else:
                artist_id = song_info['videoDetails']['channelId']
        except KeyError:
            return False
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
                    if song['videoId'] in (source_id, original_id) or (ShrinkifyConfig.Metadata.YoutubeMusicMetadata.name_match and song_info['videoDetails']['title'] == song['title']): #some songs are strange and the url links to the original, not the yt music ver
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
                    if track['videoId'] in (source_id, original_id): #some songs are strange and the url links to the original, not the yt music ver
                        logging.info(f"{source_id}: Found single")
                        songfound = True
                        target_song = track
                        target_album = song
                        break
                if songfound:
                    break
        
        if not songfound:
            for method in utils.match_ytm_methods(ShrinkifyConfig.Metadata.YoutubeMusicMetadata.name_match):
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
                            if method(song['title'], song_info['videoDetails']['title']): #some songs are strange and the url links to the original, not the yt music ver
                                logging.info(f"{source_id}: Found song in album")
                                songfound = True
                                target_song = song
                                target_album = album
                                break
                        if songfound:
                            break
                
                if not songfound and 'singles' in artist_info:
                    logging.info(f"{source_id}: Searching singles")
                    if self.ytm.get_params(artist_id, singles=True):
                        songs = self.ytm.get_artist_albums(artist_id, self.ytm.get_params(artist_id, singles=True))
                    else:
                        songs = artist_info['singles']['results']
                    for song in songs:
                        song_data = self.ytm.get_album(song['browseId'])
                        for track in song_data['tracks']:
                            if method(song['title'], song_info['videoDetails']['title']):
                                songfound = True
                                target_song = track
                                target_album = song
                                break
                        if songfound:
                            break
            
        if not songfound: #no song found at all
            logging.info(f"{source_id}: No song found")
            return False
        
        return target_song, target_album
    
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
            self.overrides = ShrinkifyConfig.Metadata.YoutubeMusicMetadata.override_song
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
                    return [o for o in ShrinkifyConfig.Metadata.YoutubeMusicMetadata.override_song if val == o[0]][0][1]
                except IndexError:
                    return False
            elif key == "artist":
                try:
                    return [o for o in ShrinkifyConfig.Metadata.YoutubeMusicMetadata.override_artist if val == o[0]][0][1]
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
