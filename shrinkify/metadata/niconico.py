from datetime import datetime
import io
import pathlib
import subprocess
import json
import re
import requests
from abc import ABC, abstractmethod
from PIL import Image
from .. import config
from .. import songclass
from .file import MetadataParser
from . import caching

class NicoNicoMetadata(MetadataParser):
    identifier = "NicoNico"
    def __init__(self, conf: config.Config, cache: caching.CacheConnector | None = None, *args, **kwargs) -> None:
        self.conf = conf
        self.cache = cache.create_simple("niconicoMetadata") if cache is not None else None
        if self.cache:
            self.cache.load_generic_schema("video_id", "raw_data")

    def check_valid(self, song: songclass.Song) -> bool:
        for regex in self.conf.metadata.niconico.filename_regex:
            if re.search(regex, song.path.name):
                return True
        return False
    
    def get_id(self, filename: str):
        for regex in self.conf.metadata.niconico.filename_regex:
            r = re.search(regex, filename)
            if r:
                return r.group(1)
        return False
    
    def get_owner_icon(self, link: str):
        try:
            owner_id = re.search('/\d+/(\d+\.jpg)', link).group(1)
        except AttributeError: #blank profile/etc
            return requests.get(link).content
        if tuple(pathlib.Path(self.conf.general.cache_dir).glob(f"nnd{owner_id}.*")):
            return next(pathlib.Path(self.conf.general.cache_dir).glob(f"nnd{owner_id}.*")).read_bytes()
        else:
            data = requests.get(link).content
            if pathlib.Path(self.conf.general.cache_dir).is_dir():
                pathlib.Path(self.conf.general.cache_dir, f'nnd{owner_id}').with_suffix(".jpg").write_bytes(data)
            return data
    
    def fetch(self, song: songclass.Song) -> None | songclass.Song:
        video_id = self.get_id(song.path.name)
        cmd = [e.format(VIDEO_ID=video_id) for e in self.conf.metadata.niconico.fetch_command]
        if self.cache and self.cache.contains(video_id=video_id):
            data = json.loads(self.cache.fetch_one(video_id=video_id)['raw_data'])
        else:
            data = json.loads(subprocess.check_output(cmd).decode('utf8'))
            if self.cache:
                self.cache.insert({'video_id': video_id, 'raw_data': json.dumps(data)}, key='video_id')
        
        video_date = datetime.strptime(data['upload_date'], r'%Y%m%d')
        
        song.metadata['title'] = data['title']
        song.metadata['artist'] = data['_api_data']['owner']['nickname']
        song.metadata['album'] = self.conf.metadata.niconico.album_format.format(channelTitle=data['_api_data']['owner']['nickname'])
        song.metadata['year'] = str(video_date.year)
        song.metadata['date'] = video_date.strftime(r"%F-%m-%d")
        song.metadata['comment'] = data['_api_data']['video']['description']
        
        idat = io.BytesIO()
        idat.write(self.get_owner_icon(data['_api_data']['owner']['iconUrl']))
        idat.seek(0)
        song.cover_image = Image.open(idat)
        song.parser = "Shrinkify/niconico"
        return song