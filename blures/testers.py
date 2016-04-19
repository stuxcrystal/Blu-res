import os


class Tester(object):
    testers = {}

    def init(self, env):
        pass

    def test(self, env, clip, resolution):
        pass

    @classmethod
    def tester(cls, name, color):
        def _decorator(new_cls):
            cls.testers[name] = new_cls()
            cls.testers[name].color = color
            return cls
        return _decorator


@Tester.tester("bilinear", "green")
class BilinearTester(Tester):

    def init(self, env):
        import avisynth

        assert isinstance(env, avisynth.AVS_ScriptEnvironment)
        path = os.path.abspath("debilinear.dll")
        if os.path.exists(path):
            env.invoke("LoadPlugin", [path])

    def test(self, env, clip, resolution):
        import avisynth

        assert isinstance(env, avisynth.AVS_ScriptEnvironment)
        assert isinstance(clip, avisynth.AVS_Clip)

        vi = clip.get_video_info()
        width, height = vi.width, vi.height

        sc_clip = env.invoke("debilinear", [clip, resolution[0], resolution[1]])
        return env.invoke("BilinearResize", [sc_clip, width, height])


@Tester.tester("bicubic", "blue")
class BicubicTester(Tester):

    def init(self, env):
        import avisynth

        assert isinstance(env, avisynth.AVS_ScriptEnvironment)
        path = os.path.abspath("debicubic.dll")
        if os.path.exists(path):
            env.invoke("LoadPlugin", [path])

    def test(self, env, clip, resolution):
        import avisynth

        assert isinstance(env, avisynth.AVS_ScriptEnvironment)
        assert isinstance(clip, avisynth.AVS_Clip)

        vi = clip.get_video_info()
        width, height = vi.width, vi.height

        sc_clip = env.invoke("debicubic", [clip, resolution[0], resolution[1]])
        return env.invoke("BicubicResize", [sc_clip, width, height])

@Tester.tester("catrom", "red")
class CatRomTester(Tester):

    def init(self, env):
        import avisynth

        assert isinstance(env, avisynth.AVS_ScriptEnvironment)
        path = os.path.abspath("debicubic.dll")
        if os.path.exists(path):
            env.invoke("LoadPlugin", [path])

    def test(self, env, clip, resolution):
        import avisynth

        assert isinstance(env, avisynth.AVS_ScriptEnvironment)
        assert isinstance(clip, avisynth.AVS_Clip)

        vi = clip.get_video_info()
        width, height = vi.width, vi.height

        sc_clip = env.invoke("debicubic", [clip, resolution[0], resolution[1], 0, 0.5], [None, None, "b", "c"])
        return env.invoke("BicubicResize", [sc_clip, width, height])
