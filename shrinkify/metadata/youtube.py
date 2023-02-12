import io
import pathlib
import re
import requests
import base64
from PIL import Image
from dateutil import parser as dateparser
import json
from . import caching
from .. import config

class VideoNotFoundException(Exception):
    pass

class YoutubeMetadata(object):
    
    SCHEMA: str = """
    CREATE TABLE IF NOT EXISTS youtubeMetadata (
        video_id STRING PRIMARY KEY NOT NULL,
        raw_data STRING NOT NULL
    );
    """
    
    def __init__(self, conf: config.Config, cache: caching.CacheConnector | None = None) -> None:
        self.conf = conf
        self.cache = cache.create_simple("youtubeMetadata") if cache is not None else None
        if self.cache:
            self.cache.load_schema(YoutubeMetadata.SCHEMA)
        self.session = requests.Session()
        if self.conf.metadata.youtube.api_key is None:
            raise RuntimeError("Youtube API key not specified in config")
        else:
            self.session.params['key'] = self.conf.metadata.youtube.api_key # type: ignore
                
    def check_valid(self, file: pathlib.Path):
        if not self.conf.metadata.youtube.api_key:
            return False
        for regex in self.conf.metadata.youtube.filename_regex:
            if re.search(regex, file.name):
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
                self.cache.insert({'video_id': video_id, 'raw_data': base64.b64encode(raw).decode('utf8')})
                
        return data
    
    def get_thumbnail(self, video_id: str):
        if tuple(pathlib.Path(self.conf.general.cache_dir).glob(f"{video_id}.*")):
            return next(pathlib.Path(self.conf.general.cache_dir).glob(f"{video_id}.*")).read_bytes()
        else:
            data = requests.get(f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg").content
            if pathlib.Path(self.conf.general.cache_dir).is_dir():
                pathlib.Path(self.conf.general.cache_dir, video_id).with_suffix(".jpg").write_bytes(data)
            return data
    
    def fetch(self, file: pathlib.Path):
        video_id = self.get_id(file.name)
        if not video_id:
            return False
        try:
            data = self.get_video_info(video_id)
        except VideoNotFoundException:
            return False
        snippet = data['snippet']
        video_date = dateparser.parse(snippet['publishedAt'])
        output = {}
        output['title'] = snippet['title']
        output['album'] = self.conf.metadata.youtube.album_format.format(channelTitle=snippet['channelTitle'])
        output['artist'] = snippet['channelTitle']
        output['year'] = str(video_date.year)
        output['date'] = video_date.strftime(r"%F-%m-%d")
        output['comment'] = snippet['description']
        idat = io.BytesIO()
        idat.write(self.get_thumbnail(video_id))
        idat.seek(0)
        output['_thumbnail_image'] = Image.open(idat)
        
        return output
        