#!/usr/bin/python
import argparse
import logging
import pathlib
import enum

from . import Shrinkify, playlist, tag
from .config import ShrinkifyConfig

#TODO: normalize config names

def full_entrypoint():
    ShrinkifyExec(ShrinkifyExec.enums.MAIN).parse()
def shrink_entrypoint():
    ShrinkifyExec(ShrinkifyExec.enums.SHRINK).parse()
def tag_entrypoint():
    ShrinkifyExec(ShrinkifyExec.enums.TAG).parse()

class ShrinkifyExec(object):
    class enums(enum.Enum):
        MAIN = "Shrinkify.py"
        SHRINK = "Shrinkify"
        TAG = "Tagify"
    def __init__(self, mode) -> None:
        self.mode = mode
        self.parser = argparse.ArgumentParser(mode)
        self.parser = self.global_opts(self.parser)
        if mode == self.enums.MAIN:
            subparsers = self.parser.add_subparsers(required=True)
            
            sub_shrink = subparsers.add_parser('shrink', aliases=['s'])
            sub_shrink.set_defaults(cmd=self.enums.SHRINK)
            self.shrink_opts(sub_shrink)
            
            sub_tag = subparsers.add_parser('tagify', aliases=['t'])
            sub_tag.set_defaults(cmd=self.enums.TAG)
            self.tag_opts(sub_tag)
            
        elif mode == self.enums.SHRINK:
            self.parser = self.shrink_opts(self.parser)
            
        elif mode == self.enums.TAG:
            self.parser = self.tag_opts(self.parser)
            
        else:
            raise RuntimeError(f"Unknown Mode: {mode}")
    
    def parse(self):
        ShrinkifyConfig.load_yaml()
        self.parser.parse_args(namespace=ShrinkifyConfig)
        logging.basicConfig(level=50-(ShrinkifyConfig.verbosity*10))
        logging.debug(dir(ShrinkifyConfig))
        if self.mode == self.enums.MAIN:
            self.mode = ShrinkifyConfig.cmd
        #purposeful if here
        if self.mode == self.enums.SHRINK:
            shrinkify = Shrinkify()
            if ShrinkifyConfig.Runtime.single_file:
                shrinkify.single_convert(ShrinkifyConfig.Runtime.single_file)
            else:
                shrinkify.recursive_convert()
            if ShrinkifyConfig.Shrinkify.delete_nonexisting:
                shrinkify.recursive_delete()
                
        elif self.mode == self.enums.TAG:
            tagify = tag.Tagify()
            if ShrinkifyConfig.Runtime.mode == 'a':
                tagify.add_tags(ShrinkifyConfig.Runtime.target, ShrinkifyConfig.Runtime.tags)
            elif ShrinkifyConfig.Runtime.mode == 'r':
                tagify.remove_tags(ShrinkifyConfig.Runtime.target, ShrinkifyConfig.Runtime.tags)
            elif ShrinkifyConfig.Runtime.mode == 'l':
                tagify.list_tags(ShrinkifyConfig.Runtime.target)
            tagify.generate_all()
        else:
            raise RuntimeError(f"Unknown Mode: {self.mode}")
        
    
    def global_opts(self, parser):
        parser.add_argument('-s', '--source-folder', dest='source_folder', type=lambda p: pathlib.Path(p).expanduser(), default=ShrinkifyConfig.source_folder)
        parser.add_argument('-o', '--output-folder', dest='output_folder', type=lambda p: pathlib.Path(p).expanduser(), default=ShrinkifyConfig.output_folder)
        parser.add_argument('-v', '--verbose',       dest='verbosity', action='count', default=0)
        parser.add_argument('--exclude',    dest='exclude_dir', nargs='+', help='list of directories to exclude', default=ShrinkifyConfig.exclude)
        parser.add_argument('--debug',      dest='debug', action='store_true')
        parser.add_argument('--cache',      dest='cache', type=lambda p: pathlib.Path(p).expanduser(), default=str(ShrinkifyConfig.cache))
        return parser
    
    def shrink_opts(self, parser):
        parser.add_argument('--simulate',       dest='simulate', action="store_true")
        parser.add_argument('-f', '--overwrite-existing', '--force', dest='Shrinkify.flag_overwrite', action='store_true', help="Overwrite existing files")
        parser.add_argument('--update-metadata',dest='Shrinkify.update_metadata', action='store_true', help='Update metadata without reconverting')
        parser.add_argument('-d', '--delete',   dest='Shrinkify.delete_nonexisting', action='store_true', help="Delete files not part of parent directory. Disabled by default")
        parser.add_argument('--filetypes',      dest='filetypes', nargs='+', help='list of filetypes to convert', default=ShrinkifyConfig.filetypes)
        parser.add_argument('-t', '--throttle', dest='Shrinkify.throttle_length', type=lambda x: int(x) if x.isdecimal() and (int(x) >= 0) else parser.error("Minimum throttle time is 0"), default=0)
        parser.add_argument('--continue-from',  dest='Runtime.continue_from', help="Continue from the file with this filename", type=lambda p: pathlib.Path(p).expanduser())
        parser.add_argument('--single-file',    dest='Runtime.single_file', type=lambda p: pathlib.Path(p).expanduser(), help="Only convert a single file.")
        
        metadata_args = parser.add_argument_group('Metadata')
        metadata_args.add_argument('--youtube-api-key', dest='Metadata.YoutubeMetadata.api_key')
        metadata_args.add_argument('--thumbnail-mode', type=int, dest='Metadata.ThumbnailGenerator.generator_mode', default=ShrinkifyConfig.Metadata.ThumbnailGenerator.generator_mode)
        return parser
        
    def tag_opts(self, parser):
        parser.add_argument('-m', '--mode', dest='Runtime.mode', default='a', choices=['a', 'r', 'l'])
        parser.add_argument('Runtime.target', type=lambda p: pathlib.Path(p).expanduser() if p != "CURRENT" else tag.enums.AUTOMATIC)
        parser.add_argument('Runtime.tags', nargs='*', default=[], metavar="[tags]")
        return parser
    