import multiprocessing

from Tkinter import *
from ttk import *
from tkMessageBox import showerror

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2TkAgg
import matplotlib.animation as animation

from blures.worker import Executor
from blures.testers import Tester
from blures.widgets import ImageViewer


def detect(heights, results, thresh):
    import numpy as np
    def is_outlier(points):
        """
        Returns a boolean array with True if points are outliers and False
        otherwise.

        Parameters:
        -----------
            points : An numobservations by numdimensions array of observations
            thresh : The modified z-score to use as a threshold. Observations with
                a modified z-score (based on the median absolute deviation) greater
                than this value will be classified as outliers.

        Returns:
        --------
            mask : A numobservations-length boolean array.

        References:
        ----------
            Boris Iglewicz and David Hoaglin (1993), "Volume 16: How to Detect and
            Handle Outliers", The ASQC Basic References in Quality Control:
            Statistical Techniques, Edward F. Mykytka, Ph.D., Editor.
        """
        if len(points.shape) == 1:
            points = points[:,None]
        median = np.median(points, axis=0)
        diff = np.sum((points - median)**2, axis=-1)
        diff = np.sqrt(diff)
        med_abs_deviation = np.median(diff)

        modified_z_score = 0.6745 * diff / med_abs_deviation

        return modified_z_score > thresh

    results = np.array(results)
    mask = is_outlier(results)
    outliers = np.array([results, np.arange(len(results), dtype=np.uint16)]).T[mask]
    ibefore = None
    for val, i in outliers:
        if ibefore is None:
            ibefore = (i, val)
            continue

        if i - ibefore[0] > 1:
            ibefore = (i, val)
            continue

        if ibefore[1] < 0:
            ibefore = (i, val)
            continue

        yield heights[int(ibefore[0])]

        ibefore = (i, val)


