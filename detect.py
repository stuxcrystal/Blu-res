"""
Usage:
    hallo.py SRC FRAMES HEIGHTS
"""
import os
import time
import threading

os.environ["TCL_LIBRARY"] = "C:\\Python27\\tcl\\tcl8.5"

from matplotlib import pyplot

import docopt

from blures.worker import Executor
from blures.testers import Tester


def run():
    vars = docopt.docopt(__doc__)

    fstep = range(*(int(i) for i in vars["FRAMES"].split(":")))
    hstep = range(*(int(i) for i in vars["HEIGHTS"].split(":")))
    src = vars["SRC"]

    app = Executor(src, hstep, fstep)
    cb, stop = app.test()

    class _data(object):
        testers = {}
        res_before = {}
        lock = threading.Lock()

        @classmethod
        def init(cls):
            for name, tester in Tester.testers.items():
                data = [[], [], []]
                cls.testers[name] = data

            plots, names = [],[]
            for name, tester in Tester.testers.items():
                pyplot.subplot(211)
                plt = pyplot.scatter([], [], color=tester.color)
                plots.append(plt)
                names.append(name)
                pyplot.grid()
                pyplot.legend(plots, names, loc='upper left', bbox_to_anchor=(0, 1))

            plots, names = [],[]
            for name, tester in Tester.testers.items():
                pyplot.subplot(212)
                plt = pyplot.scatter([], [], color=tester.color)
                plots.append(plt)
                names.append(name)
                pyplot.grid()
                pyplot.legend(plots, names, loc='upper left', bbox_to_anchor=(0, 1))

        @classmethod
        def on_new_item(cls, tester, width, height, frame, result, image):
            if tester not in cls.res_before:
                cls.res_before[tester] = result
                return

            diff = result - cls.res_before[tester]

            heights, results, actual = cls.testers[tester]
            with cls.lock:
                heights.append(height)
                results.append(diff)
                actual.append(result)

            cls.res_before[tester] = result

    def datathread():
        while cb(_data.on_new_item):
            pass

    _data.init()

    thread = threading.Thread(target=datathread)
    thread.daemon = True
    thread.start()

    def _update():
        pyplot.subplot(211)
        plots, names = [], []
        for name, tester in Tester.testers.items():
            with _data.lock:
                heights, delta, results = _data.testers[name]
                plt = pyplot.scatter(heights, delta, color=tester.color, marker="x")
            plots.append(plt)
            names.append(name)


        pyplot.title("Resolution Rescaling Image Comparison [d/dx]")
        pyplot.legend(plots, names, loc='upper left', bbox_to_anchor=(0, 1))

        pyplot.subplot(212)
        plots, names = [], []
        for name, tester in Tester.testers.items():
            with _data.lock:
                heights, delta, results = _data.testers[name]
                plt = pyplot.scatter(heights, results, color=tester.color)
            plots.append(plt)
            names.append(name)

        pyplot.title("Resolution Rescaling Image Comparison")
        pyplot.legend(plots, names, loc='upper left', bbox_to_anchor=(0, 1))

        pyplot.draw()

    pyplot.subplot(211)
    pyplot.grid()
    pyplot.subplot(212)
    pyplot.grid()

    tstart = time.time()
    while thread.is_alive():
        if time.time()-tstart > 5:
            _update()
            tstart = time.time()

        pyplot.pause(.5)
    _update()
    stop()

    import numpy as np

    def is_outlier(points, thresh=5):
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

    for name, tester in Tester.testers.items():
        heights, results, _ = _data.testers[name]
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

            print("Possible interesting point at height: %d@%s" % (heights[int(ibefore[0])], name))
            ibefore = (i, val)

    pyplot.show()

if __name__ == "__main__":
    run()