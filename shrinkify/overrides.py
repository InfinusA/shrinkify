import json
import os
import pathlib
import typing
import re
import copy
from PIL import Image
from . import songclass
from . import config

class Namespace(object):
    def __init__(self, v: dict = {}, **kwargs) -> None:
        self.__dict__.update(v)
        self.__dict__.update(**kwargs)

class Checkers(object):
    def get_checker(self, name: str) -> typing.Callable[..., bool]:
        CHK = {
            'equals': self.equals_checker,
            'regex': self.regex_checker,
            'file_exists': self.file_exists_checker
        }
        if name not in CHK:
            raise RuntimeError(f"Invalid checker {name}")
        return CHK[name]
    
    def equals_checker(self, obj1: typing.Any, obj2: typing.Any) -> bool:
        return obj1 == obj2
    def regex_checker(self, obj1: str, re_str: str) -> bool:
        return bool(re.match(re_str, obj1))
    def file_exists_checker(self, *paths: str | os.PathLike) -> bool:
        return pathlib.Path(*paths).exists()

class Executions(object):
    def get_execution(self, name: str) -> typing.Callable[..., Namespace]:
        EXC = {
            "set": self.set,
            "setimage": self.setimage,
        }
        if name not in EXC:
            raise RuntimeError(f"Invalid execution {name}")
        return EXC[name]
    
    @staticmethod
    def _recursive_set(obj, path: str | list, value):
        if isinstance(path, str) and '.' in path:
            return Executions._recursive_set(getattr(obj, path.split('.')[0]), path.split('.')[1:], value)
        elif isinstance(path, str) and '.' not in path:
            setattr(obj, path, value)
        else:
            if len(path) > 1:
                return Executions._recursive_set(getattr(obj, path[0]), path[1:], value)
            else:
                setattr(obj, path[0], value)

    def set(self, namespace: Namespace, key, value) -> Namespace:
        self._recursive_set(namespace, key, value)
        return namespace
    
    def setimage(self, namespace: Namespace, key, *pathcomponents, **kwargs) -> Namespace:
        self._recursive_set(namespace, key, Image.open(pathlib.Path(*pathcomponents)))
        return namespace

class Overrides(object):
    def __init__(self, conf: config.Config) -> None:
        self.conf = conf
        self.checkers = Checkers()
        self.executions = Executions()

    @staticmethod
    def _recursive_access(obj, path: str | list) -> typing.Any:
        if isinstance(path, str) and '.' in path:
            return Overrides._recursive_access(getattr(obj, path.split('.')[0]), path.split('.')[1:])
        elif isinstance(path, str) and '.' not in path:
            return getattr(obj, path)
        else:
            print(type(path), path)
            if len(path) > 1:
                return Overrides._recursive_access(getattr(obj, path[0]), path[1:])
            else:
                return getattr(obj, path[0])

    def find_directives(self, **kwargs):
        main_overrides = pathlib.Path(self.conf.cfgdir, 'overrides.json')
        if main_overrides.exists():
            for override in json.loads(main_overrides.read_text()):
                yield override

        if 'song' in kwargs and pathlib.Path(kwargs['song'].path, 'overrides.json').is_file():
            yield json.loads(pathlib.Path(kwargs['song'].path, 'overrides.json').read_text())
        
        if "custom_directives" in kwargs and kwargs['custom_directives'] != None:
            for directive in kwargs['custom_directives']:
                yield directive

    def basic_override(self, song: songclass.Song) -> songclass.Song:
        #format: key=(+-)value,value
        #check if folders above contain a simple override file
        for folder in reversed(song.path.parents):
            ovf = pathlib.Path(self.conf.general.root, folder, 'overrides')
            if ovf.is_file():
                for line in ovf.read_text().split("\n"):
                    line = line.strip()
                    key, prevalue = line.split("=")
                    if isinstance(song[key], str): #convert key to list
                        song[key] = [song[key]]
                    #check syntax for undefined behavior
                    for entry in prevalue.split(','):
                        if len(entry) == 0:
                            continue
                        if '+' == entry[0] or '-' == entry[0]:
                            for entry in prevalue.split(','):
                                if len(entry) == 0:
                                    continue
                                if entry[0] == '+':
                                    if entry[1:] not in song[key]: #prevent duplicates
                                        song[key].append(entry[1:])
                                elif entry[0] == '-':
                                    try:
                                        song[key].remove(entry[1:])
                                    except ValueError:
                                        pass
                                else:
                                    raise RuntimeError("Undefined behavior in override. Please specify only add and remove OR replacements")
                            break
                    else:
                        song[key] = prevalue.split(',')
        return song

    def override(self, directive: str, custom_directives: typing.Optional[list[dict]] = None, **kwargs) -> dict[str, typing.Any]:
        """Common kwargs arguments: path, song"""
        # ns = Namespace(copy.deepcopy(kwargs))
        for override in self.find_directives(custom_directives=custom_directives, **kwargs):
            if override['directive'] != directive:
                continue
            if eval(override['condition'], globals(), kwargs):
                exec(override['execute'], globals(), kwargs)
            #replace values in the condition and execution
            #for i, value in enumerate(override['condition']):
            #    if not isinstance(value, str):
            #        continue
            #    r = re.match(r"^\{([^{].*[^}])}$", value)
            #    if r:
            #        override['condition'][i] = self._recursive_access(ns, r.group(1))
            #for i, value in enumerate(override['execute']):
            #    if not isinstance(value, str):
            #        continue
            #    r = re.match(r"^\{([^{].*[^}])}$", value)
            #    if r:
            #        override['execute'][i] = self._recursive_access(ns, r.group(1))
            #if self.checkers.get_checker(override['condition'][0])(*override['condition'][1:]):
            #    ns = self.executions.get_execution(override['execute'][0])(ns, *override['execute'][1:])
        return kwargs#ns.__dict__
