#!/usr/bin/python
import enum
import json
import logging
import pathlib
import typing
try:
    import dbus
    DBUS_ENABLED = True
except ImportError:
    DBUS_ENABLED = False
from urllib.parse import quote, unquote

from .. import utils
from ..config import ShrinkifyConfig


class enums(enum.Enum):
    INCLUDE = 0
    EXCLUDE = 1
    
    AUTOMATIC = -1
#TODO: more advanced filtering (INCLUDE if all tags, EXCLUDE if all tags, etc)
class Tagify(object):
    def __init__(self) -> None:
        pass
    
    def batch_tag(self):
        file_list = tuple(filter(lambda *args, **kwargs: utils.is_valid(*args, exclude_output=False, **kwargs), sorted(ShrinkifyConfig.output_folder.rglob("*"))))
        if ShrinkifyConfig.Runtime.continue_from:
            try:
                file_list = file_list[file_list.index(ShrinkifyConfig.Runtime.continue_from):]
            except ValueError:
                contfile = next(e for e in file_list if e.stem == ShrinkifyConfig.Runtime.continue_from.stem)
                file_list = file_list[file_list.index(contfile):]
        for file in file_list:
            print(f"Current File: {file.name}")
            taglist = input("Tags (seperated by commas): ").split(',')
            if taglist in ([], [""]):
                continue
            self.add_tags(file, taglist)
            
    def get_all_tags(self):
        configfile = pathlib.Path(ShrinkifyConfig.config_dir, 'tags.json')
        tagdata = json.loads(configfile.read_text())
        tag_list = tuple(item for sublist in tagdata.values() for item in sublist)
        return sorted(set(tag_list))
    
    def get_song_tags(self, target):
        configfile = pathlib.Path(ShrinkifyConfig.config_dir, 'tags.json')
        tagdata = json.loads(configfile.read_text())
        try:
            selected = tagdata[str(target.relative_to(ShrinkifyConfig.output_folder).with_suffix(''))]
        except KeyError:
            selected = []
        return selected
    
    def list_tags(self, target=pathlib.Path('.')) -> None:
        if target == enums.AUTOMATIC:
            target = self.get_current_song()
        configfile = pathlib.Path(ShrinkifyConfig.config_dir, 'tags.json')
        tagdata = json.loads(configfile.read_text())
        tag_list = tuple(item for sublist in tagdata.values() for item in sublist)
        uniq_tags = set(tag_list)
        print("Tag List:")
        for tag in sorted(uniq_tags):
            print(f"{tag} - {tag_list.count(tag)} songs tagged")
        try:
            selected = tagdata[str(target.relative_to(ShrinkifyConfig.output_folder).with_suffix(''))]
        except (KeyError, ValueError):
            return
        print(f"\nTags in \"{target.name}\": {', '.join(selected)}")
    
    def get_current_song(self) -> pathlib.Path:
        if not DBUS_ENABLED:
            raise RuntimeError("dbus is not enabled. Are you on an mpris-supported system and do you have the dbus module installed?")
        bus = dbus.SessionBus()
        selected_songs = []
        for service in bus.list_names():
            if service.startswith("org.mpris.MediaPlayer2."):
                player = bus.get_object(service, '/org/mpris/MediaPlayer2')
                try:
                    song = str(player.Get('org.mpris.MediaPlayer2.Player', 'Metadata', dbus_interface='org.freedesktop.DBus.Properties')['xesam:url'])
                    if song.startswith("file://"):
                        selected_songs.append(song)
                except:
                    continue
        else:
            if len(selected_songs) == 0:
                raise RuntimeError("No currently playing mpris song, and no other songs specified")
        
        current_song = unquote(selected_songs[0]).replace("file://", "")
        return pathlib.Path(current_song)
    
    def add_tags(self, target: typing.Union[pathlib.Path, int], tags: list) -> None:
        if target == enums.AUTOMATIC:
            target = self.get_current_song()
        #remove path from target, since files with same stem are usually the same thing
        try:
            target = target.relative_to(ShrinkifyConfig.output_folder).with_suffix('')
        except ValueError: #file is in source not output
            try:
                target = target.relative_to(ShrinkifyConfig.source_folder).with_suffix('')
            except ValueError:
                raise RuntimeError("Selected file is not child of the source or output")
        configfile = pathlib.Path(ShrinkifyConfig.config_dir, 'tags.json')
        if not configfile.is_file():
            tagdata = {}
        else:
            tagdata = json.loads(configfile.read_text('utf8'))
        if str(target) in tagdata:
            tagdata[str(target)] += [tag for tag in tags if tag not in tagdata[str(target)]]
        else:
            tagdata[str(target)] = tags
        
        configfile.write_text(json.dumps(tagdata))
    
    def remove_tags(self, target: typing.Union[pathlib.Path, int], tags: list) -> None:
        if target == enums.AUTOMATIC:
            target = self.get_current_song()
        #remove path from target, since files with same stem are usually the same thing
        try:
            target = target.relative_to(ShrinkifyConfig.output_folder).with_suffix('')
        except ValueError: #file is in source not output
            try:
                target = target.relative_to(ShrinkifyConfig.source_folder).with_suffix('')
            except ValueError:
                raise RuntimeError("Selected file is not child of the source or output")
        configfile = pathlib.Path(ShrinkifyConfig.config_dir, 'tags.json')
        try:
            tagdata = json.loads(configfile.read_text('utf8'))
        except FileNotFoundError:
            tagdata = {}
        if str(target) in tagdata:
            existing = set(tagdata[str(target)])
            remove = set(tags)
            tagdata[str(target)] = list(existing.difference(remove))
        else:
            raise RuntimeError("You can't remove tags from a song that isn't in the database")
        
        configfile.write_text(json.dumps(tagdata))
    
    @staticmethod
    def _format_song_string(song: str) -> str:
        return f"{quote(song).replace('%2F', '/')}" if ShrinkifyConfig.Playlist.escape_codes else song
    
    def get_playlists(self):
        listfile = pathlib.Path(ShrinkifyConfig.config_dir, "playlists.json")
        playlists = json.loads(listfile.read_text('utf8'))
        return list(playlists.keys())

    def generate_playlist(self, mode: int, tags: typing.Iterable, output: pathlib.Path) -> None:
        configfile = pathlib.Path(ShrinkifyConfig.config_dir, 'tags.json')
        root = ShrinkifyConfig.output_folder
        try:
            tagdata = json.loads(configfile.read_text('utf8'))
        except FileNotFoundError:
            tagdata = {}
            
        with output.open('w+') as playlist:
            for file in root.rglob("*"):
                if not utils.is_valid(file, exclude_output=False, overwrite=True):
                    continue
                try:
                    songtags = tagdata[str(file.relative_to(ShrinkifyConfig.output_folder).with_suffix(''))]
                except:
                    songtags = []
                songtags.extend(file.relative_to(ShrinkifyConfig.output_folder).parts)
                
                if mode == enums.INCLUDE and set(songtags).intersection(tags):
                    playlist.write(f"{self._format_song_string(str(file.relative_to(ShrinkifyConfig.output_folder)))}\n")
                elif mode == enums.EXCLUDE and not set(songtags).intersection(tags):
                    playlist.write(f"{self._format_song_string(str(file.relative_to(ShrinkifyConfig.output_folder)))}\n")
                
    def generate_all(self) -> None:
        listfile = pathlib.Path(ShrinkifyConfig.config_dir, "playlists.json")
        if not listfile.is_file():
            logging.warning("Playlist file doesn't exist, skipping playlist generation")
        playlists = json.loads(listfile.read_text('utf8'))
        for list_name, args in playlists.items():
            self.generate_playlist(enums[args['mode']], args['tags'], pathlib.Path(ShrinkifyConfig.output_folder, list_name).with_suffix(".m3u8"))
