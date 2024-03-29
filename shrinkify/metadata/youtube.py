import io
import pathlib
import re
import requests
import base64
import logging
from PIL import Image
from dateutil import parser as dateparser
import json
from . import caching
from .. import config
from .. import songclass
from . import file

class VideoNotFoundException(Exception):
    pass

class YoutubeMetadata(file.MetadataParser):
    identifier = "Youtube"
    def __init__(self, conf: config.Config, cache: caching.CacheConnector | None = None) -> None:
        self.conf = conf
        self.cache = cache.create_simple("youtubeMetadata") if cache is not None else None
        if self.cache:
            self.cache.load_generic_schema("video_id", "raw_data")
        self.session = requests.Session()
        if self.conf.metadata.youtube.api_key is None:
            logging.warning("Youtube API key not specified in config")
        else:
            self.session.params['key'] = self.conf.metadata.youtube.api_key # type: ignore
                
    def check_valid(self, song: songclass.Song):
        if not self.conf.metadata.youtube.api_key:
            return False
        for regex in self.conf.metadata.youtube.filename_regex:
            if re.search(regex, song.path.name):
                return True
        return False

    def get_id(self, filename: str):
        for regex in self.conf.metadata.youtube.filename_regex:
            r = re.search(regex, filename)
            if r:
                return r.group(1)
        return False
    
    def get_video_info(self, video_id: str) -> dict:
        if self.cache and self.cache.contains(video_id=video_id):
            fetch = self.cache.fetch_one(video_id=video_id)
            try:
                data = json.loads(base64.b64decode(fetch['raw_data']))['items'][0]
            except IndexError:
                raise VideoNotFoundException()
        else:
            resp = self.session.get('https://www.googleapis.com/youtube/v3/videos', params={'part': 'contentDetails,id,liveStreamingDetails,localizations,player,recordingDetails,snippet,statistics,status,topicDetails', 'id': video_id})
            raw = resp.content
            try:
                data = resp.json()['items'][0]
            except IndexError:
                raise VideoNotFoundException()
            if self.cache:
                self.cache.insert({'video_id': video_id, 'raw_data': base64.b64encode(raw).decode('utf8')}, key='video_id')
                
        return data
    
    def get_thumbnail(self, video_id: str):
        if tuple(pathlib.Path(self.conf.general.cache_dir).glob(f"{video_id}.*")):
            return next(pathlib.Path(self.conf.general.cache_dir).glob(f"{video_id}.*")).read_bytes()
        else:
            data = requests.get(f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg").content
            if pathlib.Path(self.conf.general.cache_dir).is_dir():
                pathlib.Path(self.conf.general.cache_dir, video_id).with_suffix(".jpg").write_bytes(data)
            return data
    
    def get_channel_icon(self, channel_id: str):
        if tuple(pathlib.Path(self.conf.general.cache_dir).glob(f"{channel_id}.*")):
            return next(pathlib.Path(self.conf.general.cache_dir).glob(f"{channel_id}.*")).read_bytes()
        else:
            icon_json = json.loads(self.session.get(f"https://www.googleapis.com/youtube/v3/channels", params={'part': 'snippet', 'id': channel_id}).content)
            data = requests.get(max(icon_json['items'][0]['snippet']['thumbnails'].values(), key=lambda o: o['height']+o['width'])['url']).content
            if pathlib.Path(self.conf.general.cache_dir).is_dir():
                pathlib.Path(self.conf.general.cache_dir, channel_id).with_suffix(".jpg").write_bytes(data)
            return data
    
    def fetch(self, song: songclass.Song) -> None | songclass.Song:
        video_id = self.get_id(song.path.name)
        if not video_id:
            return None
        try:
            data = self.get_video_info(video_id)
        except VideoNotFoundException:
            return None
        snippet = data['snippet']
        video_date = dateparser.parse(snippet['publishedAt'])
        song['title'] = snippet['title']
        song['album'] = self.conf.metadata.youtube.album_format.format(channelTitle=snippet['channelTitle'])
        song['artist'] = snippet['channelTitle']
        song['year'] = str(video_date.year)
        song['date'] = video_date.strftime(r"%F-%m-%d")
        song['comment'] = snippet['description']
        idat = io.BytesIO()
        idat.write(self.get_channel_icon(snippet['channelId']))
        idat.seek(0)
        song.cover_image = Image.open(idat)
        song.parser = "Shrinkify/yt"
        return song
        