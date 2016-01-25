from Tkinter import *
from tkFileDialog import askopenfilename
from tkMessageBox import showinfo, showerror
from ttk import *

from blures.testers import Tester
from blures.futures import Task, TaskCallback

from blures.tk_avisynth import AvisynthThread
from blures.widgets import ImageViewer
from blures.autodetect import Autodetector


class FrameViewer(Notebook, object):
    class FrameTab(Frame, object):
        def __init__(self, master, id, avisynth):
            super(FrameViewer.FrameTab, self).__init__(master)
            self.id = id
            self.avisynth = avisynth

            _toolbar = Frame(self)

            self._combo_chooser = Combobox(_toolbar, state="readonly")
            self._combo_chooser["values"] = ["original"] + list(Tester.testers.keys())
            self._combo_chooser.bind("<<ComboboxSelected>>", self._cb_set)
            self._combo_chooser.set("original")
            self._combo_chooser.pack(side="left")

            @self.register
            def isint(S):
                if self._combo_chooser.get() == "original":
                    return True

                try:
                    val = int(S)
                except ValueError:
                    return False

                return val > 0

            self._height_val = IntVar()
            self._height_val.trace("w", self.setheight)

            self._height = Entry(_toolbar, state="disabled", validate="key", validatecommand=(isint, "%P"), textvariable=self._height_val)
            self._height.pack(side="left")

            self.image = ImageViewer(self, panner=self.master.panner)

            _toolbar.pack(fill="x", side="top")
            self.image.pack(fill="both", expand=1)

            self.master._update_single_frame(self)
            self._in_update = False

        def set(self, tester, height=None):
            if self._in_update:
                return

            self._in_update = True
            self._combo_chooser.set(tester)
            if height is not None:
                self._height_val.set(height)
            self._in_update = False

            if tester == "original":
                self.master.tab(self.master.index(self), text="original")
                self._height["state"] = "disabled"
            else:
                self.master.tab(self.master.index(self), text="%d@%s" % (int(height), tester))
                self._height["state"] = "enabled"

            self.master._update_single_frame(self)

        def setheight(self, *args):
            if self._combo_chooser.get() == "original":
                return
            self._cb_set()

        def _cb_set(self, event=None):
            type = self._combo_chooser.get()
            if type == "original":
                self.set("original")
            else:
                value = self._height_val.get()
                if not value:
                    self._height_val.set(100)
                    return
                if value % 2 == 1:
                    return
                self.set(type, value)

        def update_frame(self, clip, frame):
            fut = self._update_frame(clip, frame)
            fut.set_lowlevel()

        @Task
        def _update_frame(self, clip, frame):
            if clip is None:
                return

            type = self._combo_chooser.get()
            height = self._height_val.get()
            if type != "original":
                self.image.image = yield self.avisynth.get_tester_frame(clip, type, height, frame)
            else:
                self.image.image = yield self.avisynth.get_frame(clip, frame)

    def __init__(self, master, avisynth):
        super(FrameViewer, self).__init__(master)
        self.frames = {}

        self.panner = ImageViewer._Panner()

        self.avisynth = avisynth
        self.clip = None
        self.frameno = None

        self.insert("end", Frame(self), text="+")
        self.enable_traversal()
        self.bind("<<NotebookTabChanged>>", self._settab)
        self.bind("<Double-Button-1>", self._delete)

    def add_frame(self, tester="original", height=None):
        frame = FrameViewer.FrameTab(self, len(self.frames), self.avisynth)
        if height:
            self.insert(self.index("end")-1, frame, text='"%d"'%frame.id)
        elif tester == "original":
            self.insert(self.index("end")-1, frame, text='"%d"'%frame.id)
        else:
            raise ValueError("Invalid tab")

        frame.set(tester, height)
        self.select(self.index("end")-2)
        self.frames[frame.id] = frame

    def set_clip(self, clip):
        self.clip = clip
        self.frameno = 1
        self._update()

    def set_frameno(self, frameno):
        self.frameno = frameno
        self._update()

    def _update(self):
        for frame in self.frames.values():
            if frame is None:
                continue
            frame.update_frame(self.clip, self.frameno)

    def _update_single_frame(self, frame):
        if self.clip is None:
            return
        frame.update_frame(self.clip, self.frameno)

    def tab_by_index(self, index):
        return self._nametowidget(self.tabs()[index])

    def _delete(self, event):
        tindex = self.index("@%d,%d"%(event.x, event.y))
        if not tindex:
            pass

        if self.tab(tindex)["text"] == "+":
            return

        if self.tab(tindex+1)["text"] == "+":
            if len(self.tabs())>2:
                self.select(tindex-1)

        frame = self.tab_by_index(tindex)
        print(self.index(frame))
        self.forget(tindex)
        self.frames[frame.id].destroy()
        self.frames[frame.id] = None

    def _settab(self, event):
        if self.tab("current")["text"] == "+":
            self.add_frame("original")


