import logging
import pathlib
import curses
from .. import config

class SortTool(object):
    def __init__(self, conf: config.Config) -> None:
        self.conf = conf
        self.sort_dir = pathlib.Path(self.conf.utils.sort.sort_dir)
        self.reset_lists()

    def reset_lists(self):
        self.sortfiles = tuple(self.sort_dir.rglob("*.*"))
        self.placement_dirs = tuple(e for e in pathlib.Path(self.conf.general.root).rglob("*/") if not set(self.conf.general.exclude_filter).intersection(e.parts))
    
    def filter_placement(self, filterstr: str):
        return tuple(e for e in self.placement_dirs if filterstr in str(e.relative_to(self.conf.general.root)))

    def run(self):
        curses.wrapper(self.main)
    
    def trunc(self, s: str):
        return s[:curses.COLS // 2] + "..." if len(s) > curses.COLS // 2 else s

    def main(self, scr: curses.window):
        scr.keypad(True)
        scr.clear()
        mainpad = curses.newpad(len(self.sortfiles)+curses.LINES, curses.COLS)
        mainpad.keypad(True)
        while True:
            v = self.show_tobesorted(mainpad)
            mainpad.clear()
            if v is None:
                break
            else:
                n = self.sort(v, scr)
                if n is None:
                    continue
                else:
                    logging.info(f"Moving {v} to {pathlib.Path(n, v.name)}")
                    v.rename(pathlib.Path(n, v.name))
                    self.reset_lists()
                    continue
    
    def show_tobesorted(self, scr: curses.window):
        for i, path in enumerate(self.sortfiles):
            pathstr = str(path.relative_to(self.sort_dir))
            scr.addstr(i, 0, self.trunc(pathstr))
        scr.move(0, 0)
        scr.refresh(0, 0, 0, 0, curses.LINES-1, curses.COLS-1)
        scr.move(0, 0)
        pos = 0
        while True:
            k = scr.getch()
            if k == curses.KEY_UP and pos > 0:
                pos -= 1
            elif k == curses.KEY_DOWN and pos < len(self.sortfiles)-1:
                pos += 1
            elif k == ord('\n'):
                return self.sortfiles[pos]
            elif k == 27: #escape
                return None
            scr.move(0, 0)
            scr.refresh(pos, 0, 0, 0, curses.LINES-1, curses.COLS-1)
    
    def sort(self, songpath: pathlib.Path, scr: curses.window):
        scr.clear()
        pathstr = str(songpath.relative_to(self.sort_dir))
        scr.addstr(0, 0, self.trunc(pathstr))

        fullstr = ""
        abspos = 0
        pos = 0
        pathlist = []
        scr.addstr(1, 0, self.trunc("Filter: "+fullstr))
        scr.refresh()
        while True:
            k = scr.getch()
            if k == curses.KEY_BACKSPACE and len(fullstr) > 0:
                fullstr = fullstr[:-1]
            elif k == curses.KEY_DOWN and pos < min((curses.LINES - 5, len(pathlist)-1)):
                pos += 1
            elif k == curses.KEY_DOWN and pos == curses.LINES - 5 and abspos+curses.LINES-4 < len(pathlist):
                abspos += 1
            elif k == curses.KEY_UP and pos > 0:
                pos -= 1
            elif k == curses.KEY_UP and pos == 0 and abspos > 0:
                abspos -= 1
            elif k == ord('\n') and len(pathlist):
                return pathlist[abspos+pos]
            elif k == 27:
                return None
            elif 32 <= k <= 126:
                pos = 0
                abspos = 0
                fullstr += chr(k)

            scr.addstr(1, 0, " "*curses.COLS)
            scr.addstr(1, 0, self.trunc("Filter: "+fullstr))

            pathlist = self.filter_placement(fullstr)
            for i in range(3, curses.LINES-1):
                scr.addstr(i, 0, " "*curses.COLS)

            for i, path in enumerate(pathlist[abspos:abspos+curses.LINES-4]):
                scr.addstr(3+i, 0, " "*curses.COLS)
                scr.addstr(3+i, 2, self.trunc(str(path.relative_to(self.conf.general.root))))
            if len(pathlist):
                scr.addstr(3+pos, 0, ">")
            else:
                scr.addstr(3, 0, "No results")
            scr.move(1, len(self.trunc("Filter: "+fullstr)))
            scr.refresh()
