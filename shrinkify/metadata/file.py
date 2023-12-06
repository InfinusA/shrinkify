import io
import pathlib
import subprocess
import json
from abc import ABC, abstractmethod
from PIL import Image
from .. import config
from .. import songclass

class MetadataParser(ABC):
    identifier = "DEFAULT"
    @abstractmethod
    def __init__(self, *args, **kwargs) -> None:
        pass

    @abstractmethod
    def check_valid(self, song: songclass.Song) -> bool:
        pass

    @abstractmethod
    def fetch(self, song: songclass.Song) -> None | songclass.Song:
        pass

class FileMetadata(MetadataParser):
    '''
    Reference implementation for a metadata parser
    '''
    identifier = "File"
    def __init__(self, conf: config.Config, *args, **kwargs) -> None:
        self.conf = conf

    def check_valid(self, song: songclass.Song) -> bool:
        return True
    
    def fetch(self, song: songclass.Song) -> None | songclass.Song:
        meta = json.loads(subprocess.check_output(self.conf.metadata.file.ffprobe_command+(str(song.path),)).decode('utf8'))
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
            song.update(output)
        song.setdefault("title", song.path.stem)
        song.setdefault("artist", song.path.parent.name)
        song.setdefault("album", song.path.parent.name)

        for stream in meta['streams']:
            if stream['codec_name'] in self.conf.metadata.file.thumbnail_types:
                cmd = self.conf.metadata.file.ffthumb_pre_command+(str(song.path),)+self.conf.metadata.file.ffthumb_post_command
                data = subprocess.check_output(cmd)
                img = Image.open(io.BytesIO(data))
                break
        else:
            coverfile = pathlib.Path(song.path.parent, "cover.png")
            if coverfile.is_file():
                img = Image.open(coverfile)
            elif self.conf.metadata.file.default_thumbnail and pathlib.Path(self.conf.metadata.file.default_thumbnail).is_file():
                img = Image.open(pathlib.Path(self.conf.metadata.file.default_thumbnail))
            else:
                img = Image.new('RGBA', (1000,1000), 'black')
        song.cover_image = img
        song.parser = "Shrinkify/file"
        return song