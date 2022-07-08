#!/usr/bin/env python3
import logging
import pathlib
import pprint
import shutil
import subprocess
import sys
import time
from io import BytesIO

from . import metadata
from . import playlist
from .config import ShrinkifyConfig


class Namespace(object):
    def __init__(self, **kwargs):
        self.__dict__.update(**kwargs)
    def update_dict(self, d):
        self.__dict__.update(d)
    def update(self, **kwargs):
        self.__dict__.update(**kwargs)

class Shrinkify(object):
    def __init__(self):
        self.meta_parser = metadata.MetadataProcessor()
    
    def is_invalid(self, file: pathlib.Path) -> bool:
        return bool(set(ShrinkifyConfig.exclude).intersection(set(file.parts)))#True not in [s in str(file) for s in ShrinkifyConfig.exclude]
    
    def single_convert(self, filename):
        file = pathlib.Path(filename).resolve()
        root = pathlib.Path('.').resolve().expanduser() if ShrinkifyConfig.source_folder is None else pathlib.Path(ShrinkifyConfig.source_folder).resolve()
        # root = root.resolve()
        output_folder = pathlib.Path(root, 'compressed').expanduser().resolve() if ShrinkifyConfig.output_folder is None else pathlib.Path(ShrinkifyConfig.output_folder)
        output_file = pathlib.Path(output_folder, file.relative_to(root).with_suffix('.m4a'))
        
        metadata = self.meta_parser.parse(file, no_cache=True)
        pprint.pprint(metadata)
        
        # if ShrinkifyConfig.flag_simulate:
        #     time.sleep(ShrinkifyConfig.ShrinkifyRuntime.throttle_length)
        #     return
        output_file.parent.mkdir(exist_ok=True, parents=True)
        metadata_list = [f"{k}={v}" for k, v in metadata.items() if not k.startswith("_")]
        if ShrinkifyConfig.flag_simulate:
            return
        if ShrinkifyConfig.ShrinkifyRuntime.flag_update_metadata and output_file.is_file():
            #create temp file since ffmpeg can't overwrite in-place
            tmp_file = pathlib.Path(root, f'tmp_file{output_file.suffix}')
            tmp_file.unlink(missing_ok=True)
            shutil.copyfile(output_file, tmp_file)
            ffmpeg_args = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', 
                '-i', str(tmp_file.resolve()), '-i', '-', 
                '-map', '0:a:0', '-map', '1', '-c:v', 'copy', '-disposition:v:0', 'attached_pic', '-c:a', 'copy']
        else:
            ffmpeg_args = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', 
                '-i', str(file.resolve()), '-i', '-', 
                '-map', '0:a:0', '-map', '1', '-c:v', 'copy', '-disposition:v:0', 'attached_pic', '-c:a', 'aac']
            
        for metadata_val in metadata_list:
            ffmpeg_args.append('-metadata')
            ffmpeg_args.append(metadata_val)
        ffmpeg_args.append(str(output_file))
        if ShrinkifyConfig.flag_debug:
            print("About to run ffmpeg")
            ffmpeg = subprocess.Popen(ffmpeg_args, stdin=subprocess.PIPE)
        else:
            ffmpeg = subprocess.Popen(ffmpeg_args, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        metadata['_thumbnail_image'].save(ffmpeg.stdin, format='png')#write thumbnail to stdin, saving having to write to file
        if ShrinkifyConfig.flag_debug:
            print("Waiting for ffmpeg to finish")
        ffmpeg.communicate()
        if ShrinkifyConfig.ShrinkifyRuntime.flag_update_metadata:
            tmp_file.unlink(missing_ok=False)
            
            
    def recursive_convert(self):
        root = ShrinkifyConfig.source_folder
        output_folder = pathlib.Path(root, 'compressed').expanduser().resolve() if not isinstance(ShrinkifyConfig.output_folder, pathlib.Path) else ShrinkifyConfig.output_folder
        continue_flag = False
        for file in root.rglob("*"):
            output_file = pathlib.Path(output_folder, file.relative_to(root).with_suffix('.m4a'))
            if ShrinkifyConfig.ShrinkifyRuntime.continue_from is not None and not continue_flag: #we are doing a continue and it hasn't been disabled
                if file.name == ShrinkifyConfig.ShrinkifyRuntime.continue_from or str(file) == ShrinkifyConfig.ShrinkifyRuntime.continue_from:
                    continue_flag = True
                else:
                    continue
            if file.is_dir():
                continue
            if (not ShrinkifyConfig.ShrinkifyRuntime.flag_overwrite) and output_file.is_file():
                # print('file exists, skipping')
                continue
            if file.suffix not in ShrinkifyConfig.filetypes:
                # print('filetype invalid, skipping')
                continue
            # if set(ShrinkifyConfig.exclude).intersection(set(file.parts)): #any parts of path in the parts of filename
            if self.is_invalid(file):
                # print('file is in invalid directory, skipping')
                continue
            if 'test_cases' in file.parts and ShrinkifyConfig.flag_debug is False:
                continue
                    
            #continue scripts
            print(f"Converting {file.relative_to(root)}")
            # logging.debug(file)
            
            metadata = self.meta_parser.parse(file)
            thumb_data = BytesIO()
            # metadata['_thumbnail_image'].save(thumb_data, format='png')
            output_file.parent.mkdir(exist_ok=True, parents=True)
            metadata_list = [f"{k}={v}" for k, v in metadata.items() if not k.startswith("_")]
            
            if ShrinkifyConfig.flag_simulate:
                time.sleep(ShrinkifyConfig.ShrinkifyRuntime.throttle_length)
                continue
            
            if ShrinkifyConfig.ShrinkifyRuntime.flag_update_metadata and output_file.is_file():
                #create temp file since ffmpeg can't overwrite in-place
                tmp_file = pathlib.Path(root, f'tmp_file{output_file.suffix}')
                tmp_file.unlink(missing_ok=True)
                shutil.copyfile(output_file, tmp_file)
                ffmpeg_args = ['ffmpeg', '-hide_banner', '-y', 
                    '-i', str(tmp_file.resolve()), '-i', '-', 
                    '-map', '0:a:0', '-map', '1', '-c:v', 'copy', '-disposition:v:0', 'attached_pic', '-c:a', 'copy']
            else:
                ffmpeg_args = ['ffmpeg', '-hide_banner', '-y', 
                    '-i', str(file.resolve()), '-i', '-', 
                    '-map', '0:a:0', '-map', '1', '-c:v', 'copy', '-disposition:v:0', 'attached_pic', '-c:a', 'aac']
                
            for metadata_val in metadata_list:
                ffmpeg_args.append('-metadata')
                ffmpeg_args.append(metadata_val)
            ffmpeg_args.append(str(output_file))
            if ShrinkifyConfig.flag_debug:
                print("About to run ffmpeg")
                ffmpeg = subprocess.Popen(ffmpeg_args, stdin=subprocess.PIPE)
            else:
                logging.info("Beginning conversion")
                ffmpeg = subprocess.Popen(ffmpeg_args, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            metadata['_thumbnail_image'].save(ffmpeg.stdin, format='png')#write thumbnail to stdin, saving having to write to file
            if ShrinkifyConfig.flag_debug:
                print("Waiting for ffmpeg to finish")
            ffmpeg.communicate()
            logging.info("Finished conversion")
            if ShrinkifyConfig.ShrinkifyRuntime.flag_update_metadata:
                tmp_file.unlink(missing_ok=False)
            time.sleep(ShrinkifyConfig.ShrinkifyRuntime.throttle_length)
            # break
        
    def recursive_delete(self):
        #recursively delete any files not in the parent directory
        logging.info('Running recursive delete')
        for file in ShrinkifyConfig.output_folder.rglob("*"):
            if file.suffix != '.m4a': #TODO: output file config
                continue
            relative_file = file.relative_to(ShrinkifyConfig.output_folder)
            parent_folder = pathlib.Path(ShrinkifyConfig.source_folder, relative_file).parent
            if not parent_folder.exists():
                continue #literally can't delete if not exist
            matched_children = [str(cf) for cf in parent_folder.iterdir() if file.stem == cf.stem and cf.suffix in ShrinkifyConfig.filetypes]
            #below line deletes everything if output folder is also excluded
            if len(matched_children) == 0:# or self.is_invalid(file.relative_to(ShrinkifyConfig.output_folder)): #glob for file without filename, since children have different extensions
                if ShrinkifyConfig.flag_simulate:
                    print("Simulating deletion of", file)
                else:
                    print(f"Deleting {str(file)}")
                    file.unlink()
                continue
            
        for folder in tuple(ShrinkifyConfig.output_folder.glob("**")): #will cause errors if generator
            if len(list(folder.iterdir())) == 0:
                if ShrinkifyConfig.flag_simulate:
                    print("Simulating deletion of", folder)
                else:
                    print(f"Deleting empty folder {str(folder)}")
                    folder.rmdir()
                