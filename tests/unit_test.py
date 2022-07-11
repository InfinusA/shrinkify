#!/usr/bin/env python3
import os
import unittest
import pathlib
from shrinkify import metadata
from shrinkify.config import ShrinkifyConfig

class MetadataTester(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ytm = metadata.youtube_music_metadata.YoutubeMusicMetadata()
        self.yt = metadata.youtube_metadata.YoutubeMetadata()
        ShrinkifyConfig.MetadataRuntime.YoutubeMetadata.api_key = os.getenv("YT_API_KEY")
        self.fm = metadata.file_metadata.FileMetadata()
        
    def test_ytm_valid(self):
        res = self.ytm.fetch('-AuQZrUHjhg')
        # print("RES:",res)
        self.assertTrue(res)
    
    def test_ytm_invalid(self):
        res = self.ytm.fetch('_KTwDH_KQ_g')
        # print(res)
        self.assertFalse(res)
    
    def test_ytm_partial(self):
        res = self.ytm.fetch('95t0C0uoqI8')
        # print(res)
        self.assertFalse(res)
    
    def test_ytm_cache_album(self):
        cv = self.ytm.ytm.get_album('MPREb_zbscLyELohH')
        self.assertTrue(cv)
    
    def test_ytm_cache_artist_album(self):
        cv = self.ytm.ytm.get_artist_albums('UCJwGWV914kBlV4dKRn7AEFA', None) #should not raise if pulling from cache anyways
        self.assertTrue(cv)
    
    def test_ytm_cache_artist(self):
        cv = self.ytm.ytm.get_song('dQw4w9WgXcQ')
        self.assertTrue(cv)
        
    def test_ytm_override(self):
        ShrinkifyConfig.MetadataRuntime.YoutubeMusicMetadata.override_artist = [["UCaXRnD344VW4pw9-cqmBEzw", "UC0nHqGCP46JhIUw867xXJ-Q"]]
        cv = self.ytm.ytm.get_artist('UCaXRnD344VW4pw9-cqmBEzw')
        self.assertEqual('UC0nHqGCP46JhIUw867xXJ-Q', cv['channelId'])
        
    def test_yt_valid(self):
        cv = self.yt.fetch('NIv_yYKl9tQ')
        self.assertTrue(cv)
    
    # def test_file_valid(self):
    #     cv = self.fm.fetch('')
    #     self.assertTrue(cv)

if __name__ == '__main__':
    unittest.main()