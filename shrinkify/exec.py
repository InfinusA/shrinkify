#!/usr/bin/env python3
import argparse
import pathlib
import logging
from . import Shrinkify
from .config import ShrinkifyConfig
from . import playlist as shrinkify_playlist
from . import tag as shrinkify_tag
import pprint
#TODO: global parser options (source/output directories always needed)
def global_opts(parser: argparse.ArgumentParser):
    parser.add_argument('-s', '--source-folder', dest='source_folder', type=lambda p: pathlib.Path(p).expanduser(), default=ShrinkifyConfig.source_folder)
    parser.add_argument('-o', '--output-folder', dest='output_folder', type=lambda p: pathlib.Path(p).expanduser(), default=ShrinkifyConfig.output_folder)
    parser.add_argument('-v', '--verbose',       dest='verbosity', action='count', default=0)
    parser.add_argument('--exclude',    dest='exclude_dir', nargs='+', help='list of directories to exclude', default=ShrinkifyConfig.exclude)
    parser.add_argument('--debug',      dest='flag_debug', action='store_true')
    parser.add_argument('--cache',      dest='cache', type=lambda p: pathlib.Path(p).expanduser(), default=str(ShrinkifyConfig.cache))
    

def shrink_parser(parser: argparse.ArgumentParser):
    parser.add_argument('--simulate',       dest='flag_simulate', action="store_true")
    parser.add_argument('-f', '--overwrite-existing', '--force', dest='Shrinkify.flag_overwrite', action='store_true', help="Overwrite existing files")
    parser.add_argument('--update-metadata',dest='Shrinkify.flag_update_metadata', action='store_true', help='Update metadata without reconverting')
    parser.add_argument('-d', '--delete',   dest='Shrinkify.flag_delete_nonexisting', action='store_true', help="Delete files not part of parent directory. Disabled by default")
    parser.add_argument('--filetypes',      dest='filetypes', nargs='+', help='list of filetypes to convert', default=ShrinkifyConfig.filetypes)
    parser.add_argument('-t', '--throttle', dest='Shrinkify.throttle_length', type=lambda x: int(x) if x.isdecimal() and (int(x) >= 0) else parser.error("Minimum throttle time is 0"), default=0)
    parser.add_argument('--continue-from',  dest='Shrinkify.continue_from', help="Continue from the file with this filename", type=lambda p: pathlib.Path(p).expanduser())
    parser.add_argument('--single-file',    dest='Shrinkify.single_file', type=lambda p: pathlib.Path(p).expanduser(), help="Only convert a single file.")
    
    metadata_args = parser.add_argument_group('Metadata')
    metadata_args.add_argument('--youtube-api-key', dest='Metadata.YoutubeMetadata.api_key')
    metadata_args.add_argument('--thumbnail-mode', type=int, dest='Metadata.ThumbnailGenerator.generator_mode', default=ShrinkifyConfig.Metadata.ThumbnailGenerator.generator_mode)
    return parser

def playlist_parser(parser: argparse.ArgumentParser):
    parser.add_argument('--skeleton-dir', type=pathlib.Path, help="location of json playlist files. Leave unchanged if unsure", default=ShrinkifyConfig.Playlist.playlist_skeletion_dir)
    parser.add_argument('--current', '-c', dest='Playlist.current', action="store_true", help="use current song based on mpris (linux-only, overrides specified songs)", default=ShrinkifyConfig.Playlist.current)
    parser.add_argument('Playlist.mode', choices=['add', 'a', 'remove', 'r', 'exclude', 'e', 'unexclude', 'u', 'list', 'l', 'new', 'n'], metavar="mode")
    parser.add_argument('Playlist.selected_playlist', nargs='?', default=None, metavar="[selected playlist]")
    parser.add_argument('Playlist.selected_songs', nargs='*', default=[], metavar="[selected songs]")
    return parser

def tag_parser(parser: argparse.ArgumentParser):
    parser.add_argument('-m', '--mode', dest='Runtime.mode', default='a', choices=['a', 'r'])
    parser.add_argument('Runtime.target', type=lambda p: pathlib.Path(p).expanduser() if p != "CURRENT" else shrinkify_tag.enums.AUTOMATIC)
    parser.add_argument('Runtime.tags', nargs='*', default=[], metavar="[tags]")
    return parser

def only_shrink():
    ap = argparse.ArgumentParser("shrinkify")
    shrink_parser(ap)
    ap.parse_args(namespace=ShrinkifyConfig)
    logging.basicConfig(level=50-(ShrinkifyConfig.verbosity*10))
    logging.debug(f'Pre-Config File Configuration values: {vars(ShrinkifyConfig)}')
    ShrinkifyConfig.load_yaml()
    shrink()
    # shrinkify_playlist.PlaylistGenerator().create_playlists()