class Autodetector(Toplevel, object):

    def __init__(self, master, filename, framecb):
        super(Autodetector, self).__init__(master)
        self.filename = filename
        self.framecb = framecb

        self.title("Resolution Autodetector")
        self.iconbitmap("data/br.ico")

        self.executor = None

        _data = Frame(self)
        _settings = Frame(_data)
        try:
            cCpu = multiprocessing.cpu_count()
        except NotImplementedError:
            cCpu = 1

        Label(_settings, text="Processes").grid(row=0, column=0)
        self.cpu_count = cCpu
        if cCpu > 1:
            self.cpu_sel = Combobox(_settings, state="readonly")
            self.cpu_sel["values"] = tuple(str(i+1) for i in range(cCpu))
            self.cpu_sel.set(self.cpu_count)
            self.cpu_sel.grid(row=0, column=1)
        else:
            self.cpu_sel = IntVar(value=1)
            Label(_settings, text="1").grid(row=0, column=0, sticky="nesw")

        Label(_settings, text="Aspect Ratio").grid(row=1, column=0)
        self.ar = StringVar(value="16:9")
        Entry(_settings, textvariable=self.ar).grid(row=1, column=1, sticky="nesw")

        self.from_ = IntVar(value="400")
        self.to = IntVar(value="1080")
        Label(_settings, text="From").grid(row=2, column=0)
        Label(_settings, text="To").grid(row=3, column=0)
        Entry(_settings, textvariable=self.from_).grid(row=2, column=1, sticky="news")
        Entry(_settings, textvariable=self.to).grid(row=3, column=1, sticky="news")

        self.proc = Button(_settings, text="Detect", command=self.start_detect)
        self.proc.grid(row=4, column=0, columnspan=2)

        self.progress = Progressbar(_settings)
        self.progress.grid(row=5, column=0, columnspan=2, sticky="news")

        _settings.grid_columnconfigure(1, weight=1)
        _settings.pack(side="top", padx=5, pady=5, fill="y")

        _vals = Frame(_data)
        self.values = Listbox(_data, selectmode='multiple')
        _sel = Frame(_vals)
        _sel.pack(side="top", fill="x")

        self.values.pack(fill="both", expand=1)

        self.thresh = StringVar()
        Entry(_sel, textvariable=self.thresh).pack(side="left")
        Button(_sel, text="Find", command=self.find).pack(side="left")
        Button(_sel, text="Open", command=self.open).pack(side="right")

        _vals.pack(side="bottom", fill="x")

        _data.pack(side="left", fill="y")

        nb = Notebook(self)
        nb.pack(fill="both", expand=1)
        self.viewer = ImageViewer(nb)

        fig = Frame(nb)
        self.figure = Figure()
        self.derivative_data = self.figure.add_subplot(211)
        self.normal_data = self.figure.add_subplot(212)
        self.reset_plots()
        self.figure.suptitle("Similarity...", fontsize=20)
        self.figure.subplots_adjust(hspace=.5)

        self.stats = FigureCanvasTkAgg(self.figure, fig)
        nav = NavigationToolbar2TkAgg(self.stats, fig)
        nav.update()

        self.ani = animation.FuncAnimation(self.figure, self._update_lines, interval=100, blit=False)
        self.stats.get_tk_widget().pack(fill="both", expand=1)
        self.stats._tkcanvas.pack(fill="both", expand=1)

        nb.add(fig, text="Statistics")
        nb.add(self.viewer, text="Preview")

        self.reset_data()

    def find(self):
        try:
            thresh = float(self.thresh.get())
        except ValueError:
            showerror("Invalid data", "Threshhold has to be a float.", master=self)
            return

        self.values.delete(0, "end")

        for name, tester in Tester.testers.items():
            heights, delta = self.derivative[name]
            for outlier in detect(heights, delta, thresh):
                res = self.all_frames[(outlier, name)]
                self.values.insert("end", ("%d@%s | %.2f%%"%(outlier, name, 100*res)))

    def open(self):
        for line in (self.values.get(i) for i in self.values.curselection()):
            data, _ = line.split(" | ")
            height, tester = data.split("@")
            height = int(height)
            self.master.open_tab(tester, height)

    def reset_data(self):
        self.d_val = {}
        self.all_frames = {}

    def reset_plots(self, min_x=400, max_x=1080):
        self.derivative_data.clear()
        self.normal_data.clear()

        self.derivative_data.set_title("Similarity [d/dx]")
        self.derivative_data.grid()
        self.derivative_data.set_xlabel("Height")
        self.derivative_data.set_ylabel("Similarity Delta")

        self.normal_data.set_title("Similarity [Actual Values]")
        self.normal_data.grid()
        self.normal_data.set_xlabel("Height")
        self.normal_data.set_ylabel("Similarity")

        self.derivative_plots = {}
        self.normal_plots = {}
        self.derivative = {}
        self.normal = {}
        for name, tester in Tester.testers.items():
            self.normal[name] = [], []
            self.derivative[name] = [], []

            self.derivative_plots[name], = self.derivative_data.plot([], [], marker="o", c=tester.color, label=name, linewidth=0)
            self.normal_plots[name], = self.normal_data.plot([], [], c=tester.color, marker="x", label=name, linewidth=0)

        self.derivative_data.set_xlim([min_x, max_x])
        self.derivative_data.set_ylim([-0.1, +0.1])
        self.normal_data.set_xlim([min_x, max_x])
        self.normal_data.set_ylim([.55, .75])

        self.derivative_data.legend(handles=list(self.derivative_plots.values()), loc='upper left', bbox_to_anchor=(0, 1))
        self.normal_data.legend(handles=list(self.normal_plots.values()), loc='upper left', bbox_to_anchor=(0, 1))

    def start_detect(self):
        if self.executor is not None:
            self.executor[1]()
            self.executor = None
            self.proc["text"] = "Detect"
            return

        cpus = int(self.cpu_sel.get())

        raw_ar = self.ar.get().split(":")
        if len(raw_ar) != 2:
            showerror("Invalid data", "Invalid aspect ratio", master=self)
            return

        try:
            ar = tuple(int(a) for a in raw_ar)
        except ValueError:
            showerror("Invalid data", "Invalid aspect ratio", master=self)
            return

        try:
            from_ = self.from_.get()
        except ValueError:
            showerror("Invalid data", "Invalid start frame", master=self)
            return

        try:
            to = self.to.get()
        except ValueError:
            showerror("Invalid data", "Invalid end frame", master=self)
            return

        self.proc["text"] = "Stop"
        self.progress["max"] = len(xrange(from_, to+1, 2))*len(Tester.testers)
        self.progress["value"] = 0

        self.reset_plots(from_, to)
        self.reset_data()

        executor = Executor(self.filename, range(from_, to+1, 2), self.framecb(), aspect_ratio=ar, cpus=cpus)
        cb, stop = executor.test()

        self.after(1, self.sync)
        self.executor = (executor, stop, cb)

    def add_list(self, tester, height, result):
        self.values.insert("end", ("%d@%s | %.2f%%"%(height, tester, 100*result)))
        self.all_frames[(height, tester)] = result

    def sync(self):
        if self.executor is None:
            return

        if self.executor[2](self.new_result):
            self.after(10, self.sync)
            return

        self.executor = None
        self.proc["text"] = "Detect"

    def _update_lines(self, num):
        plts = []
        for name, tester in Tester.testers.items():
            norm_heights, norm_result = self.normal[name]
            self.normal_plots[name].set_data(norm_heights, norm_result)
            plts.append(self.normal_plots[name])

            deri_heights, deri_result = self.derivative[name]
            self.derivative_plots[name].set_data(deri_heights, deri_result)
            plts.append(self.derivative_plots[name])
        return plts

    def new_result(self, tester, width, height, frame, result, image):
        norm_heights, norm_result = self.normal[tester]

        norm_heights.append(height)
        norm_result.append(result)

        if tester in self.d_val:
            deri_heights, deri_result = self.derivative[tester]
            deri_heights.append(height)
            deri_result.append(result - self.d_val[tester])
        self.d_val[tester] = result

        self.figure.canvas.draw()
        self.stats.show()

        self.progress["value"] = int(self.progress["value"])+1

        self.viewer.image = image

        self.add_list(tester, height, result)