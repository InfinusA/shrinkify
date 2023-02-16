import io
import pathlib
import json
import base64
import time
from . import caching
from .. import config
from PIL import Image
import requests
import acoustid

class AcoustIDMetadata(object):
    def __init__(self, conf: config.Config, cache: caching.CacheConnector | None) -> None:
        self.conf = conf
        self.session = requests.Session()
        self.session.headers['User-Agent'] = self.conf.metadata.acoustid.musicbrainz_agent
        self.session.headers['Accept'] = "application/json"
        self.cache = cache.create_simple("acoustidMetadata") if cache is not None else None
        self.infocache = cache.create_simple("musicbrainzMetadata") if cache is not None else None
        if self.cache and self.infocache:
            self.cache.load_generic_schema("relativePath", "data")
            self.infocache.load_generic_schema("id", "data")
        #self.musicbrainz_cache = cache.create_simple("musicbrainzMetadata") if cache is not None else None

    def check_valid(self, file: pathlib.Path):
        if not self.conf.metadata.acoustid.api_key:
            return False
        if set(file.parts).intersection(self.conf.metadata.acoustid.special_exclude):
            return False
        else:
            return True
    
    @staticmethod
    def uncache(data):
        return json.loads(base64.b64decode(data))
    
    @staticmethod
    def cachify(data):
        return base64.b64encode(json.dumps(data).encode('utf8'))
    
    def fetch(self, file: pathlib.Path):
        #get musicbrainz id
        if self.cache and self.cache.contains(relativePath=str(file.relative_to(self.conf.general.root))):
            acoustid_resp = self.uncache(self.cache.fetch_one(relativePath=str(file.relative_to(self.conf.general.root)))['data'])
        else:
            acoustid_resp = tuple(acoustid.match(self.conf.metadata.acoustid.api_key, str(file.expanduser().resolve())))
            if self.cache:
                self.cache.insert({'relativePath': str(file.relative_to(self.conf.general.root)), 'data': self.cachify(acoustid_resp)})
        #get actual metadata
        acoustid_resp = sorted(acoustid_resp, key=lambda t: t[0], reverse=True)
        if not acoustid_resp:
            return False
        selected_response = acoustid_resp[0]
        if selected_response[0] < self.conf.metadata.acoustid.score_threshold:
            return False
        if self.infocache and self.infocache.contains(id=selected_response[1]):
            recording = {} #TODO: Actually cache responses
            release = self.uncache(self.infocache.fetch_one(id=selected_response[1])['data'])
        else:
            time.sleep(1)
            resp = self.session.get(f"https://musicbrainz.org/ws/2/recording/{selected_response[1]}", params={'inc': 'releases'})
            time.sleep(1)
            recording = resp.json()
            release_id = recording['releases'][0]['id']
            resp = self.session.get(f"https://musicbrainz.org/ws/2/release/{release_id}", params={'inc': 'artists+collections+labels+recordings+release-groups'})
            time.sleep(1)
            release = resp.json()
        
        #check if cover art exists; if it doesn't then there's no point in continuing since that's like half the point of the program
        if release['cover-art-archive']['count'] < 1 and not self.conf.metadata.acoustid.allow_missing_image:
            return False
        #get cover art
        cache_dir = pathlib.Path(self.conf.general.cache_dir)
        if self.conf.metadata.acoustid.allow_missing_image:
            image = Image.new('RGBA', (1000,1000), 'black')
        elif cache_dir.is_dir() and pathlib.Path(cache_dir, f"{release['id']}.png").exists():
            image = Image.open(pathlib.Path(cache_dir, f"{release['id']}.png"))
        else:
            resp = self.session.get(f"https://coverartarchive.org/release/{release['id']}/front")
            raw_data = resp.content
            image = Image.open(io.BytesIO(raw_data))
            if cache_dir.is_dir():
                pathlib.Path(cache_dir, release['id']+".png").write_bytes(raw_data)
        
        output = {
            'title': recording['title'],
            'artist': [a['name'] for a in release['artist-credit']],
            'album': release['release-group']['title'],
            'date': release['date'],
            'year': release['date'][0:4],
            '_thumbnail_image': image
        }

        return output

