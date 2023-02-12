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
from . import utils
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
    
    def single_convert(self, filename: pathlib.Path):
        ShrinkifyConfig.cache = None
        ShrinkifyConfig.Shrinkify.flag_overwrite = True
        if ShrinkifyConfig.output_folder in filename.parents: #file is the compressed ver
            basename = filename.stem
            relative_parents = filename.relative_to(ShrinkifyConfig.output_folder).parent
            real_dir = pathlib.Path(ShrinkifyConfig.source_folder, relative_parents)
            try:
                filename = next(real_dir.glob(f"{basename}.*"))
            except StopIteration:
                raise RuntimeError("Parent file not found. Does the source exist?")
        self.recursive_convert(flist=[filename], show_metadata=True)
            
    def recursive_convert(self, flist=None, show_metadata=False):
        root = ShrinkifyConfig.source_folder
        output_folder = pathlib.Path(root, 'compressed').expanduser().resolve() if not isinstance(ShrinkifyConfig.output_folder, pathlib.Path) else ShrinkifyConfig.output_folder
        continue_flag = False
        if flist is None:
            flist = tuple(root.rglob("*"))
        #TODO:filter out nonvalid beforehand
        flist = tuple(filter(lambda x: utils.is_valid(x, exclude_output=True, overwrite=ShrinkifyConfig.Shrinkify.flag_overwrite), flist))
        flist = sorted(flist)
        for file_index, file in enumerate(flist):
            if ShrinkifyConfig.Runtime.continue_from is not None and not continue_flag: #we are doing a continue and it hasn't been disabled
                if file.resolve() == pathlib.Path(ShrinkifyConfig.Runtime.continue_from).expanduser().resolve():
                    continue_flag = True
                else:
                    continue
            output_file = utils.resolve_shrunk(file)
                    
            #continue scripts
            print(f"Converting #{file_index}/{len(flist)} {file.relative_to(root)}")
            # logging.debug(file)
            print("Fetching metadata")
            # while True:
            #     try:
            metadata = self.meta_parser.parse(file)
                #     break
                # except Exception as e:
                #     logging.error(f"Error when fetching metadata: {type(e).__name__}: {e}")
                #     time.sleep(ShrinkifyConfig.Shrinkify.throttle_length)
            if show_metadata:
                print("\nMetadata Info:")
                for opt in metadata.items():
                    if opt[0].startswith("_"):
                        continue
                    print(f"{opt[0]}: {opt[1]}")
                print("")
                    
            output_file.parent.mkdir(exist_ok=True, parents=True)
            metadata_list = [f"{k}={v}" for k, v in metadata.items() if not k.startswith("_")]
            
            if ShrinkifyConfig.simulate:
                time.sleep(ShrinkifyConfig.Shrinkify.throttle_length)
                continue
            
            #create temp file since ffmpeg can't overwrite in-place (and it's safer in most cases)
            #TODO: make me toggleable
            tmp_file = pathlib.Path(output_file.parent, f"shrinkify-tmp{output_file.suffix}")

            ffmpeg_input = output_file if ShrinkifyConfig.Shrinkify.update_metadata and output_file.exists() else file
            ffmpeg_args = ['ffmpeg', '-hide_banner', '-y', 
                '-i', str(ffmpeg_input.resolve()), '-i', '-', 
                '-map', '0:a:0', '-map', '1', '-c:v', 'copy', '-disposition:v:0', 'attached_pic', '-c:a']
            ffmpeg_args.append("copy" if ShrinkifyConfig.Shrinkify.update_metadata and output_file.exists() else "aac")
                
            for metadata_val in metadata_list:
                ffmpeg_args.append('-metadata')
                ffmpeg_args.append(metadata_val)
            ffmpeg_args.append(str(tmp_file.resolve()))
            
            print("Converting File")
            if ShrinkifyConfig.debug:
                print("About to run ffmpeg")
                ffmpeg = subprocess.Popen(ffmpeg_args, stdin=subprocess.PIPE)
            else:
                logging.info("Beginning conversion")
                ffmpeg = subprocess.Popen(ffmpeg_args, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            metadata['_thumbnail_image'].save(ffmpeg.stdin, format='png')#write thumbnail to stdin, saving having to write to file
            if ShrinkifyConfig.debug:
                print("Waiting for ffmpeg to finish")
            ffmpeg.communicate()
            logging.info("Finished conversion")
            try:
                tmp_file.rename(output_file.resolve())
            except FileExistsError:
                output_file.rename("_"+str(output_file.resolve))
                tmp_file.rename(output_file.resolve())
                pathlib.Path("_"+str(output_file.resolve())).unlink(missing_ok=True)
            time.sleep(ShrinkifyConfig.Shrinkify.throttle_length)
            print()
        
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
                if ShrinkifyConfig.simulate:
                    print("Simulating deletion of", file)
                else:
                    print(f"Deleting {str(file)}")
                    file.unlink()
                continue
            
        for folder in tuple(ShrinkifyConfig.output_folder.glob("**")): #will cause errors if generator
            if len(list(folder.iterdir())) == 0:
                if ShrinkifyConfig.simulate:
                    print("Simulating deletion of", folder)
                else:
                    print(f"Deleting empty folder {str(folder)}")
                    folder.rmdir()
                