from dataclasses import dataclass, field
import json
import logging
import pathlib
import os
from types import EllipsisType
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
    root: os.PathLike | str = pathlib.Path("~/Music/").expanduser()
    output: os.PathLike | str = pathlib.Path("~/Music/compressed/").expanduser()
    cache_dir: os.PathLike | str = pathlib.Path("~/.cache/shrinkify/").expanduser()
    cache_file: os.PathLike | str = pathlib.Path("~/.cache/shrinkify/cache.sqlite").expanduser()
    use_cache: bool = True
    input_types: tuple[str, ...] = ('.mp3', '.mp4', '.mkv', '.webm', '.m4a', '.aac', '.wav', '.ogg', '.opus', '.flac')
    output_type: str = '.ogg'
    exclude_filter: tuple[str, ...] = ('compressed',)
    loglevel: int = logging.INFO
    
@dataclass
class Conversion(ConfigGroup):
    throttle: int = 0
    thumbnail_format: str = '.png'
    rescale: None | tuple[int, int] = (750, 750)
    conversion_args: list[str | EllipsisType] = field(default_factory=lambda: ['ffmpeg', '-y', '-i', '{INPUT}', '-vn', ..., '{OUTPUT}'])
    pre_args: list[str] = field(default_factory=lambda: ['ffmpeg', '-y'])
    mid_args: list[str] = field(default_factory=lambda: ['-map', '0:a:0', '-map', '1', '-c:v', 'copy', '-disposition:v:0', 'attached_pic'])

@dataclass
class FileMetadata(ConfigGroup):
    ffprobe_command: tuple[str, ...] = ('ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams')
    ffthumb_pre_command: tuple[str, ...] = ('ffmpeg', '-i')
    ffthumb_post_command: tuple[str, ...] = ('-an', '-map', '0:v:0', '-vframes', '1', '-c:v', 'png', '-f', 'image2pipe', '-')
    thumbnail_types: tuple[str, ...] = ('jpg', 'jpeg', 'png')
    default_thumbnail: str | os.PathLike | None = None

@dataclass
class YoutubeMetadata(ConfigGroup):
    filename_regex: tuple[str, ...] = (r"-([a-zA-Z0-9\-_]{11})\.", r"\[([a-zA-Z0-9\-_]{11})\]\.")
    album_format: str = "{channelTitle} (YouTube)"
    api_key: str | None = None
    
@dataclass
class NicoNicoMetadata(ConfigGroup):
    filename_regex: tuple[str, ...] = (r"-(sm\d+)\.", r"\[(sm\d+)\]\.",)
    fetch_command: list[str] = field(default_factory=lambda: ['yt-dlp', '-J', 'https://www.nicovideo.jp/watch/{VIDEO_ID}'])
    album_format: str = "{channelTitle} (Niconico)"

@dataclass
class YoutubeMusicMetadata(ConfigGroup):
    filename_regex: tuple[str, ...] = (r"-([a-zA-Z0-9\-_]{11})\.", r"\[([a-zA-Z0-9\-_]{11})\]\.")
    use_very_inaccurate: bool = False

@dataclass
class AcoustIDMetadata(ConfigGroup):
    api_key: str | None = None
    allow_missing_image: bool = False
    score_threshold: float = 0.6
    special_exclude: tuple[str, ...] = tuple()
    musicbrainz_agent: str = "Shrinkify/0.1.0 ( aipacifico24@gmail.com )"

@dataclass
class Reorganize(ConfigGroup):
    retry_delay: float = .5
    retry_count: int = 5

@dataclass
class Metadata(ConfigGroup):
    identifiers: tuple[str, ...] = ("YoutubeMusic", "AcoustID", "NicoNico", "Youtube", "File")
    youtubemusic: YoutubeMusicMetadata = field(default_factory=YoutubeMusicMetadata)
    youtube: YoutubeMetadata = field(default_factory=YoutubeMetadata)
    file: FileMetadata = field(default_factory=FileMetadata)
    acoustid: AcoustIDMetadata = field(default_factory=AcoustIDMetadata)
    niconico: NicoNicoMetadata = field(default_factory=NicoNicoMetadata)

@dataclass
class Tests(ConfigGroup):
    testdir: str | os.PathLike = pathlib.Path("./testfiles/").expanduser()

@dataclass
class Cleanup(ConfigGroup):
    delete: bool = False

@dataclass
class Sort(ConfigGroup):
    sort_dir: os.PathLike | str = "DEFAULT"

@dataclass
class Utils(ConfigGroup):
    reorganize: Reorganize = field(default_factory=Reorganize)
    cleanup: Cleanup = field(default_factory=Cleanup)
    sort: Sort = field(default_factory=Sort)

@dataclass
class Config(ConfigGroup):
    cfgdir: str | os.PathLike = pathlib.Path("~/.config/shrinkify/").expanduser()
    general: General = field(default_factory=General)
    conversion: Conversion = field(default_factory=Conversion)
    metadata: Metadata = field(default_factory=Metadata)
    tests: Tests = field(default_factory=Tests)
    utils: Utils = field(default_factory=Utils)


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

def load_config_files():
    cfg = generate_default()
    cfgfile = pathlib.Path(cfg.cfgdir, "config.json")
    cfgdir = pathlib.Path(cfg.cfgdir)
    if cfgfile.is_file():
        load_dict(json.loads(cfgfile.read_text()), cfg)
        if cfgdir != pathlib.Path(cfg.cfgdir):
            #load a new config
            #note that the new config will not note a new cfgdir
            load_dict(json.loads(cfgfile.read_text()), cfg)
    logging.getLogger().setLevel(cfg.general.loglevel)
    logging.debug(f"Post-config file configuration: {cfg}")
    return cfg