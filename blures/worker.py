import math
import time
import Queue
import ctypes
import multiprocessing
from multiprocessing.queues import SimpleQueue

import numpy as np
from PIL import Image, ImageChops

from blures.testers import Tester


class ScaleWorker(object):
    """
    Multiprocessing support for scales.
    """

    @staticmethod
    def create_buffer(clip):
        vi = clip.get_video_info()
        w, h = vi.width, vi.height
        stride = (24/8)*w
        return ctypes.create_string_buffer(stride*h)

    @staticmethod
    def get_frame(buf, env, clip, n):
        frame = clip.get_frame(n)
        vi = clip.get_video_info()
        w, h = vi.width, vi.height
        stride = (24/8)*w
        pBuf = ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte))

        env.bit_blt(pBuf, stride, frame.get_read_ptr(), frame.get_pitch(), frame.get_row_size(), frame.get_height())
        image = Image.frombytes("RGB", (w, h), ctypes.string_at(buf, stride*h), "raw", "BGR")
        image.show()
        raise

        return image.rotate(180).transpose(Image.FLIP_LEFT_RIGHT)

    def write_raw(self, type, data):
        if hasattr(self.out_queue, "send"):
            self.out_queue.send((type, self.no, data))
        else:
            self.out_queue.put((type, self.no, data))

    def write_message(self, message):
        self.write_raw("message", message)

    def write_result(self, tester, width, height, frame, result, image, time):
        self.write_raw("result", (tester, width, height, frame, result, image, time))

    def write_restart(self):
        self.write_raw("restart", ())

    @classmethod
    def start(cls, no, avsfile, frames, in_queue, out_queue):
        sw = ScaleWorker()
        sw.run(no, avsfile, frames, in_queue, out_queue)

    def run(self, no, avsfile, frames, in_queue, out_queue):
        def _get_frame(env, clip, frame):
            fr = self.get_frame(self.buf, env, clip, frame)
            return fr, self.compare(fr, fr)

        import avisynth

        self.no = no
        self.avsfile = avsfile
        self.in_queue = in_queue
        self.out_queue = out_queue
        self.frames = frames

        self.write_message("Initializing avisynth")
        env = avisynth.AVS_ScriptEnvironment(3)
        for tester in Tester.testers.values():
            tester.init(env)

        self.write_message("Loading video...")
        clip = env.invoke("ConvertToRGB24", [env.invoke("Import", [self.avsfile])])

        self.buf = self.create_buffer(clip)

        self.write_message("Rendering comparison frames")
        self.frames = {
            frame: _get_frame(env, clip, frame)
            for frame in frames
        }

        self.write_message("Working on queue")
        count = -1
        while count != 0:
            try:
                tester, width, height, frame = self.in_queue.get(timeout=5)
            except Queue.Empty:
                self.write_message("Empty queue detected.")
                break

            tester_inst = Tester.testers[tester]
            test_clip = tester_inst.test(env, clip, (width, height))

            try:
                image = self.get_frame(self.buf, env, test_clip, frame)
            except avisynth.AvisynthError:
                self.write_message("Error in %dx%d@%d" % (width, height, frame))
                raise

            ratio = self.compare(image, self.frames[frame][0])/self.frames[frame][1]
            self.write_result(tester, width, height, frame, ratio, image, time.time())

            count -= 1

        if count == 0:
            self.write_restart()
            while True:
                pass

    def compare(self, generated, original):
        h = np.array(ImageChops.difference(generated, original).histogram(), dtype=np.uint64)
        return math.sqrt(np.sum((h**2)*np.arange(len(h))) / (float(original.size[0]) * original.size[1]))


class Executor(object):

    def __init__(self, avsfile, heights, frames, aspect_ratio=(16,9), cpus=None):
        import avisynth

        self.avsfile = avsfile

        self.env = avisynth.AVS_ScriptEnvironment(3)
        for tester in Tester.testers.values():
            tester.init(self.env)
        self.clip = self.env.invoke("ConvertToRGB24", [self.env.invoke("Import", [self.avsfile])])

        self.fstep = list(frames)
        self.hstep = list(heights)
        self.cpus = cpus

        self.aspect_ratio = aspect_ratio

    @staticmethod
    def get_resolutions(height_step, aspect_ratio=(16,9)):
        for height in height_step:
            yield Executor.get_resolution(height, aspect_ratio)

    @staticmethod
    def get_resolution(height, aspect_ratio=(16, 9)):
        return int(round(height/float(aspect_ratio[1])*aspect_ratio[0]/2)*2), height

    @staticmethod
    def get_frames(frame_step):
        for frame in frame_step:
            yield frame

    def get_vals(self, frames):
        for name, tester in Tester.testers.items():
            for frame in frames:
                for width, height in self.get_resolutions(self.hstep, aspect_ratio=self.aspect_ratio):
                    yield name, width, height, frame

    def test(self):
        print("[Main] Generating Comparison Frames.")

        vals = self.get_vals(list(self.get_frames(self.fstep)))

        if self.cpus is None:
            try:
                self.cpus = multiprocessing.cpu_count()
            except NotImplementedError:
                self.cpus = 1

        in_queue = multiprocessing.Queue()
        main_queue = multiprocessing.Queue()

        print("[Main] Starting workers (%d)" % self.cpus)

        starttime = time.time()
        running_workers = {}
        workers = []
        queues = [main_queue]
        for i in range(self.cpus):
            main_queue.put(("restart", i, ()))

        starttime = time.time()
        class _data(object): pass

        def test_loopcb(item_update):
            while _data.next_obj is not None:
                in_queue.put(_data.next_obj, 1)
                _data.next_obj = next(vals, None)

            found = False
            for queue in queues:
                try:
                    if hasattr(queue, "empty"):
                        if queue.empty():
                            continue

                        type, worker, data = queue.get()
                    else:
                        if not queue.poll():
                            continue
                        type, worker, data = queue.recv()

                except Queue.Empty:
                    continue
                else:
                    found = True
                    break

            queues.remove(queue)
            queues.append(queue)

            if not found:
                alive = False
                if len(workers) > 0:
                    for worker in workers:
                        if worker.is_alive():
                            alive = True
                            break

                if not alive:
                    return False
                else:
                    return True

            if type == "message":
                print("[Worker-%d] %s" % (worker, data))

            elif type == "result":
                tester, width, height, frame, result, image, r_time = data
                self.print_result(tester, width, height, frame, result, r_time-starttime, worker)
                item_update(tester, width, height, frame, result, image)

            elif type == "restart":
                print("[Main] Restarting worker %d" % worker)
                if worker in running_workers:
                    running_workers[worker].terminate()

                out_queue = SimpleQueue()
                new_worker = multiprocessing.Process(
                    target=ScaleWorker.start,
                    args=(
                        worker, self.avsfile, self.fstep, in_queue, out_queue
                    )
                )
                new_worker.daemon = True
                running_workers[worker] = new_worker
                queues.append(out_queue)
                workers.append(new_worker)
                new_worker.start()

            return True

        def stop():
            for worker in workers:
                worker.terminate()

        _data.next_obj = next(vals, None)
        return test_loopcb, stop

    def print_result(self, t, w, h, f, p, c, n):
        print "[Result] %s\t%dx%d\t%d\t%.4f%%\t%.2fsecs\tWorker-%d"%(t, w, h, f, p*100, c, n)