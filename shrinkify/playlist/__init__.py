#!/usr/bin/env python3
import json
import logging
import pathlib
import re
from urllib.parse import quote
import dbus

from ..config import ShrinkifyConfig
from ..metadata.file_metadata import FileMetadata
# from . import arch, grass, rain

PLAYLIST_TEMPLATE = {
    'title': None,
    'include': [],
    'exclude': []
}

def main():
    plg = PlaylistGenerator#PlaylistGenerator(pathlib.Path('/media/ext1/music/compressed/'), ('.mp3', '.mp4', '.mkv', '.webm', '.m4a', '.aac', '.wav', '.ogg', '.opus', '.flac'), ['not-music', 'origin', 'mirai-rips', 'cache', 'spotify-stonks'])
    plg.create_playlists()

class PlaylistModifier(object):
    def __init__(self):
        pass
    
    def list(self, selected_playlist=None):
        selected_playlist = selected_playlist if selected_playlist else ShrinkifyConfig.PlaylistRuntime.selected_playlist
        if not selected_playlist:
            for playlist_skeletion in pathlib.Path(ShrinkifyConfig.PlaylistRuntime.playlist_skeletion_dir).iterdir():
                if playlist_skeletion.suffix != '.json':
                    continue
                print(f"{str(playlist_skeletion)} - {json.loads(playlist_skeletion.read_text())['title']}")
        else:
            playlist_gen = PlaylistGenerator()
            playlist_file = pathlib.Path(ShrinkifyConfig.PlaylistRuntime.playlist_skeletion_dir, f'{selected_playlist}.json')
            playlist_data = json.loads(playlist_file.read_text())
            for index, line in enumerate(playlist_data['include']):
                if isinstance(line, str):
                    print(f"#{index+1}: {line}")
                else:
                    print(f"#{index+1}: special format")
            for valid_song in playlist_gen.playlist_generic(pos_filter=playlist_data["include"], neg_filter=playlist_data["exclude"]):
                print(f"{str(valid_song)}")
    
    def new_playlist(self, selected_playlist):
        file = pathlib.Path(ShrinkifyConfig.config_dir, f'{selected_playlist}.json')
        current_playlist = PLAYLIST_TEMPLATE.copy()
        current_playlist['title'] = selected_playlist
        file.write_text(json.dumps(current_playlist))
    
    def modify(self, mode=None, selected_playlist=None, selected_songs=None):
        mode = mode if mode else ShrinkifyConfig.PlaylistRuntime.mode
        selected_playlist = selected_playlist if selected_playlist else ShrinkifyConfig.PlaylistRuntime.selected_playlist
        selected_songs = selected_songs if selected_songs else ShrinkifyConfig.PlaylistRuntime.selected_songs
        
        if ShrinkifyConfig.PlaylistRuntime.current:
            bus = dbus.SessionBus()
            #select first player
            for service in bus.list_names():
                if service.startswith("org.mpris.MediaPlayer2."):
                    player = bus.get_object(service, '/org/mpris/MediaPlayer2')
                    try:
                        selected_songs = [str(player.Get('org.mpris.MediaPlayer2.Player', 'Metadata', dbus_interface='org.freedesktop.DBus.Properties')['xesam:title'])]
                        break
                    except:
                        continue
            else:
                if len(selected_songs) == 0:
                    raise RuntimeError("No currently playing mpris song, and no other songs specified")
            
        
        if mode is None:
            raise RuntimeError("No action supplied.")
        
        #TODO: fallback on title inside file if nothing matches
        playlist_file = pathlib.Path(ShrinkifyConfig.PlaylistRuntime.playlist_skeletion_dir, f'{selected_playlist}.json')
        playlist_data = json.loads(playlist_file.read_text())
        if mode in ('a', 'add'):
            playlist_data['include'].extend(selected_songs)
        elif mode in ('r', 'remove'):
            for song in selected_songs:
                playlist_data['include'].remove(song)
        elif mode in ('e', 'exclude'):
            playlist_data['exclude'].extend(selected_songs)
        elif mode in ('u', 'unexclude'):
            for song in selected_songs:
                playlist_data['exclude'].remove(song)
        playlist_file.write_text(json.dumps(playlist_data))
        print(f"Successfully edited {selected_playlist} with songs {selected_songs}")

