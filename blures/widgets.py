from PIL import ImageTk
from Tkinter import Canvas, Frame, Menu


class PopupMenu(Menu, object):
    """
    Defines a popup menu.
    """

    def __init__(self, *args, **kwargs):
        kwargs["tearoff"] = kwargs.get("tearoff", False)
        super(PopupMenu, self).__init__(*args, **kwargs)

    def attach(self):
        self.master.bind("<Button-3>", self.show_menu)

    def show_menu(self, event):
        self.post(event.x_root, event.y_root)


class ImageViewer(Frame, object):

    class _Panner(object):
        def __init__(self):
            self.viewers = []
            self._factor = 1
            self._drags = []
            self._cdrag = None

        def add(self, val):
            self.viewers.append(val)
            for mark, end in self._drags:
                val.canvas.scan_mark(*mark)
                val.canvas.scan_dragto(*end, gain=1)
            if self._cdrag:
                val.canvas.scan_mark(*self._cdrag[0])
                val.canvas.scan_dragto(*self._cdrag[1], gain=1)

        def move_mark(self, x, y):
            if self._cdrag:
                self._drags.append(self._cdrag)

            self._cdrag = [(x, y), (x, y)]

            for viewer in self.viewers:
                viewer.canvas.scan_mark(x, y)

        def move_actual(self, x, y):
            self._cdrag[1] = (x, y)
            for viewer in self.viewers:
                viewer.canvas.scan_dragto(x, y, gain=1)

        def update(self):
            for viewer in self.viewers:
                viewer._update()

    def __init__(self, master, panner=None):
        super(ImageViewer, self).__init__(master)

        self._image = None
        self._view = None
        self._view_id = None

        self.canvas = Canvas(self, background="#000")
        self.canvas.pack(fill='both', expand=1)
        self.canvas.bind("<MouseWheel>", self.zoom)
        self.canvas.bind("<ButtonPress-1>", self.scroll_start)
        self.canvas.bind("<B1-Motion>", self.scroll_move)
        # self.canvas.bind("<Enter>", self.focus_widget)
        # self.canvas.bind("<Leave>", self.unfocus_widget)

        self.popup_menu = PopupMenu(self.canvas)
        for val in (10, 25, 50, 75, 100, 150, 200, 250, 300, 500):
            self.popup_menu.add_command(label="%d%%"%val, command=(lambda v:(lambda :self.set_factor(v/100.)))(val))

        self.popup_menu.attach()

        self._panner = panner
        if panner is None:
            self._panner = ImageViewer._Panner()
        self._panner.add(self)

        self._focus_prev = None

    def destroy(self):
        self._panner.viewers.remove(self)
        super(ImageViewer, self).destroy()

    @property
    def image(self):
        return self._image

    @image.setter
    def image(self, value):
        self._image = value
        self.after(1, self.show)

    @property
    def factor(self):
        return self._panner._factor

    @factor.setter
    def factor(self, value):
        self._panner._factor = value
        self.after(1, self.show)

    def set_factor(self, value):
        self.factor = value

    def zoom(self, event):
        if event.delta < 0:
            if self.factor == .1:
                return
            self.factor -= .1
        elif event.delta > 0:
            if self.factor == 5:
                return
            self.factor += .1
        self.show()

    def scroll_start(self, event):
        self._panner.move_mark(event.x, event.y)

    def scroll_move(self, event):
        self._panner.move_actual(event.x, event.y)

    def focus_widget(self, event):
        self._focus_prev = self.canvas.focus_get()
        self.focus_set()

    def unfocus_widget(self, event):
        self._focus_prev.focus_set()

    def show(self):
        self._panner.update()

    def _update(self):
        if self._image is None:
            return

        if self._view_id is not None:
            self.canvas.delete(self._view_id)

        x, y = self.image.size
        x, y = int(round(x*self.factor)), int(round(y*self.factor))

        self._view = ImageTk.PhotoImage(self.image.resize((x, y)))

        self._view_id = self.canvas.create_image(0, 0, image=self._view, anchor="nw")
        self.canvas.configure(scrollregsion=self.canvas.bbox("ALL"))
