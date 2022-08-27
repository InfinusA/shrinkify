#!/usr/bin/env python3
from .utils import smart_regex
from ..config import ShrinkifyConfig
import json
import pathlib

def main():
    import pprint
    pprint.pprint(get_songs())
    
def get_songs():
    return [*complex_matches, *json.loads(pathlib.Path(ShrinkifyConfig.Playlist.playlist_skeletion_dir, 'arch.json').read_text())]

complex_matches = [
    lambda title: ((not smart_regex.regex_is_yt()(title)) and '99' in title) or smart_regex.regex_no_yt('99')(title),
    smart_regex.regex_full_word('loser'),
    smart_regex.regex_full_word('king'),
    smart_regex.regex_full_word('ogre'),
    lambda title: '乙女解剖' in title and 'TeddyLoid Alllies Remix'.lower() in title.lower(),
    smart_regex.regex_full_word('faith'),
    smart_regex.regex_full_word('rise'),
    smart_regex.regex_full_word('dye'),
]
if __name__ == '__main__':
    main()