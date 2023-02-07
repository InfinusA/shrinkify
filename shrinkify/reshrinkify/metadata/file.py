import pathlib
from . import MetadataHandler

class FileMetadata(MetadataHandler):
    def check_valid(self, file: pathlib.Path) -> bool:
        return True
    
    def parse(self, file: pathlib.Path) -> dict:
        return super().parse(file)