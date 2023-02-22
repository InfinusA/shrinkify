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

try:
    import mutagen
    import mutagen.easymp4
    MUTAGEN_ENABLED = True
except ImportError:
    MUTAGEN_ENABLED = False
    
MUTAGEN_KEY_CONVERSION = {
    'year': '\xa9day'
}

class Shrinkify(object):
    """
    The class used to handle the conversion of files
    """
    def __init__(self, config: config.Config) -> None:
        #TODO: check for relativity
        self.root = pathlib.Path(config.general.root)
        self.output = pathlib.Path(config.general.output)
        self.config = config
        self.metaprocessor = metadata.MetadataParser(self.config)
    
    def get_output_file(self, file: os.PathLike | str) -> pathlib.Path:
        pfile = pathlib.Path(file)
        if pfile.is_absolute():
            if not pfile.is_relative_to(self.root):
                raise RuntimeError(f"File {pfile} is not relative to the music root {self.root}")
            return pathlib.Path(self.output, pfile.relative_to(self.root)).with_suffix(self.config.general.output_type)
        else:
            #assume relative to root
            logging.debug(f"Assuming file {pfile} is relative to root")
            return pathlib.Path(self.root, pfile).with_suffix(self.config.general.output_type)
    
    def is_valid_file(self, file: pathlib.Path, update=False):
        if set(file.parts).intersection(self.config.general.exclude_filter):
            return False
        if file.suffix not in self.config.general.input_types:
            return False
        if self.get_output_file(file).exists() and not update:
            return False
        return True

    def shrink_directory(self, directory: os.PathLike | str, update=False, continue_from: None | os.PathLike | str = None):
        pathdir = pathlib.Path(directory)
        valid_files = sorted(filter(lambda f: self.is_valid_file(f, update=update), pathdir.rglob("*")))
        #TODO: Force conversion
        logging.debug(tuple(valid_files))
        skip = continue_from is not None
        for fileno, file in enumerate(valid_files):
            if skip:
                if continue_from == file or continue_from == self.get_output_file(file):
                    skip = False
                else:
                    continue
            logging.info(f"Converting {file.name} ({fileno+1}/{len(valid_files)})")
            self.shrink_file(file, update=update)

    def shrink_file(self, filename: os.PathLike | str, update: bool = False):
        #resolve file before processing
        file = pathlib.Path(filename).expanduser()

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
        convert_cmd.extend(['-i', str(file.expanduser()), '-i', '-'])
        convert_cmd.extend(copy.copy(self.config.conversion.mid_args))
        if update:
            convert_cmd.extend(['-a:c', 'copy'])
        if not MUTAGEN_ENABLED:
            for k, v in meta.items():
                if k.startswith('_'):
                    continue
                if isinstance(v, list): #multi-value tags
                    v = ", ".join(v)
                convert_cmd.extend(['-metadata', f"{k}={v}"])
        convert_cmd.append(str(output.expanduser()))
        logging.debug(f"{file.name}: command list: {convert_cmd}")
        logging.info(f"{file.name}: beginning conversion")

        ffmpeg_stdin = io.BytesIO()
        ffmpeg_proc = subprocess.Popen(convert_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)

        meta['_thumbnail_image'].save(ffmpeg_stdin, format=self.config.conversion.thumbnail_format.strip("."))
        ffmpeg_stdin.seek(0)

        ffmpeg_stdout, ffmpeg_stderr = ffmpeg_proc.communicate(ffmpeg_stdin.read())
        ffmpeg_proc.wait()
        if MUTAGEN_ENABLED:
            logging.debug("starting mutagen metadata adder thing")
            if self.config.general.output_type == '.m4a':
                muta_file = mutagen.easymp4.EasyMP4(output.expanduser())
                for k, v in MUTAGEN_KEY_CONVERSION.items():
                    muta_file.RegisterTextKey(k, v)
                for k, v in meta.items():
                    if k[0] == "_":
                        continue
                    try:
                        muta_file[k] = v
                    except mutagen.easymp4.EasyMP4KeyError as e:
                        logging.error(f"{type(e).__name__} {e}")
                muta_file.save()
            else:
                raise RuntimeError(f"Unsupported output format for mutagen metadata: {self.config.general.output_type}")
        
        logging.info(f"{file.name}: finished conversion")

        real_output = self.get_output_file(file)
        real_output.parent.mkdir(parents=True, exist_ok=True)
        try:
            output.rename(real_output)
        except FileExistsError:
            #make sure nothing is deleted without another copy existing 
            real_output.rename(real_output.with_stem("_"+real_output.stem))
            output.rename(real_output)
            real_output.with_stem("_"+real_output.stem).unlink(missing_ok=True)
        
        time.sleep(self.config.conversion.throttle)
