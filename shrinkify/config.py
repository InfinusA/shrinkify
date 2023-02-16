from dataclasses import dataclass, field
import logging
import pathlib
import os
class ConfigGroup:
    def __setattr__(self, name, value):
        if '.' in name:
            group,name = name.split('.',1)
            ns = getattr(self, group, ConfigGroup())
            setattr(ns, name, value)
            self.__dict__[group] = ns
        else:
            self.__dict__[name] = value

@dataclass
class General(ConfigGroup):
    root: os.PathLike | str = pathlib.Path("~/Music").expanduser()
    output: os.PathLike | str = pathlib.Path("~/Music/compressed").expanduser()
    cache_dir: os.PathLike | str = pathlib.Path("~/.cache/shrinkify").expanduser()
    cache_file: os.PathLike | str = pathlib.Path("~/.cache/shrinkify/cache.sqlite").expanduser()
    input_types: tuple[str, ...] = ('.mp3', '.mp4', '.mkv', '.webm', '.m4a', '.aac', '.wav', '.ogg', '.opus', '.flac')
    output_type: str = '.m4a'
    exclude_filter: tuple[str, ...] = ('compressed',)
    
@dataclass
class Conversion(ConfigGroup):
    throttle: int = 0
    thumbnail_format: str = '.png'
    pre_args: list[str] = field(default_factory=lambda: ['ffmpeg', '-y'])
    mid_args: list[str] = field(default_factory=lambda: ['-map', '0:a:0', '-map', '1', '-c:v', 'copy', '-disposition:v:0', 'attached_pic'])

@dataclass
class FileMetadata(ConfigGroup):
    ffprobe_command: tuple[str, ...] = ('ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams')
    ffthumb_pre_command: tuple[str, ...] = ('ffmpeg', '-i')
    ffthumb_post_command: tuple[str, ...] = ('-an', '-map', '0:v:0', '-vframes', '1', '-c:v', 'png', '-f', 'image2pipe', '-')
    thumbnail_types: tuple[str, ...] = ('jpg', 'jpeg', 'png')

@dataclass
class YoutubeMetadata(ConfigGroup):
    filename_regex: tuple[str, ...] = (r"-([a-zA-Z0-9\-_]{11})\.", r"\[([a-zA-Z0-9\-_]{11})\].")
    album_format: str = "{channelTitle} (YouTube)"
    api_key: str | None = None

@dataclass
class YoutubeMusicMetadata(ConfigGroup):
    filename_regex: tuple[str, ...] = (r"-([a-zA-Z0-9\-_]{11})\.", r"\[([a-zA-Z0-9\-_]{11})\].")

@dataclass
class AcoustIDMetadata(ConfigGroup):
    api_key: str | None = None
    allow_missing_image: bool = False
    score_threshold: float = 0.6
    special_exclude: tuple[str, ...] = tuple()
    musicbrainz_agent: str = "Shrinkify/0.1.0 ( aipacifico24@gmail.com )"

@dataclass
class Metadata(ConfigGroup):
    youtubemusic: YoutubeMusicMetadata = YoutubeMusicMetadata()
    youtube: YoutubeMetadata = YoutubeMetadata()
    file: FileMetadata = FileMetadata()
    acoustid: AcoustIDMetadata = AcoustIDMetadata()

@dataclass
class Config(ConfigGroup):
    general: General = General()
    conversion: Conversion = Conversion()
    metadata: Metadata = Metadata()

def generate_default():
    conf = Config()
    return conf

def load_dict(data: dict, conf: ConfigGroup):
    for key in data.keys():
        if not isinstance(key, str) or not hasattr(conf, key):
            logging.warning(f"Invalid key: {key}")
            continue
        if isinstance(data[key], dict):
            load_dict(data[key], getattr(conf, key))
        else:
            setattr(conf, key, data[key])