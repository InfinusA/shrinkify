#!/usr/bin/env python3
import argparse
import pathlib
import logging
from . import Shrinkify
from .config import ShrinkifyConfig
from . import playlist
import pprint
#TODO: global parser options (source/output directories always needed)
def shrink_parser(parser: argparse.ArgumentParser):
    parser.add_argument('--cache',          dest='cache', type=lambda p: pathlib.Path(p).expanduser(), default=str(ShrinkifyConfig.cache))
    parser.add_argument('--simulate',       dest='flag_simulate', action="store_true")
    parser.add_argument('-f', '--overwrite-existing', '--force', dest='ShrinkifyRuntime.flag_overwrite', action='store_true', help="Overwrite existing files")
    parser.add_argument('--update-metadata',dest='ShrinkifyRuntime.flag_update_metadata', action='store_true', help='Update metadata without reconverting')
    parser.add_argument('--debug',          dest='flag_debug', action='store_true')
    parser.add_argument('-v', '--verbose',  dest='verbosity', action='count', default=0)
    parser.add_argument('-d', '--delete',   dest='ShrinkifyRuntime.flag_delete_nonexisting', action='store_true', help="Delete files not part of parent directory. Disabled by default")
    parser.add_argument('--exclude',        dest='exclude_dir', nargs='+', help='list of directories to exclude', default=ShrinkifyConfig.exclude)
    parser.add_argument('--filetypes',      dest='filetypes', nargs='+', help='list of filetypes to convert', default=ShrinkifyConfig.filetypes)
    parser.add_argument('-t', '--throttle', dest='ShrinkifyRuntime.throttle_length', type=lambda x: int(x) if x.isdecimal() and (int(x) >= 0) else parser.error("Minimum throttle time is 0"), default=0)
    parser.add_argument('--continue-from',  dest='ShrinkifyRuntime.continue_from', help="Continue from the file with this filename", type=lambda p: pathlib.Path(p).expanduser())
    parser.add_argument('--single-file',    dest='ShrinkifyRuntime.single_file', type=lambda p: pathlib.Path(p).expanduser(), help="Only convert a single file.")
    parser.add_argument('-s', '--source-folder', dest='source_folder', type=lambda p: pathlib.Path(p).expanduser(), default=ShrinkifyConfig.source_folder)
    parser.add_argument('-o', '--output-folder', dest='output_folder', type=lambda p: pathlib.Path(p).expanduser(), default=ShrinkifyConfig.output_folder)
    
    metadata_args = parser.add_argument_group('Metadata')
    metadata_args.add_argument('--youtube-api-key', dest='MetadataRuntime.YoutubeMetadata.api_key')
    metadata_args.add_argument('--thumbnail-mode', type=int, dest='MetadataRuntime.ThumbnailGenerator.generator_mode', default=ShrinkifyConfig.MetadataRuntime.ThumbnailGenerator.generator_mode)
    return parser

def playlist_parser(parser: argparse.ArgumentParser):
    parser.add_argument('-v', '--verbose',  dest='verbosity', action='count', default=0)
    parser.add_argument('-s', '--source-folder', dest='source_folder', type=lambda p: pathlib.Path(p).expanduser(), default=ShrinkifyConfig.source_folder)
    parser.add_argument('--skeleton-dir', type=pathlib.Path, help="location of json playlist files. Leave unchanged if unsure", default=ShrinkifyConfig.PlaylistRuntime.playlist_skeletion_dir)
    parser.add_argument('--current', '-c', dest='PlaylistRuntime.current', action="store_true", help="use current song based on mpris (linux-only, overrides specified songs)", default=ShrinkifyConfig.PlaylistRuntime.current)
    parser.add_argument('PlaylistRuntime.mode', choices=['add', 'a', 'remove', 'r', 'exclude', 'e', 'unexclude', 'u', 'list', 'l', 'new', 'n'], metavar="mode")
    parser.add_argument('PlaylistRuntime.selected_playlist', nargs='?', default=None, metavar="[selected playlist]")
    parser.add_argument('PlaylistRuntime.selected_songs', nargs='*', default=[], metavar="[selected songs]")
    return parser

def only_shrink():
    ap = argparse.ArgumentParser("shrinkify")
    shrink_parser(ap)
    ap.parse_args(namespace=ShrinkifyConfig)
    logging.basicConfig(level=50-(ShrinkifyConfig.verbosity*10))
    logging.debug(f'Pre-Config File Configuration values: {vars(ShrinkifyConfig)}')
    ShrinkifyConfig.load_yaml()
    ShrinkifyConfig.PlaylistRuntime.root = ShrinkifyConfig.output_folder #TODO: Change references of root to output
    shrinkify = Shrinkify()
    if ShrinkifyConfig.ShrinkifyRuntime.single_file:
        shrinkify.single_convert(ShrinkifyConfig.ShrinkifyRuntime.single_file)
    else:
        shrinkify.recursive_convert()
    if ShrinkifyConfig.ShrinkifyRuntime.flag_delete_nonexisting:
        shrinkify.recursive_delete()
    plg = playlist.PlaylistGenerator()
    plg.create_playlists()

