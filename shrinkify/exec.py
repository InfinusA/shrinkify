import argparse
import json
import pathlib
import sys
import logging
from . import Shrinkify
from . import config
from . import songclass
from .utils import sortutil

def main():
    logging.basicConfig(level=0)
    conf = config.load_config_files()
    cle = CommandLineExec(conf)
    cle.determine_parse(sys.argv)

def shrink():
    logging.basicConfig(level=0)
    conf = config.load_config_files()
    cle = CommandLineExec(conf)
    cle.parse_shrink(sys.argv[1:])

class RecursiveNamespace(argparse.Namespace):
    def __setattr__(self, name, value):
        if '.' in name:
            group,name = name.split('.',1)
            ns = getattr(self, group)
            setattr(ns, name, value)
            self.__dict__[group] = ns
        else:
            self.__dict__[name] = value

class CommandLineExec(object):
    def __init__(self, conf: config.Config) -> None:
        self.conf = conf

        # cfgfile = pathlib.Path(self.conf.cfgdir, "config.json")
        # cfgdir = pathlib.Path(self.conf.cfgdir)
        # if cfgfile.is_file():
        #     config.load_dict(json.loads(cfgfile.read_text()), self.conf)
        #     if cfgdir != pathlib.Path(self.conf.cfgdir):
        #         #load a new config
        #         #note that the new config will not note a new cfgdir
        #         config.load_dict(json.loads(cfgfile.read_text()), self.conf)
        #     logging.debug(f"Post-config file configuration: {self.conf}")


    def add_general_opts(self, parser: argparse.ArgumentParser):
        parser.add_argument("-s", "-r", "--root", "--source", dest="c.general.root", type=pathlib.Path, default=self.conf.general.root)
        parser.add_argument("-o", "-d", "--output", "--dest", dest="c.general.output", type=pathlib.Path, default=self.conf.general.output)
        parser.add_argument("--cachedir", dest="c.general.cache_dir", type=pathlib.Path, default=self.conf.general.cache_dir)
        parser.add_argument("--cachefile", dest="c.general.cache_file", type=pathlib.Path, default=self.conf.general.cache_file)
        parser.add_argument("--disable-cache", dest="c.general.use_cache", action='store_false', default=self.conf.general.use_cache)
        parser.add_argument("-i", "--input-types", dest="c.general.input_types", default=self.conf.general.input_types, nargs='*', type=str)
        parser.add_argument("-t", "--output-type", dest="c.general.output_type", default=self.conf.general.output_type, type=str)
        parser.add_argument("-e", "--exclude", dest="c.general.exclude_filter", default=self.conf.general.exclude_filter, nargs='*', type=str)
        parser.add_argument("--verbosity", type=int, dest="c.general.loglevel", default=self.conf.general.loglevel)
        return parser
    
    def add_convert_opts(self, parser: argparse.ArgumentParser):
        parser.add_argument("-w", "--throttle", dest="c.conversion.throttle", default=self.conf.conversion.throttle, type=int)
        parser.add_argument("--thumbnail-format", dest="c.conversion.thumbnail_format", default=self.conf.conversion.thumbnail_format, type=str)
        parser.add_argument("--ffmpeg-pre-args", dest="c.conversion.pre_args", default=self.conf.conversion.pre_args, nargs='*', type=str, help="Do not use unless you know what you are doing")
        parser.add_argument("--ffmpeg-mid-args", dest="c.conversion.mid_args", default=self.conf.conversion.mid_args, nargs='*', type=str, help="Do not use unless you know what you are doing")
        self.add_metadata_opts(parser)
        return parser

    def add_metadata_opts(self, parser: argparse.ArgumentParser):
        parser.add_argument("-y", "--youtube-api-key", dest="c.metadata.youtube.api_key", default=self.conf.metadata.youtube.api_key, type=str)
        return parser

    def add_cleanup_opts(self, parser: argparse.ArgumentParser):
        parser.add_argument("--delete", dest='c.utils.cleanup.delete', help="Delete files instead of listing them", action='store_true')
        return parser
    
    def add_sortutil_opts(self, parser: argparse.ArgumentParser):
        parser.add_argument("c.utils.sort.sort_dir")
        return parser
    

    def parse_shrink(self, argv: list[str]):
        parser = argparse.ArgumentParser()
        self.add_general_opts(parser)
        self.add_convert_opts(parser)
        parser.add_argument('--in-place', dest='in_place', default=False, action='store_true')
        parser.add_argument('--continue-from', dest='continue_from', type=pathlib.Path, default=None)
        parser.add_argument('files', nargs='*', help="Optional: Specific files to convert. If not specified, converts all convertable files in root.")

        parse_namespace = RecursiveNamespace(c=self.conf)
        parse_namespace = parser.parse_args(argv, namespace=parse_namespace)
        logging.getLogger().setLevel(parse_namespace.c.general.loglevel)
        logging.debug(parse_namespace)
        shrink = Shrinkify(self.conf)
        if len(parse_namespace.files) == 0:
            shrink.shrink_directory(self.conf.general.root, update=parse_namespace.in_place, continue_from=parse_namespace.continue_from)
        else:
            for file in parse_namespace.files:
                file = pathlib.Path(file).expanduser()
                if file.is_dir():
                    shrink.shrink_directory(file, update=parse_namespace.in_place, continue_from=parse_namespace.continue_from)
                elif file.is_file():
                    shrink.shrink_file(songclass.Song(file), update=parse_namespace.in_place)
    
    def parse_reorganize(self, argv: list[str]):
        parser = argparse.ArgumentParser()
        self.add_general_opts(parser)
        parse_namespace = RecursiveNamespace(c=self.conf)
        parse_namespace = parser.parse_args(argv, namespace=parse_namespace)
        logging.getLogger().setLevel(parse_namespace.c.general.loglevel)
        logging.debug(parse_namespace)
        shrink = Shrinkify(self.conf)
        shrink.reorganize_util()

    def parse_cleanup(self, argv: list[str]):
        parser = argparse.ArgumentParser()
        self.add_general_opts(parser)
        self.add_cleanup_opts(parser)
        parse_namespace = RecursiveNamespace(c=self.conf)
        parse_namespace = parser.parse_args(argv, namespace=parse_namespace)
        logging.getLogger().setLevel(parse_namespace.c.general.loglevel)
        logging.debug(parse_namespace)
        shrink = Shrinkify(self.conf)
        shrink.cleanup()

    def parse_sort(self, argv: list[str]):
        parser = argparse.ArgumentParser()
        self.add_general_opts(parser)
        self.add_sortutil_opts(parser)
        parse_namespace = RecursiveNamespace(c=self.conf)
        parse_namespace = parser.parse_args(argv, namespace=parse_namespace)
        logging.getLogger().setLevel(parse_namespace.c.general.loglevel)
        nc = sortutil.SortTool(self.conf)
        nc.run()

    def determine_parse(self, argv: list[str]):
        logging.debug(argv)
        if len(argv) < 2 or argv[1] in ("shrink", "s"):
            self.parse_shrink(argv[2:])
        elif argv[1] in ("reorganize", "r"):
            self.parse_reorganize(argv[2:])
        elif argv[1] in ("cleanup", "c"):
            self.parse_cleanup(argv[2:])
        elif argv[1] in ("sort", "o"):
            self.parse_sort(argv[2:])
        else:
            raise RuntimeError(f"Unknown subcommand: {argv[1]}")
