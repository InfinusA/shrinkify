#!/usr/bin/env python3
import subprocess
import pathlib
import json
from ..config import ShrinkifyConfig
from . import shrink_utils

FFPROBE_METADATA = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format']
FFMPEGTHUMBNAILER = ['ffmpegthumbnailer', '-i', None, '-o', '-', '-s0', '-c', 'png', '-m']

class FileMetadata(object):
    def fetch(self, file, no_thumb=False):
        if not isinstance(file, pathlib.Path):
            file = pathlib.Path(file)
        file_metadata_raw = subprocess.check_output(FFPROBE_METADATA+[str(file.resolve())]).decode('utf8')
        file_metadata = json.loads(file_metadata_raw)
        tags = file_metadata['format']['tags'] if 'tags' in file_metadata['format'].keys() else {}
        #remove stuff that's probably not wanted in the output
        #mostly just undisplayed stuff
        self.remove_tag(tags, 'compatible_brands')
        self.remove_tag(tags, 'encoder')
        self.remove_tag(tags, 'encoded_by')
        self.remove_tag(tags, 'major_brand')
        self.remove_tag(tags, 'minor_brand')
        shrinkify_metadata = tags
        if not no_thumb:
            try:
                this_thumbnail_command = FFMPEGTHUMBNAILER
                this_thumbnail_command[2] = str(file.resolve())
                thumbnail_raw = subprocess.check_output(this_thumbnail_command, stderr=subprocess.DEVNULL)
                thumbnail = shrink_utils.data_to_thumbnail(thumbnail_raw)
            except subprocess.CalledProcessError:
                cover_art = pathlib.Path(file.parent, 'cover.png')
                if cover_art.exists():
                    thumbnail = shrink_utils.data_to_thumbnail(cover_art.read_bytes())
                else:
                    if ShrinkifyConfig.Metadata.ThumbnailGenerator.enabled:
                        title = shrinkify_metadata['title'] if 'title' in shrinkify_metadata else file.stem
                        thumbnail = shrink_utils.custom_thumbnail_generator(title, font=ShrinkifyConfig.Metadata.ThumbnailGenerator.font, font_size=ShrinkifyConfig.Metadata.ThumbnailGenerator.font_size, base_image=ShrinkifyConfig.Metadata.ThumbnailGenerator.base_image)
                    else:
                        thumbnail = None
            shrinkify_metadata['_thumbnail_image'] = thumbnail
        if 'title' not in shrinkify_metadata:
            shrinkify_metadata['title'] = file.stem
        if 'artist' not in shrinkify_metadata:
            shrinkify_metadata['artist'] = file.parent.name
        if 'album' not in shrinkify_metadata:
            shrinkify_metadata['album'] = file.parent.name
            
        return shrinkify_metadata

    @staticmethod
    def remove_tag(cdict, tag):
        try:
            del cdict[tag]
        except KeyError:
            pass
        return cdict