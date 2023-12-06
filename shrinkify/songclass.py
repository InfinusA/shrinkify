import pathlib
import typing
from typing import Any
from PIL import Image

class Song(object):
    def __init__(self, path: pathlib.Path, *, output: typing.Optional[pathlib.Path] = None, cover_image: typing.Optional[Image.Image] = None, **kwargs: typing.Any):
        self.path = path #should be the original, unprocessed path
        self.output = output
        self.cover_image = cover_image
        self._parser: typing.Optional[str] = None
        self.metadata: dict[str, typing.Any] = kwargs
    
    @property
    def parser(self):
        return self._parser
    
    @parser.setter
    def parser(self, value: str):
        self._parser = value
        self.metadata['encoder'] = value

    @property
    def resolved(self): #expand user and resolve
        if self.path:
            return self.path.expanduser().resolve()
        else:
            return None
    
    @property
    def output_resolved(self): #expand user and resolve
        if self.output:
            return self.output.expanduser().resolve()
        else:
            return None
    
    def update(self, d: dict):
        self.metadata.update(d)
    
    def setdefault(self, key: typing.Any, value: typing.Any):
        if key not in self.metadata:
            self.metadata[key] = value
    
    def __getitem__(self, key: str):
        return self.metadata[key]
    
    def __setitem__(self, key, value):
        self.metadata[key] = value
    
    def __delitem__(self, key):
        del self.metadata[key]
    
    def __contains__(self, item):
        return item in self.metadata
    
    @staticmethod
    def _trunc(s: str, l: int = 20) -> str:
        return s[:l]+'...' if len(s) > l else s
    
    def __repr__(self) -> str:
        t = ", ".join(f"{k}={self._trunc(v)}" for k, v in self.metadata.items())
        return f"Song({self.path}) [{t}]"

class YoutubeSong(Song):
    def __init__(self, path: pathlib.Path, yt_id: str, *, output: pathlib.Path | None = None, cover_image: Image.Image | None = None, **kwargs: typing.Any):
        super().__init__(path, output=output, cover_image=cover_image, **kwargs)
        self.yt_id = yt_id