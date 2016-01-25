import inspect
import functools
import traceback


class TkFuture(object):

    def __init__(self):
        self.error_cb = []
        self.result_cb = []

        self._done = False
        self.result = None
        self.error = None

    def _call_cbs(self, cbs):
        for cb in cbs:
            cb(self)

    def set_error(self, error):
        if self._done:
            return
        self._done = True
        self.error = error
        self._call_cbs(self.error_cb)

    def set_result(self, result):
        if self._done:
            return
        self._done = True
        self.result = result
        self._call_cbs(self.result_cb)

    def add_callback(self, cb):
        self.add_res_cb(cb)
        self.add_err_cb(cb)

    def add_res_cb(self, cb):
        if self._done:
            if self.is_error():
                return
            cb(self)
            return

        self.result_cb.append(cb)

    def add_err_cb(self, cb):
        if self._done:
            if not self.is_error():
                return
            cb(self)
            return
        self.error_cb.append(cb)

    def is_done(self):
        return self._done

    def get(self):
        if not self._done:
            return None
        if self.error is not None:
            raise self.error
        return self.result

    def is_error(self):
        if not self._done:
            return False
        return self.error is not None

    def set_lowlevel(self):
        def _raise(_):
            print(_.error)
            traceback.print_exc()
        self.add_err_cb(_raise)

    def __iter__(self):
        yield self


def TaskCallback(task):
    @functools.wraps(task)
    def _wrapper(*args, **kwargs):
        fut = task(*args, **kwargs)
        fut.set_lowlevel()
        return fut
    return _wrapper


def Task(masterattr="master"):
    def run_future(master, *args):
        master.after(1, lambda: advance_future(master, *args))

    def advance_future(master, gen, self_fut, other_fut):
        try:
            if other_fut is not None:
                other = send_value(gen, other_fut.result, other_fut.error)
            else:
                other = send_value(gen)
        except Exception as e:
            self_fut.set_error(e)
        else:
            if not isinstance(other, TkFuture):
                self_fut.set_result(other)
            else:
                other.add_callback(lambda fut: run_future(master, gen, self_fut, fut))

    def send_value(gen, val=None, err=None):
        try:
            if err:
                return gen.throw(err)
            else:
                return gen.send(val)
        except StopIteration:
            return None

    def _ensure_generator(func):
        if inspect.isgeneratorfunction(func):
            return func

        if inspect.isgenerator(func):
            return lambda: func

        @functools.wraps(func)
        def _wrapper(*args, **kwargs):
            yield func(*args, **kwargs)
        return _wrapper

    def _decorator(func):
        @functools.wraps(func)
        def _wrapper(self, *args, **kwargs):
            if masterattr is not None:
                master = getattr(self, masterattr)
            else:
                master = None

            res_future = TkFuture()
            advance_future(master, _ensure_generator(func)(self, *args, **kwargs), res_future, None)

            return res_future

        return _wrapper

    if callable(masterattr):
        func = masterattr
        masterattr = "master"
        return _decorator(func)
    return _decorator