class PlaylistGenerator(object):
    def __init__(self) -> None:
        self.playlist_root = pathlib.Path(ShrinkifyConfig.output_folder).resolve()
        self.exclude = ShrinkifyConfig.PlaylistRuntime.exclude
        self.filetypes = ShrinkifyConfig.filetypes
        self.metadata = FileMetadata()
    
    def create_playlists(self) -> None:
        #get playlist jsons
        #dunno why config is in yaml but playlist in json but eh whatever
        logging.debug(f"Playlist mode is {'quoted' if ShrinkifyConfig.PlaylistRuntime.escape_codes else 'unquoted'}")
        playlist_list = ShrinkifyConfig.PlaylistRuntime.playlist_skeletion_dir.glob("*.json")
        for playlist in playlist_list:
            logging.debug(f"Parsing json for playlist: {playlist.name}")
            playlist_data = json.loads(playlist.read_text())
            logging.info(f"Formatting playlist {playlist_data['title']}")
            output_file = pathlib.Path(ShrinkifyConfig.output_folder, f'{playlist_data["title"]}.m3u8')
            with output_file.open('w+') as op:
                for song in self.playlist_generic(playlist_data['exclude'], playlist_data['include']):
                    relative_song = song.relative_to(self.playlist_root)
                    output_string = f"{quote(str(relative_song)).replace('%2F', '/')}\n" if ShrinkifyConfig.PlaylistRuntime.escape_codes \
                        else f"{relative_song}\n"# else f"{str(relative_song).replace('#', '%23')}\n"
                        
                    op.write(output_string)
                
    def playlist_generic(self, neg_filter=[], pos_filter=[]) -> pathlib.Path:
        for file in self.playlist_root.rglob("*"):
            # logging.debug(f"Processing file {file.name}")
            if file.is_dir():
                continue
            if self.filetypes is not None and file.suffix not in self.filetypes:
                continue
            if set(self.exclude).intersection(set(file.parts)):
                print("HI", set(self.exclude).intersection(set(file.parts)))
                continue
            if neg_filter and any(((f in file.name) or (f in file.parts) for f in neg_filter)):
                continue
            
            song_metadata = self.metadata.fetch(file) #only parse builtin metadata
            
            if self.match_titles((str(file), song_metadata['title']), pos_filter):
                yield file
                    
            if not pos_filter:
                # logging.debug(f"Added {file.name} to playlist")
                yield file
    
    @staticmethod
    def match_titles(titles, matches):
        for title in titles:
            for match in matches:
                if match in title or re.match(match, title):
                    return True
        else:
            return False
        
    # def playlist_general(self) -> pathlib.Path:
    #     long_songs = (
    #         'VPBqpyub4Kc', #holovibe: bossa nova/jazz
    #         'WFWw821wozI', #holovibe: jazz
    #         'XD1t7JHbge0', #holovibe: lofi
    #         '7afoD1ZBn3I', #holovibe: holo_remix
    #     )
    #     yield from self.playlist_generic(neg_filter=long_songs)
    
    # def playlist_memeless(self) -> pathlib.Path:
    #     #special syntax, can't use generic
    #     for file in self.playlist_root.rglob("*"):
    #         if file.is_dir():
    #             continue
    #         if set(self.exclude).intersection(set(file.parts)):
    #             continue
    #         if self.filetypes is not None and file.suffix not in self.filetypes:
    #             continue
    #         if 'meme' in file.parts:
    #             continue
    #         yield file

    # def playlist_goodbye_sengen(self) -> pathlib.Path:
    #     gbs = ('goodbye sengen', 'goodbye declaration', 'グッバイ宣言')
    #     yield from self.playlist_generic(pos_filter=gbs)
    
    # def playlist_rain(self) -> pathlib.Path:
    #     yield from self.playlist_generic(pos_filter=rain.get_songs())
    
    # def playlist_grass(self) -> pathlib.Path:
    #     yield from self.playlist_generic(pos_filter=grass.get_songs())
        
    # def playlist_arch(self) -> pathlib.Path:
    #     yield from self.playlist_generic(pos_filter=arch.get_songs())

if __name__ == '__main__':
    main()