def only_playlist():
    ap = argparse.ArgumentParser("listify")
    playlist_parser(ap)
    ap.parse_args(namespace=ShrinkifyConfig)
    logging.basicConfig(level=50-(ShrinkifyConfig.verbosity*10))
    logging.debug(f'Pre-Config File Configuration values: {vars(ShrinkifyConfig)}')
    ShrinkifyConfig.load_yaml()
    logging.debug(f'Post-Config File Configuration values: {vars(ShrinkifyConfig)}')
    #hand control over to the playlist
    playlist()
    # shrinkify_playlist.PlaylistGenerator().create_playlists()

def only_tag():
    ap = argparse.ArgumentParser("tagify")
    tag_parser(ap)
    ap.parse_args(namespace=ShrinkifyConfig)
    logging.basicConfig(level=50-(ShrinkifyConfig.verbosity*10))
    logging.debug(f'Pre-Config File Configuration values: {vars(ShrinkifyConfig)}')
    ShrinkifyConfig.load_yaml()
    logging.debug(f'Post-Config File Configuration values: {vars(ShrinkifyConfig)}')
    tag()

def shrink():
    shrinkify = Shrinkify()
    if ShrinkifyConfig.Shrinkify.single_file:
        shrinkify.single_convert(ShrinkifyConfig.Shrinkify.single_file)
    else:
        shrinkify.recursive_convert()
    if ShrinkifyConfig.Shrinkify.flag_delete_nonexisting:
        shrinkify.recursive_delete()

def playlist():
    plm = playlist.PlaylistModifier()
    if ShrinkifyConfig.Playlist.mode in ('l', 'list'):
        plm.list(ShrinkifyConfig.Playlist.selected_playlist)
    elif ShrinkifyConfig.Playlist.mode in ('n', 'new'):
        if ShrinkifyConfig.Playlist.selected_playlist is None:
            raise RuntimeError("Must specify a playlist name to create")
        plm.new_playlist(ShrinkifyConfig.Playlist.selected_playlist)
    else:
        if ShrinkifyConfig.Playlist.selected_playlist is None:
            raise RuntimeError("Must specify a playlist to modify")
        elif len(ShrinkifyConfig.Playlist.selected_songs) <= 0 and ShrinkifyConfig.Playlist.current is False:
            raise RuntimeError("Must specify a song to modify playlist with")
        plm.modify()
    playlist.PlaylistGenerator().create_playlists()

def tag():
    #TODO: make this not suck
    tag = shrinkify_tag.Tagify()
    if ShrinkifyConfig.Runtime.mode == 'a':
        tag.add_tags(ShrinkifyConfig.Runtime.target, ShrinkifyConfig.Runtime.tags)
    elif ShrinkifyConfig.Runtime.mode == 'r':
        tag.remove_tags(ShrinkifyConfig.Runtime.target, ShrinkifyConfig.Runtime.tags)
    tag.generate_all()
    # shrinkify_playlist.PlaylistGenerator().create_playlists()
    
def main():
    ap = argparse.ArgumentParser("Shrinkify.py")
    subparsers = ap.add_subparsers(required=True)

    shrinkify_args = subparsers.add_parser('shrink', aliases=['s'])
    shrinkify_args.set_defaults(cmd='shrink')
    shrink_parser(shrinkify_args)

    playlist_args = subparsers.add_parser('playlist', aliases=['p'])
    playlist_args.set_defaults(cmd='playlist')
    playlist_parser(playlist_args)
    
    tag_args = subparsers.add_parser('tag', aliases=['t'])
    tag_args.set_defaults(cmd='tag')
    tag_parser(tag_args)
    
    ap.parse_args(namespace=ShrinkifyConfig)

    #set log level. Note that logging's minimum is 50 and argparse's is 0, so account for this
    logging.basicConfig(level=50-(ShrinkifyConfig.verbosity*10))

    logging.debug(f'Pre-Config File Configuration values: {vars(ShrinkifyConfig)}')
    #load config
    ShrinkifyConfig.load_yaml()

    logging.debug(f'Configuration values: {vars(ShrinkifyConfig)}')
    if ShrinkifyConfig.cmd == 'shrink':
        shrink()
            
    elif ShrinkifyConfig.cmd == 'playlist':
        playlist()
    
    elif ShrinkifyConfig.cmd == 'tag':
        tag()

    #playlist generator
    # # shrinkify_playlist.PlaylistGenerator().create_playlists()
