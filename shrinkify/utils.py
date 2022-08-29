import pathlib
from .config import ShrinkifyConfig

def is_valid(file: pathlib.Path, exclude_output=True) -> bool:
    '''Check if file is valid for conversion'''
    initial = file.is_dir() or file.suffix not in ShrinkifyConfig.filetypes
    if exclude_output:
        exclude = ShrinkifyConfig.exclude + [ShrinkifyConfig.output_folder.name]
    else:
        exclude = ShrinkifyConfig.exclude
    return not (initial or bool(set(exclude).intersection(set(file.parts))))
