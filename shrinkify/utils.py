import logging
import pathlib
import difflib
from .config import ShrinkifyConfig

def is_valid(file: pathlib.Path, exclude_output=True, overwrite=False) -> bool:
    '''Check if file is valid for conversion'''
    initial = file.is_file() and \
        file.suffix in ShrinkifyConfig.filetypes and \
        (ShrinkifyConfig.Shrinkify.flag_overwrite or ShrinkifyConfig.Shrinkify.update_metadata or ShrinkifyConfig.Runtime.single_file or not resolve_shrunk(file).is_file())
    
    if exclude_output:
        exclude = ShrinkifyConfig.exclude + [ShrinkifyConfig.output_folder.name]
    else:
        exclude = ShrinkifyConfig.exclude
    output = initial and not bool(set(exclude).intersection(file.parts))
    return output

def resolve_shrunk(input: pathlib.Path):
    output = pathlib.Path(ShrinkifyConfig.output_folder, input.relative_to(ShrinkifyConfig.source_folder).with_suffix('.m4a'))
    return output

def _similarity_match(str1, str2):
    ratio = difflib.SequenceMatcher(None, str1, str2).ratio()
    logging.info(f"Diff of {str1} and {str2}: {ratio}")
    return ratio > ShrinkifyConfig.Metadata.YoutubeMusicMetadata.similarity_threshold

def match_ytm_methods(name_match=False):
    methods = []
    if name_match:
        methods.append(lambda base, comp: base == comp)
    if ShrinkifyConfig.Metadata.YoutubeMusicMetadata.similarity_match:
        methods.append(_similarity_match)
    if ShrinkifyConfig.Metadata.YoutubeMusicMetadata.substring_match:
        methods.append(lambda base, comp: comp.upper() in base.upper() or base.upper() in comp.upper())
    return methods