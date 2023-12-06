#!/usr/bin/env python3
import os
import unittest
import pathlib
import shrinkify
import shrinkify.overrides

class MetadataTester(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cfg = shrinkify.config.load_config_files()
        
    def test_override(self):
        TSTDR = [
            {
                "directive": "final_metadata",
                "condition": ["file_exists", "{song.path.parent}", "cover.png"],
                "execute": ["setimage", "song.cover_image", "{song.path.parent}", "cover.png"]
            }
        ]
        test_song = shrinkify.songclass.Song(next(pathlib.Path(self.cfg.tests.testdir).iterdir()))
        orig = test_song.cover_image
        ovr = shrinkify.overrides.Overrides(self.cfg)
        ovr.override("final_metadata", song=test_song, custom_directives=TSTDR)
        self.assertNotEqual(orig, test_song.cover_image)


if __name__ == '__main__':
    unittest.main()