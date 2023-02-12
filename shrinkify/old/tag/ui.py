import pathlib
import tkinter as tk
import tkinter.ttk as ttk

from . import Tagify

from ..config import ShrinkifyConfig
from .. import utils


def exec():
    master = tk.Tk()
    #master.protocol('WM_DELETE_WINDOW', master.destroy)
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
        
        self.tcanvas = tk.Canvas(self.mlist)
        self.tframe = ttk.Frame(self.tcanvas)
        self.tframe_scroll = ttk.Scrollbar(self.mlist, orient='horizontal', command=self.tcanvas.xview)
        self.tframe.bind("<Configure>", lambda _: self.tcanvas.configure(scrollregion=self.tcanvas.bbox("all"), height=self.tframe.winfo_height()))
        self.tcanvas.create_window((0, 0), window=self.tframe, anchor="nw")
        self.tcanvas.configure(xscrollcommand=self.tframe_scroll.set)
        self.tcanvas.grid(row=0, column=0, columnspan=2, sticky='ew')
        self.tframe_scroll.grid(row=1, column=0, columnspan=2, sticky='ew')
        
        self.lbox_scroll = ttk.Scrollbar(self.mlist)
        self.lbox = tk.Listbox(self.mlist, yscrollcommand=self.lbox_scroll.set)
        self.lbox_scroll.config(command=self.lbox.yview)
        self.lbox.grid(column=0, row=2, sticky='nsew')
        self.lbox_scroll.grid(column=1, row=2, sticky='ns')
        self.lbox.bind('<<ListboxSelect>>', self.update_tag)
        self.lbox.activate(0)
        
        self.flist = []
        self.tag_buttons = []
        self.list_list = []
        self.selected_list = tk.IntVar()
        
        self.regen_sidebar()
        self.regen_tag()
        self.regen_list()
        self.update_tag(self.lbox)

    def regen_sidebar(self):
        for oldtag, _ in self.sidebar.pack_slaves():
            oldtag.pack_forget()
            oldtag.destroy()
            
        self.list_list = self.tagify.get_playlists()
        self.list_list.insert(0, None)
        for list_index, list_name in enumerate(self.list_list):
            rb = ttk.Radiobutton(self.sidebar, text=list_name if list_name is not None else "All", variable=self.selected_list, value=list_index, command=self.set_list)
            rb.pack(side="top")
    
    def set_list(self, *args):
        current_tag = self.list_list[self.selected_list.get()]
        self.regen_list(current_tag)
        self.regen_tag()
    
    def regen_tag(self):
        for oldtag, _ in self.tag_buttons:
            oldtag.pack_forget()
            oldtag.destroy()
            
        self.tag_buttons = []
        if self.tagify.get_all_tags():
            for ix, tag in enumerate(self.tagify.get_all_tags()):
                b = ttk.Checkbutton(self.tframe, text=tag, command=lambda ix=ix, tag=tag: self.set_tag(ix, tag))
                b.checked = tk.BooleanVar()
                b.configure(var=b.checked)
                b.pack(side='left')
                self.tag_buttons.append((b, tag))
        else:
            l = ttk.Label(self.tframe, text="There are no tags")
            l.pack()
            self.tag_buttons.append((l, None))

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
            if tag is None: #there are no tags
                continue
            if tag in taglist:
                b.checked.set(1)
            else:
                b.checked.set(0)
    
    def regen_list(self, tag=None):
        if tag is not None:
            self.flist = list(self.tagify.get_playlist_content(tag))
        else:
            self.flist = sorted(filter(lambda f: utils.is_valid(f, exclude_output=False, overwrite=True), ShrinkifyConfig.output_folder.rglob('*')))
        self.lbox.delete(0, 'end')
        for row, value in enumerate(self.flist):
            self.lbox.insert(tk.END, value.relative_to(ShrinkifyConfig.output_folder))
