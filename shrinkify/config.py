#!/usr/bin/env python3
import logging
import pathlib
import yaml
import os

class NestedNamespace(object):
    """Namespace with special __setattr__ function
    """
    def __setattr__(self, name, value):
        if '.' in name:
            group,name = name.split('.',1)
            ns = getattr(self, group, NestedNamespace())
            setattr(ns, name, value)
            self.__dict__[group] = ns
        else:
            self.__dict__[name] = value

class _ShrinkifyConfig(NestedNamespace):
    '''big namespace for config options'''
    #global entries
    def __init__(self):
        #cache path
        self.cache = pathlib.Path(pathlib.Path.home(), '.cache/shrinkify')
        #directory that holds configuratian
        self.config_dir = pathlib.Path(pathlib.Path.home(), '.config/shrinkify')
        #simulate conversion
        self.flag_simulate = False
        #folder that is parsed and converted
        self.source_folder = pathlib.Path(pathlib.Path.home(), 'Music')
        #folder to output converted files
        self.output_folder = pathlib.Path(pathlib.Path.home(), 'Music/compressed')
        #debug mode (kinda useless)
        self.flag_debug = False
        #verbosity on a scale of 0 to 5
        self.verbosity = logging.WARNING//10
        #folders to exclude from conversion
        self.exclude = ('compressed',)
        #list of filetypes to convert
        self.filetypes = ('.mp3', '.mp4', '.mkv', '.webm', '.m4a', '.aac', '.wav', '.ogg', '.opus', '.flac')
        #subconfigs
        self.Shrinkify = self._Shrinkify()
        self.Metadata = self._Metadata()
        self.Playlist = self._Playlist()
    
    def load_dict(self, d: dict, namespace=None):
        """Load dictionary as config

        Args:
            d (dict): dictionary to load
            namespace (object, optional): namespace to load config into. Defaults to None.
        """
        if namespace is None:
            namespace = self
        for key, item in d.items():
            logging.debug(f"Loading config entry {key}")
            if isinstance(item, dict):
                logging.debug(f"Item {key} is dict, recursing")
                try:
                    self.load_dict(item, namespace=getattr(namespace, key))
                except AttributeError as e:
                    logging.warning(f"Error when loading config - {type(e).__name__}: {e}")
            elif isinstance(item, str):
                #test for path, and convert to path automatically
                if isinstance(getattr(namespace, key), pathlib.Path):
                    setattr(namespace, key, pathlib.Path(item))
                else:
                    setattr(namespace, key, item)
            else:
                setattr(namespace, key, item)
    
    def load_yaml(self, filename=pathlib.Path(pathlib.Path.home(), '.config/shrinkify/config.yaml')):
        """Load yaml config file

        Args:
            filename (os.PathLike, optional): File to load. Defaults to pathlib.Path(pathlib.Path.home(), '.config/shrinkify/config.yaml').
        """
        filename = pathlib.Path(filename)
        if filename.exists():
            logging.info("Config file exists, attempting to load")
            temp_conf = yaml.load(filename.read_text(), Loader=yaml.Loader)
            self.load_dict(temp_conf)
        else:
            logging.info("Config file doesn't exist")
    
    class _Shrinkify(NestedNamespace):
        def __init__(self):
            self.continue_from = None
            self.single_file = None
            self.throttle_length = 0
            self.flag_delete_nonexisting = False
            self.flag_update_metadata = False
            self.flag_overwrite = False
    
    class _Metadata(NestedNamespace):
        def __init__(self):
            # self.enabled_parsers = ['youtube', 'youtube music', 'file']
            self.youtube_comments = False
            self.ThumbnailGenerator = self._ThumbnailGenerator()
            self.YoutubeMetadata = self._YoutubeMetadata()
            self.YoutubeMusicMetadata = self._YoutubeMusicMetadata()
            
        class _ThumbnailGenerator(NestedNamespace):
            def __init__(self):
                self.enabled = True
                self.font = 'segoeui'
                self.font_size = 100
                self.base_image = pathlib.Path(pathlib.Path.home(), '.config/shrinkify/no-image.png')
                self.generator_mode = 0 #blur background/center crop
        class _YoutubeMetadata(NestedNamespace):
            def __init__(self):
                self.enabled = True
                self.api_key = ''
        class _YoutubeMusicMetadata(NestedNamespace):
            def __init__(self):
                self.method = 1
                self.search_query = "{title} - {artist}"
                self.enabled = True
                self.name_match = True
                self.override_enabled = True
                self.override_artist = []
                self.override_song = []
    
    class _Playlist(NestedNamespace):
        def __init__(self):
            self.mode = None
            self.selected_playlist = None
            self.selected_songs = []
            # self.root = pathlib.Path(pathlib.Path.home(), 'Music/compressed')
            self.exclude = ('not-music', 'origin', 'mirai-rips', 'cache', 'spotify-stonks')
            self.playlist_skeletion_dir = pathlib.Path(pathlib.Path.home(), '.config/shrinkify/')
            self.escape_codes = True
            self.current = False
        
ShrinkifyConfig = _ShrinkifyConfig()
#global instance
        
def main():
    import pprint
    sc = ShrinkifyConfig
    pprint.pprint(vars(sc))
    pprint.pprint(dir(sc))
    
if __name__ == '__main__':
    main()