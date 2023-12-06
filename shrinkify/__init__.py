import base64
import copy
import os
import pathlib
import logging
import subprocess
import io
import argparse
import sys
import time
import hashlib
from types import EllipsisType
import shutil
from PIL import Image
from . import metadata
from . import config #FIXME
from . import songclass

import mutagen
import mutagen.easymp4
import mutagen.oggvorbis
import mutagen.flac
    
MUTAGEN_KEY_CONVERSION = {
    'year': '\xa9day',
    'encoder': '\xa9too'
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
    
    def is_valid_file(self, file: pathlib.Path, exist_ok=False):
        if set(file.parts).intersection(self.config.general.exclude_filter):
            return False
        if file.suffix not in self.config.general.input_types:
            return False
        if self.get_output_file(file).exists() and not exist_ok:
            return False
        return True

    def cleanup(self):
        root_list = filter(lambda x: self.is_valid_file(x, exist_ok=True), pathlib.Path(self.config.general.root).rglob("*"))
        child_list = set(self.get_output_file(f) for f in root_list)
        output_list = set(e for e in pathlib.Path(self.config.general.output).rglob("*") if e.is_file() and e.suffix == self.config.general.output_type)
        diffs = output_list.difference(child_list)
        for diff in diffs:
            print(str(diff))
            if self.config.utils.cleanup.delete:
                diff.unlink()

    def reorganize_util(self):
        root = pathlib.Path(self.config.general.root)
        last_tree = {(f, f.stat().st_size) for f in filter(lambda f: self.is_valid_file(f, exist_ok=True), root.rglob("*"))}
        retries = 0
        while True:
            try:
                current_tree = {(f, f.stat().st_size) for f in filter(lambda f: self.is_valid_file(f, exist_ok=True), root.rglob("*"))}
                missing_old = last_tree.difference(current_tree)
                copied_new = current_tree.difference(last_tree)
                
                #TODO: handle different files with same sizes
                original_files = {path: size for path, size in missing_old}
                new_files = {size: path for path, size in copied_new}
                
                stragglers = set()
                
                for original, hash in original_files.items():
                    if hash not in new_files:
                        logging.debug(f"Destination file for {original} not found, adding to straggler list")
                        stragglers.add((original, hash))
                        continue
                    new = new_files[hash]
                    comp_old = self.get_output_file(original)
                    if not comp_old.is_file():
                        logging.info("Compressed file doesn't exist, ignoring...")
                        last_tree = copy.deepcopy(current_tree)
                        continue
                    comp_new = self.get_output_file(new)
                    comp_new.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(comp_old, comp_new)
                    comp_old.unlink()
                    print(comp_old, '->', comp_new)
                
                
                last_tree = copy.deepcopy(current_tree)
                last_tree = last_tree.union(stragglers)
                
                        
            except KeyboardInterrupt:
                print("Control-C detected, exiting...")
                break

    def shrink_directory(self, directory: os.PathLike | str, update=False, continue_from: None | os.PathLike | str = None):
        pathdir = pathlib.Path(directory)
        valid_files = sorted(filter(lambda f: self.is_valid_file(f, exist_ok=update), pathdir.rglob("*")))
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
            self.shrink_file(songclass.Song(file), update=update)

    def shrink_file(self, song: songclass.Song, update: bool = False):
        #updating runs inplace, so find the child file and use it as the source
        if update and not song.path.is_relative_to(self.output):
            song.path = pathlib.Path(self.output, song.path.parent.relative_to(self.root)).with_suffix(self.config.general.output_type)
            if not song.path.is_file():
                raise RuntimeError(f"Tried to update {song}'s converted file but the converted file doesn't exist")

        song.output = pathlib.Path(song.path.parent, "shrinkify_temp").with_suffix(self.config.general.output_type)
        
        logging.info("parsing metadata")
        song = self.metaprocessor.parse(song)
        if not song.cover_image:
            logging.error("No cover image defined, creating emergency image")
            song.cover_image = Image.new("RGBA", (100, 100), "red")
        if self.config.conversion.rescale:
            song.cover_image.thumbnail(self.config.conversion.rescale)
        song.cover_image = song.cover_image.convert("RGBA")
        logging.debug(song)


        convert_cmd_base = copy.deepcopy(self.config.conversion.conversion_args)
        convert_cmd = []
        for argument in convert_cmd_base:
            if isinstance(argument, EllipsisType):
                if update:
                    convert_cmd.extend(['-a:c', 'copy'])
            elif isinstance(argument, str):
                convert_cmd.append(argument.format(
                    INPUT=str(song.resolved),
                    OUTPUT=str(song.output_resolved)
                ))
            else:
                raise TypeError("Invalid type in convert list")
        # convert_cmd = []
        # convert_cmd.extend(copy.copy(self.config.conversion.pre_args))
        # convert_cmd.extend(['-i', str(song.resolved), '-i', '-'])
        # convert_cmd.extend(copy.copy(self.config.conversion.mid_args))
        # if update:
        #     convert_cmd.extend(['-a:c', 'copy'])
        # if not MUTAGEN_ENABLED:
        #     for k, v in song.metadata.items():
        #         if isinstance(v, list): #multi-value tags
        #             v = ", ".join(v)
        #         convert_cmd.extend(['-metadata', f"{k}={v}"])
        # convert_cmd.append(str(song.output_resolved))
        logging.debug(f"{song}: command list: {convert_cmd}")
        logging.info(f"{song}: beginning conversion")

        ffmpeg_stdin = io.BytesIO()
        ffmpeg_proc = subprocess.Popen(convert_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)

        # song.cover_image.save(ffmpeg_stdin, format=self.config.conversion.thumbnail_format.strip("."))
        # ffmpeg_stdin.seek(0)

        # ffmpeg_stdout, ffmpeg_stderr = ffmpeg_proc.communicate(ffmpeg_stdin.read())
        ffmpeg_proc.wait()

        logging.debug("starting mutagen metadata adder thing")
        if self.config.general.output_type == '.m4a':
            muta_file = mutagen.easymp4.EasyMP4(song.output_resolved)
            for k, v in MUTAGEN_KEY_CONVERSION.items():
                muta_file.RegisterTextKey(k, v)
            for k, v in song.metadata.items():
                try:
                    muta_file[k] = v
                except mutagen.easymp4.EasyMP4KeyError as e:
                    logging.error(f"{type(e).__name__} {e}")
            muta_file.save()
        elif self.config.general.output_type == '.ogg':
            muta_file = mutagen.oggvorbis.OggVorbis(song.output_resolved)
            try:
                muta_file.add_tags()
            except:
                pass
            assert muta_file.tags is not None
            for k, v in song.metadata.items():
                muta_file.tags[k] = v
            #add thumbnail
            raw = io.BytesIO()
            song.cover_image.save(raw, format="png")
            raw.seek(0)
            img = mutagen.flac.Picture()
            img.data = raw.read()
            img.type = 3
            img.desc = "Cover (front)"
            img.mime = "image/png"
            img.width = song.cover_image.width
            img.height = song.cover_image.height
            img.depth = 32
            picture_data = img.write()
            encoded_data = base64.b64encode(picture_data)
            vcomment_value = encoded_data.decode("ascii")
            muta_file.tags['metadata_block_picture'] = [vcomment_value]
            
            muta_file.save()
        else:
            raise RuntimeError(f"Unsupported output format for mutagen metadata: {self.config.general.output_type}")
        
        logging.info(f"{song}: finished conversion")

        dummy_output = song.output
        if not dummy_output:
            raise RuntimeError("Song output is unset despite needing to be set before")

        song.output = self.get_output_file(song.path)
        song.output.parent.mkdir(parents=True, exist_ok=True)
        try:
            dummy_output.rename(song.output)
        except FileExistsError:
            #make sure nothing is deleted without another copy existing 
            song.output.rename(song.output.with_stem("_"+song.output.stem))
            dummy_output.rename(song.output)
            song.output.with_stem("_"+song.output.stem).unlink(missing_ok=True)
        
        time.sleep(self.config.conversion.throttle)
