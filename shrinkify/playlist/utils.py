#!/usr/bin/env python3
import re

class smart_regex(object):
    @staticmethod
    def regex_is_yt():
        return lambda title: re.match(f'.*-[A-Za-z0-9]{{11}}\..*', title)
    
    @staticmethod
    def regex_no_yt(string, case_insensitive=True):
        return lambda title: re.match(f'.*{string}.*-[A-Za-z0-9]{{11}}\..*', title, flags=re.IGNORECASE if case_insensitive else 0)

    @staticmethod
    def regex_full_word(string, case_insensitive=True):
        return lambda title: re.match(f'(?<![A-Za-z0-9]){string}(?!)[A-Za-z0-9]', title, flags=re.IGNORECASE if case_insensitive else 0)
