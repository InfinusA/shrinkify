from dataclasses import dataclass
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

class Config(ConfigGroup):
    @dataclass
    class GeneralConfig(ConfigGroup):
        root: os.PathLike | str
        output: os.PathLike | str
        cache_dir: os.PathLike | str
        cache_file: os.PathLike | str #sqlite db
        input_types: tuple[str]
        exclude_filter: tuple[str]
        
    @dataclass
    class ConvertConfig(ConfigGroup):
        output_type: str

