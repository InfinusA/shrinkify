import copy
import os
import pathlib
import logging
import subprocess
import io
import argparse
import time
from . import metadata
from . import config #FIXME

class Shrinkify(object):
    """
    The class used to handle the conversion of files
    """
    def __init__(self, config: config.Config) -> None:
        #TODO: check for relativity
        self.root = pathlib.Path(config.general.root).resolve()
        self.output = pathlib.Path(config.general.output).resolve()
        self.config = config
        self.metaprocessor = metadata.MetadataParser(self.config)
    
    def get_output_file(self, file: os.PathLike | str) -> pathlib.Path:
        pfile = pathlib.Path(file).resolve()
        if pfile.is_absolute():
            if not pfile.is_relative_to(self.root):
                raise RuntimeError(f"File {pfile} is not relative to the music root {self.root}")
            return pathlib.Path(self.output, pfile.relative_to(self.root)).with_suffix(self.config.general.output_type)
        else:
            #assume relative to root
            logging.debug(f"Assuming file {pfile} is relative to root")
            return pathlib.Path(self.root, pfile).with_suffix(self.config.general.output_type)

    def shrink_directory(self, directory: os.PathLike | str, update=False, continue_from: None | os.PathLike | str = None):
        pathdir = pathlib.Path(directory)
        valid_files = sorted(filter(lambda f: not set(self.config.general.exclude_filter).intersection(f.parts) and f.is_file() and f.suffix in self.config.general.input_types, pathdir.rglob("*")))
        skip = continue_from is not None
        for fileno, file in enumerate(valid_files):
            if skip:
                if continue_from == file or continue_from == self.get_output_file(file):
                    skip = False
                else:
                    continue
            if not update and self.get_output_file(file).is_file(): #TODO: force
                continue
            logging.info(f"Converting {file.name} ({fileno+1}/{len(valid_files)})")
            self.shrink_file(file, update=update)

    def shrink_file(self, filename: os.PathLike | str, update: bool = False):
        #resolve file before processing
        file = pathlib.Path(filename).expanduser().resolve()

        #updating runs inplace, so find the child file and use it as the source
        if update and not file.is_relative_to(self.output):
            file = pathlib.Path(self.output, file.parent.relative_to(self.root)).with_suffix(self.config.general.output_type)
            if not file.is_file():
                raise RuntimeError(f"Tried to update {file}'s converted file but the converted file doesn't exist")

        output = pathlib.Path(file.parent, "shrinkify_temp").with_suffix(self.config.general.output_type)
        
        logging.info("parsing metadata")
        meta = self.metaprocessor.parse(file)
        logging.debug(f"{file.name}: metadata: {meta}")
        convert_cmd = []
        convert_cmd.extend(copy.copy(self.config.conversion.pre_args))
        convert_cmd.extend(['-i', str(file.expanduser().resolve()), '-i', '-'])
        convert_cmd.extend(copy.copy(self.config.conversion.mid_args))
        if update:
            convert_cmd.extend(['-a:c', 'copy'])
        for k, v in meta.items():
            if k.startswith('_'):
                continue
            convert_cmd.extend(['-metadata', f"{k}={v}"])
        convert_cmd.append(str(output.expanduser().resolve()))
        logging.debug(f"{file.name}: command list: {convert_cmd}")
        logging.info(f"{file.name}: beginning conversion")

        ffmpeg_stdin = io.BytesIO()
        ffmpeg_proc = subprocess.Popen(convert_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)

        meta['_thumbnail_image'].save(ffmpeg_stdin, format=self.config.conversion.thumbnail_format.strip("."))
        ffmpeg_stdin.seek(0)

        ffmpeg_stdout, ffmpeg_stderr = ffmpeg_proc.communicate(ffmpeg_stdin.read())
        ffmpeg_proc.wait()
        logging.info(f"{file.name}: finished conversion")

        real_output = self.get_output_file(file).resolve()
        real_output.parent.mkdir(parents=True, exist_ok=True)
        try:
            output.rename(real_output)
        except FileExistsError:
            #make sure nothing is deleted without another copy existing 
            real_output.rename(real_output.with_stem("_"+real_output.stem))
            output.rename(real_output)
            real_output.with_stem("_"+real_output.stem).unlink(missing_ok=True)
        
        time.sleep(self.config.conversion.throttle)