class VideoViewer(Frame, object):

    def __init__(self, avisynth, master, video):
        super(VideoViewer, self).__init__(master=master)
        self.avisynth = avisynth
        self.videofile = video
        self.frame_chooser = Scale(self, from_=0, to=1, orient=HORIZONTAL, command=self._update)
        self.frame_chooser.grid(row=1, column=0, sticky="nswe")
        self.frame_chooser._in_drag = False
        self.frame_chooser.bind("<ButtonPress-1>", self._frame_chooser_drag_start)
        self.frame_chooser.bind("<ButtonRelease-1>", self._frame_chooser_drag_end)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.tabs = FrameViewer(self, avisynth)
        self.tabs.add_frame("original")
        self.tabs.grid(row=0, column=0, sticky="nswe")

        self.avisynth.load(self.videofile).add_callback(TaskCallback(self._load_video))

    @Task
    def _load_video(self, future):
        self.clip = yield future
        frames = self.clip.get_video_info().num_frames
        self.frame_chooser.configure(from_=0, to=frames)
        self.frame_chooser.set(0)
        self.tabs.set_clip(self.clip)

    @Task
    def _update(self, arg):
        if self.frame_chooser._in_drag:
            return
        self.tabs.set_frameno(int(float(arg)))

    def open_tab(self, tester, height):
        self.tabs.add_frame(tester, height)

    def _frame_chooser_drag_start(self, event):
        self.frame_chooser._in_drag = True

    def _frame_chooser_drag_end(self, event):
        self.frame_chooser._in_drag = False
        self._update(self.frame_chooser["value"]).set_lowlevel()


class Application(Tk, object):

    menudata = [
        ("File", [
            ("Open Video", ("open_avs", ("Ctrl-O", "<Control-o>"))),
            ("Detect Resolution", ("detect_res", ("F1", "<F1>"))),
            None,
            ("Exit", ("quit", ("Alt-F4", None))),
        ]),
        ("Help", [
            ("About", ("open_about", None)),
        ])
    ]

    bindings = {

    }


    def __init__(self):
        super(Application, self).__init__()

        self.title("Blu-res v0.0.1")
        self.iconbitmap("data/br.ico")
        self.config(menu=self.generate_menu(self, self.menudata))
        self.bind_bindings()
        self.avisynth = AvisynthThread(self)
        self.after(1, self.check_x32)
        self.editor = None
        self.filename = None

    def check_x32(self):
        if sys.maxsize > 2**32:
            showerror("Invalid Python Version", "You need to use a 32-bit python version to run this program.")
            self.destroy()
        print("Running x32")
        self.after(1, self.run_avisynth)

    def run_avisynth(self):
        self.avisynth.start()

    def bind_bindings(self):
        for event, funcs in self.bindings.items():
            for func in funcs:
                self.bind(event, getattr(self, func))

    def generate_menu(self, parent, menu):
        """
        Generates the menu for the gui.

        :param parent:   The parent object.
        :param menu:     The menu.
        :return: A menu.
        """
        result = Menu(parent, tearoff=False)
        for item in menu:
            if item is None:
                result.add_separator()
                continue

            title, data = item
            if isinstance(data, list):
                result.add_cascade(label=title, menu=self.generate_menu(result, data))
            elif isinstance(data, tuple):
                func = getattr(self, data[0])
                if data[1] is not None:
                    result.add_command(label=title, command=func, accelerator=data[1][0])

                    if data[1][1] is not None:
                        self.bind_all(data[1][1], func)
                else:
                    result.add_command(label=title, command=func)
        return result

    def open_avs(self, event=None):
        self.filename = askopenfilename(parent=self, title="Open video file")
        if not self.filename:
            return

        if self.editor is not None:
            self.editor.pack_forget()

        self.editor = VideoViewer(self.avisynth, self, self.filename)
        self.editor.pack(fill=BOTH, expand=1)

    def open_about(self):
        showinfo(title="About", message="Blu-res by stux!\nIdea by Ninelpinel", parent=self)

    def detect_res(self, event=None):
        if self.editor is None:
            return

        Autodetector(self, self.filename, lambda:[int(float(self.editor.frame_chooser.get()))])

    def open_tab(self, tester, height):
        self.editor.open_tab(tester, height)

    def quit(self):
        self.destroy()


if __name__ == "__main__":
    Application().mainloop()