def only_playlist():
    ap = argparse.ArgumentParser("listify")
    playlist_parser(ap)
    ap.parse_args(namespace=ShrinkifyConfig)
    logging.basicConfig(level=50-(ShrinkifyConfig.verbosity*10))
    logging.debug(f'Pre-Config File Configuration values: {vars(ShrinkifyConfig)}')
    logging.debug(f'Pre-Config Playlist Config Values: {vars(ShrinkifyConfig.PlaylistRuntime)}')
    ShrinkifyConfig.load_yaml()
    logging.debug(f'Post-Config File Configuration values: {vars(ShrinkifyConfig)}')
    logging.debug(f'Post-Config Playlist Config Values: {vars(ShrinkifyConfig.PlaylistRuntime)}')
    ShrinkifyConfig.PlaylistRuntime.root = ShrinkifyConfig.output_folder #TODO: Change references of root to output
    #hand control over to the playlist
    plm = playlist.PlaylistModifier()
    if ShrinkifyConfig.PlaylistRuntime.mode in ('l', 'list'):
        plm.list(ShrinkifyConfig.PlaylistRuntime.selected_playlist)
    elif ShrinkifyConfig.PlaylistRuntime.mode in ('n', 'new'):
        if ShrinkifyConfig.PlaylistRuntime.selected_playlist is None:
            raise RuntimeError("Must specify a playlist name to create")
        plm.new_playlist(ShrinkifyConfig.PlaylistRuntime.selected_playlist)
    else:
        if ShrinkifyConfig.PlaylistRuntime.selected_playlist is None:
            raise RuntimeError("Must specify a playlist to modify")
        elif len(ShrinkifyConfig.PlaylistRuntime.selected_songs) <= 0 and ShrinkifyConfig.PlaylistRuntime.current is False:
            raise RuntimeError("Must specify a song to modify playlist with")
        plm.modify()
    plg = playlist.PlaylistGenerator()
    plg.create_playlists()

def main():
    ap = argparse.ArgumentParser("Shrinkify.py")
    subparsers = ap.add_subparsers(required=True)

    shrinkify_args = subparsers.add_parser('shrink', aliases=['s'])
    shrinkify_args.set_defaults(cmd='shrink')
    shrink_parser(shrinkify_args)

    playlist_args = subparsers.add_parser('playlist', aliases=['p'])
    playlist_args.set_defaults(cmd='playlist')
    playlist_parser(playlist_args)
    

    ap.parse_args(namespace=ShrinkifyConfig)

    #set log level. Note that logging's minimum is 50 and argparse's is 0, so account for this
    logging.basicConfig(level=50-(ShrinkifyConfig.verbosity*10))

    logging.debug(f'Pre-Config File Configuration values: {vars(ShrinkifyConfig)}')
    #load config
    ShrinkifyConfig.load_yaml()

    #set special playlist variables
    # ShrinkifyConfig.PlaylistRuntime.root = ShrinkifyConfig.output_folder
    # ShrinkifyConfig.PlaylistRuntime.exclude = [i for i in ShrinkifyConfig.exclude if i != ShrinkifyConfig.PlaylistRuntime.root.name]

    logging.info(f'Configuration values: {vars(ShrinkifyConfig)}')
    if ShrinkifyConfig.cmd == 'shrink':
        shrinkify = Shrinkify()
        if ShrinkifyConfig.ShrinkifyRuntime.single_file:
            shrinkify.single_convert(ShrinkifyConfig.ShrinkifyRuntime.single_file)
        else:
            shrinkify.recursive_convert()
        if ShrinkifyConfig.ShrinkifyRuntime.flag_delete_nonexisting:
            shrinkify.recursive_delete()
            
    elif ShrinkifyConfig.cmd == 'playlist':
        #hand control over to the playlist
        plm = playlist.PlaylistModifier()
        if ShrinkifyConfig.PlaylistRuntime.mode in ('l', 'list'):
            plm.list()
        elif ShrinkifyConfig.PlaylistRuntime.mode in ('n', 'new'):
            if ShrinkifyConfig.PlaylistRuntime.selected_playlist is None:
                raise RuntimeError("Must specify a playlist name to create")
            plm.new_playlist(ShrinkifyConfig.PlaylistRuntime.selected_playlist)
        else:
            if ShrinkifyConfig.PlaylistRuntime.selected_playlist is None:
                raise RuntimeError("Must specify a playlist to modify")
            elif len(ShrinkifyConfig.PlaylistRuntime.selected_songs) <= 0 and ShrinkifyConfig.PlaylistRuntime.current is False:
                raise RuntimeError("Must specify a song to modify playlist with")
            plm.modify()

    #playlist generator
    plg = playlist.PlaylistGenerator()
    plg.create_playlists()
