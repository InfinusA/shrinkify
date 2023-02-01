import os
import pathlib
import logging
from . import metadata
from . import config #FIXME
class Shrinkify(object):
    """
    The class used to handle the conversion of files
    """
    def __init__(self, root: os.PathLike | str, output: os.PathLike | str, convert_opts: config.ConfigGroup) -> None:
        #TODO: check for relativity
        self.root = pathlib.Path(root).resolve()
        self.output = pathlib.Path(output).resolve()
        self.convert_opts
        self.metaprocessor = metadata.MetadataProcessor()
    
    def get_output_file(self, file: os.PathLike | str) -> pathlib.Path:
        pfile = pathlib.Path(file)
        if pfile.is_absolute():
            if not pfile.is_relative_to(self.root):
                raise RuntimeError(f"File {pfile} is not relative to the music root")
            return pathlib.Path(self.output, pfile.relative_to(self.root))
        else:
            #assume relative to root
            logging.debug(f"Assuming file {pfile} is relative to root")
            return pathlib.Path(self.root, pfile)

    def shrink_directory(self, directory: os.PathLike | str):
        pathdir = pathlib.Path(directory)

    def shrink_file(self, filename: os.PathLike | str):
        #resolve file before processing
        file = pathlib.Path(filename).expanduser().resolve()
        meta = self.metaprocessor.parse(file)
