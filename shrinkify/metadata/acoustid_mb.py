import io
import logging
import pathlib
import json
import base64
import time
from . import caching
from .. import config
from . import file
from .. import songclass
from PIL import Image
import requests
import acoustid

class AcoustIDMetadata(file.MetadataParser):
    identifier = "AcoustID"
    def __init__(self, conf: config.Config, cache: caching.CacheConnector | None) -> None:
        self.conf = conf
        self.session = requests.Session()
        self.session.headers['User-Agent'] = self.conf.metadata.acoustid.musicbrainz_agent
        self.session.headers['Accept'] = "application/json"
        self.cache = cache.create_simple("acoustidMetadata") if cache is not None else None
        self.cache2 = cache.create_simple("acoustidMetadata2") if cache is not None else None
        self.rec_cache = cache.create_simple("mbRecording") if cache is not None else None
        self.rel_cache = cache.create_simple("mbRelease") if cache is not None else None
        if self.cache and self.rec_cache and self.rel_cache and self.cache2:
            self.cache.load_generic_schema("relativePath", "data")
            self.cache2.load_generic_schema("relativePath", "data")
            self.rec_cache.load_generic_schema("id", "data")
            self.rel_cache.load_generic_schema("id", "data")
        #self.musicbrainz_cache = cache.create_simple("musicbrainzMetadata") if cache is not None else None

    def check_valid(self, song: songclass.Song) -> bool:
        if not self.conf.metadata.acoustid.api_key:
            return False
        if set(song.path.parts).intersection(self.conf.metadata.acoustid.special_exclude):
            return False
        else:
            return True
    
    @staticmethod
    def uncache(data):
        return json.loads(base64.b64decode(data))
    
    @staticmethod
    def cachify(data: object) -> bytes:
        return base64.b64encode(json.dumps(data).encode('utf8'))
            
    def fetch(self, song: songclass.Song) -> bool | songclass.Song:
        #get musicbrainz id
        if self.cache and self.cache.contains(relativePath=str(song.path.relative_to(self.conf.general.root))):
            acoustid_resp = self.uncache(self.cache.fetch_one(relativePath=str(song.path.relative_to(self.conf.general.root)))['data'])
        else:
            acoustid_resp = tuple(acoustid.match(self.conf.metadata.acoustid.api_key, str(song.path.expanduser())))
            if self.cache:
                self.cache.insert({'relativePath': str(song.path.relative_to(self.conf.general.root)), 'data': self.cachify(acoustid_resp)}, key='relativePath')
        #get actual metadata
        acoustid_resp = sorted(acoustid_resp, key=lambda t: t[0], reverse=True)
        if not acoustid_resp:
            return False
        logging.debug(acoustid_resp)
        recording = release = None
        
        for match in acoustid_resp:
            if match[0] < self.conf.metadata.acoustid.score_threshold:
                return False
            
            if self.rec_cache and self.rec_cache.contains(id=match[1]):
                recording = self.uncache(self.rec_cache.fetch_one(id=match[1])['data'])
            else: #not cached/no cache
                time.sleep(1)
                rec_resp = self.session.get(f"https://musicbrainz.org/ws/2/recording/{match[1]}", params={'inc': 'releases+work-rels+artist-credits'})
                time.sleep(1)
                if rec_resp.status_code != 200:
                    continue
                recording = rec_resp.json()
                logging.debug(recording)
                if 'releases' not in recording: #strange off-case
                    continue
                if self.rec_cache:
                    self.rec_cache.insert({'id': match[1], 'data': self.cachify(recording)}, key='id')
            related_mode = False
            for rec_release in recording['releases']:
                if self.rel_cache and self.rel_cache.contains(id=rec_release['id']):
                    release = self.uncache(self.rel_cache.fetch_one(id=rec_release['id'])['data'])
                    break
                else:
                    time.sleep(1)
                    rel_resp = self.session.get(f"https://musicbrainz.org/ws/2/release/{rec_release['id']}", params={'inc': 'artists+collections+labels+recordings+release-groups'})
                    time.sleep(1)
                    if rel_resp.status_code != 200:
                        continue
                    release = rel_resp.json()
                    if ('cover-art-archive' not in release or not release['cover-art-archive']['front']) and not self.conf.metadata.acoustid.allow_missing_image:
                        continue
                    if self.rel_cache:
                        self.rel_cache.insert({'id': rec_release['id'], 'data': self.cachify(release)}, key='id')
                    break
            else:
                #check related works
                relation = None
                related_mode = True
                for relation in recording['relations']:
                    if relation['target-type'] != 'work':
                        continue
                    break
                else:
                    continue
                if relation is None: continue
                time.sleep(1)
                related_works = self.session.get(f"https://musicbrainz.org/ws/2/work/{relation['work']['id']}", params={'inc': 'aliases+recording-rels'}).json()
                time.sleep(1)
                for related_recording in related_works['relations']:
                    if related_recording['target-type'] != 'recording':
                        continue
                    related_recording_data = self.session.get(f"https://musicbrainz.org/ws/2/recording/{related_recording['recording']['id']}", params={'inc': 'aliases+artist-credits+releases'}).json()
                    time.sleep(1)
                    for release_raw in related_recording_data['releases']:
                        release = self.session.get(f"https://musicbrainz.org/ws/2/release/{release_raw['id']}", params={'inc': 'artists+collections+labels+recordings+release-groups'}).json()
                        time.sleep(1)
                        logging.debug(release)
                        if ('cover-art-archive' not in release or not release['cover-art-archive']['front']) and not self.conf.metadata.acoustid.allow_missing_image:
                            logging.debug("no cover found")
                            continue
                        if self.rel_cache:
                            self.rel_cache.insert({'id': related_recording['recording']['id'], 'data': self.cachify(release)}, key='id')
                        break
                    else:
                        continue
                    break
                else:
                    continue
            break
        else:
            return False

        #get cover art
        cache_dir = pathlib.Path(self.conf.general.cache_dir)
        if self.conf.metadata.acoustid.allow_missing_image and not release['cover-art-archive']['front']:
            image = Image.new('RGBA', (1000,1000), 'black')
        elif cache_dir.is_dir() and pathlib.Path(cache_dir, f"{release['id']}.png").exists():
            image = Image.open(pathlib.Path(cache_dir, f"{release['id']}.png"))
        else:
            resp = self.session.get(f"https://coverartarchive.org/release/{release['id']}/front")
            if resp.status_code != 200:
                return False
            raw_data = resp.content
            image = Image.open(io.BytesIO(raw_data))
            if cache_dir.is_dir():
                pathlib.Path(cache_dir, release['id']+".png").write_bytes(raw_data)
        
        song['title'] = recording['title']
        song['artist'] = list(set(a['name'] for a in release['artist-credit']).union(set(a['name'] for a in recording['artist-credit'])))
        song['album'] = f"{release['release-group']['title']} ({', '.join(relation['attributes'])})" if related_mode else release['release-group']['title']
        song.cover_image = image
        if 'date' in release: song['date'] = release['date']
        if 'date' in release: song['year'] = release['date'][0:4]
        song.parser = 'shrinkify/acoustid'
        song['mbid'] = recording['id']
        song['mb-similarity'] = str(match[0])

        return song

