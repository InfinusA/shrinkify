import io
import pathlib
import subprocess
import json
from PIL import Image
from .. import config
#from . import MetadataHandler

class FileMetadata(object):#MetadataHandler):
    def __init__(self, conf: config.Config) -> None:
        self.conf = conf

    def check_valid(self, file: pathlib.Path) -> bool:
        return True
    
    def fetch(self, file: pathlib.Path) -> dict:
        meta = json.loads(subprocess.check_output(self.conf.metadata.file.ffprobe_command+(str(file),)).decode('utf8'))
        output = {}
        if 'tags' in meta['format']:
            output.update(meta['format']['tags'])
            output.pop("compatible_brands", None)
            output.pop("encoder", None)
            output.pop("ENCODER", None)
            output.pop("encoded_by", None)
            output.pop("major_brand", None)
            output.pop("minor_brand", None)
            output.pop("minor_version", None)
        output.setdefault("title", file.stem)
        output.setdefault("artist", file.parent.name)
        output.setdefault("album", file.parent.name)
        for stream in meta['streams']:
            if stream['codec_name'] in self.conf.metadata.file.thumbnail_types:
                cmd = self.conf.metadata.file.ffthumb_pre_command+(str(file),)+self.conf.metadata.file.ffthumb_post_command
                data = subprocess.check_output(cmd)
                img = Image.open(io.BytesIO(data))
                break
        else:
            img = Image.new('RGBA', (1000,1000), 'black')
        output['_thumbnail_image'] = img
        return output