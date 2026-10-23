import copy
import importlib.util
import pathlib
import shlex
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("unifi2lox", ROOT / "bin/unifi2lox.py")
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)


def config(mode="vaapi_decode", **camera):
    cam = dict(plugin.CAMERA_DEFAULTS, slug="camera_1", name="Test")
    cam.update(camera)
    return {"server": {"hwaccel": mode}, "cameras": [cam]}


def generate(cfg):
    return plugin.build_go2rtc(cfg, {c["slug"]: "rtsp://example.invalid/test"
                                     for c in cfg["cameras"]})


class DecodeOnlyTests(unittest.TestCase):
    def test_separate_input_and_cpu_encoder(self):
        g = generate(config(width=0))
        src = g["streams"]["camera_1_mjpeg"][0]
        self.assertIn("#input=u2l/vaapi_decode", src)
        self.assertNotIn("#hardware", src)
        inp = shlex.split(g["ffmpeg"]["u2l/vaapi_decode"])
        self.assertEqual(inp[inp.index("-hwaccel") + 1], "vaapi")
        self.assertEqual(inp[inp.index("-hwaccel_output_format") + 1], "vaapi")
        self.assertLess(inp.index("-hwaccel"), inp.index("-i"))
        self.assertIn("-c:v mjpeg ", g["ffmpeg"]["mjpeg"])
        self.assertNotIn("mjpeg_vaapi", str(g))

    def test_download_precedes_scale_and_every_rotation(self):
        for width in (0, 640, 1280):
            for rot, rotate_filter in ((0, []), (90, ["transpose=1"]),
                                       (180, ["transpose=1", "transpose=1"]),
                                       (270, ["transpose=2"])):
                with self.subTest(width=width, rotation=rot):
                    g = generate(config(width=width, rotate=rot))
                    src = g["streams"]["camera_1_mjpeg"][0]
                    self.assertNotIn("#width", src)
                    self.assertNotIn("#rotate", src)
                    args = shlex.split(g["ffmpeg"]["u2l_camera_1"])
                    self.assertEqual(args.count("-vf"), 1)
                    want = ["hwdownload", "format=nv12"]
                    if width:
                        want.append("scale=%d:-1" % width)
                    self.assertEqual(args[args.index("-vf") + 1].split(","),
                                     want + rotate_filter)

    def test_other_modes_keep_standard_go2rtc_filters(self):
        for mode, suffix in (("off", ""), ("auto", "#hardware"),
                             ("vaapi", "#hardware=vaapi"),
                             ("v4l2m2m", "#hardware=v4l2m2m"),
                             ("rkmpp", "#hardware=rkmpp")):
            with self.subTest(mode=mode):
                g = generate(config(mode, width=640, rotate=90))
                self.assertEqual(g["streams"]["camera_1_mjpeg"], [
                    "ffmpeg:camera_1#video=mjpeg#raw=u2l_camera_1#width=640#rotate=90" + suffix])
                self.assertEqual(g["ffmpeg"]["u2l_camera_1"], "-q:v 5 -r 10")
                self.assertNotIn("u2l/vaapi_decode", g["ffmpeg"])

    def test_cameras_have_independent_filters_and_no_template_collision(self):
        cfg = config(slug="vaapi_decode", width=640, rotate=90, quality=2, fps=5)
        cfg["cameras"].append(dict(plugin.CAMERA_DEFAULTS, slug="second", width=0))
        g = generate(cfg)
        self.assertIn("-hwaccel vaapi", g["ffmpeg"]["u2l/vaapi_decode"])
        self.assertIn("scale=640:-1,transpose=1", g["ffmpeg"]["u2l_vaapi_decode"])
        self.assertEqual(g["ffmpeg"]["u2l_second"],
                         "-q:v 5 -r 10 -vf hwdownload,format=nv12")
        self.assertIn("-q:v 2 -r 5", g["ffmpeg"]["u2l_vaapi_decode"])

    def test_stream_authentication_preload_and_input_config_preserved(self):
        cfg = config(preload="mjpeg")
        cfg["server"].update(username="test", password="dummy", port=2345)
        original = copy.deepcopy(cfg)
        g = generate(cfg)
        self.assertEqual(cfg, original)
        self.assertEqual(g["rtsp"]["password"], "dummy")
        self.assertEqual(g["api"]["listen"], ":2345")
        self.assertEqual(g["preload"], {"camera_1_mjpeg": "video"})

    def test_unresolved_camera_stays_absent(self):
        g = plugin.build_go2rtc(config(), {})
        self.assertEqual(g["streams"], {})
        self.assertNotIn("preload", g)


if __name__ == "__main__":
    unittest.main()
