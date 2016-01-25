import Queue
import threading
import functools

import avisynth

from blures.futures import TkFuture
from blures.worker import ScaleWorker, Executor
from blures.testers import Tester


def queue_command(func):
    def _call_wrapped_func(data):
        self, args, kwargs, fut = data
        try:
            fut.set_result(func(self, *args, **kwargs))
        except Exception as e:
            fut.set_error(e)

    @functools.wraps(func)
    def _wrapper(self, *args, **kwargs):
        fut = TkFuture()
        self.queue.put((_call_wrapped_func, (self, args, kwargs, fut)))
        return fut

    return _wrapper


class AvisynthThread(threading.Thread):
    def __init__(self, master):
        super(AvisynthThread, self).__init__()
        self.daemon = True
        self.master = master
        self.queue = Queue.Queue()
        self.avisynth = None

    def run(self):
        self.avisynth = avisynth.AVS_ScriptEnvironment()
        qempty = Queue.Empty
        while True:
            try:
                func, data = self.queue.get(timeout=1)
            except qempty:
                continue

            func(data)

    @queue_command
    def load(self, avs):
        return self.avisynth.invoke("ConvertToRGB24", [self.avisynth.invoke("Import", [avs])])

    @queue_command
    def get_frame(self, clip, n):
        buf = ScaleWorker.create_buffer(clip)
        return ScaleWorker.get_frame(buf, self.avisynth, clip, n)

    @queue_command
    def get_tester_frame(self, clip, tester, height, n):
        buf = ScaleWorker.create_buffer(clip)
        tclip = Tester.testers[tester].test(self.avisynth, clip, Executor.get_resolution(height))
        return ScaleWorker.get_frame(buf, self.avisynth, tclip, n)