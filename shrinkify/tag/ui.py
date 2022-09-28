import pathlib
import tkinter as tk
import tkinter.ttk as ttk

from . import Tagify

from ..config import ShrinkifyConfig
from .. import utils


def exec():
    master = tk.Tk()
    u = Shiggy(master)
    master.mainloop()

class Shiggy(object):
    def __init__(self, master):
        self.tagify = Tagify()
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure('test.TFrame', background='red')
        self.root = master
        self.root.grid()
        self.root.columnconfigure(0, weight=1)
        self.root.columnconfigure(1, weight=3)
        self.root.rowconfigure(0, weight=1)

        self.sidebar = ttk.Frame(self.root)
        self.sidebar.grid(column=0, row=0, sticky='nsew')
        
        self.mlist = ttk.Frame(self.root, style='test.TFrame')
        self.mlist.grid(column=1, row=0, sticky='nsew')
        self.mlist.columnconfigure(0, weight=1)
        self.mlist.rowconfigure(2, weight=1)
        
        self.flist = []
        self.tag_buttons = []
        
        self.regen_tag()
        self.regen_list()
        
    def regen_tag(self):
        tcanvas = tk.Canvas(self.mlist)
        tframe = ttk.Frame(tcanvas)
        tframe_scroll = ttk.Scrollbar(self.mlist, orient='horizontal', command=tcanvas.xview)
        tframe.bind("<Configure>", lambda _: tcanvas.configure(scrollregion=tcanvas.bbox("all"), height=tframe.winfo_height()))
        #tcanvas.create_rectangle((0,0,900,900), fill='red')
        tcanvas.create_window((0, 0), window=tframe, anchor="nw")
        self.tag_buttons = []
        for ix, tag in enumerate(self.tagify.get_all_tags()):
            b = ttk.Checkbutton(tframe, text=tag, command=lambda ix=ix, tag=tag: self.set_tag(ix, tag))
            b.checked = tk.BooleanVar()
            b.configure(var=b.checked)
            b.pack(side='left')
            self.tag_buttons.append((b, tag))
        tcanvas.configure(xscrollcommand=tframe_scroll.set)
        
        tcanvas.grid(row=0, column=0, columnspan=2, sticky='ew')
        tframe_scroll.grid(row=1, column=0, columnspan=2, sticky='ew')

    def set_tag(self, ix, tag):
        enabled = bool(self.tag_buttons[ix][0].checked.get())
        try:
            index = int(self.lbox.curselection()[0])
        except IndexError:
            index = 0
        if enabled:
            self.tagify.add_tags(self.flist[index], [tag])
        else:
            try:
                self.tagify.remove_tags(self.flist[index], [tag])
            except RuntimeError:
                pass

    def update_tag(self, ev):
        w = self.lbox
        try:
            index = int(w.curselection()[0])
        except IndexError:
            index = 0
        taglist = self.tagify.get_song_tags(self.flist[index])
        for b, tag in self.tag_buttons:
            if tag in taglist:
                b.checked.set(1)
            else:
                b.checked.set(0)
    
    def regen_list(self, tag=None):
        if tag:
            pass
        else:
            self.flist = sorted(filter(lambda f: utils.is_valid(f, exclude_output=False, overwrite=True), ShrinkifyConfig.output_folder.rglob('*')))
        lbox_scroll = ttk.Scrollbar(self.mlist)
        self.lbox = tk.Listbox(self.mlist, yscrollcommand=lbox_scroll.set)
        
        for row, value in enumerate(self.flist):
            self.lbox.insert(tk.END, value.relative_to(ShrinkifyConfig.output_folder))
        lbox_scroll.config(command=self.lbox.yview)
        self.lbox.grid(column=0, row=2, sticky='nsew')
        lbox_scroll.grid(column=1, row=2, sticky='ns')
        
        self.lbox.bind('<<ListboxSelect>>', self.update_tag)
        self.lbox.activate(0)
        self.update_tag(self.lbox)