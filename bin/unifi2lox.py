#!/usr/bin/env python3
"""UniFi Protect -> Loxone bridge helper.

Commands:
  generate   build go2rtc config from config.json (resolves RTSPS URLs via Protect API)
  discover   list cameras of the Protect console as JSON
  test       test the API connection, prints JSON
  defaults   print a default camera entry as JSON

Only Python standard library is used.
"""
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# this file lives in $LBHOMEDIR/bin/plugins/<folder>/
_SELF = os.path.dirname(os.path.realpath(__file__))
LBHOMEDIR = os.environ.get("LBHOMEDIR") or os.path.realpath(os.path.join(_SELF, "..", "..", ".."))
PLUGIN = os.path.basename(_SELF)
CFGDIR = os.environ.get("U2L_CFGDIR", os.path.join(LBHOMEDIR, "config/plugins", PLUGIN))
DATADIR = os.environ.get("U2L_DATADIR", os.path.join(LBHOMEDIR, "data/plugins", PLUGIN))
CFGFILE = os.path.join(CFGDIR, "config.json")
GO2RTC_YAML = os.path.join(DATADIR, "go2rtc.yaml")
CACHEFILE = os.path.join(DATADIR, "streams_cache.json")

QUALITIES = ("high", "medium", "low", "package")

CAMERA_DEFAULTS = {
    "id": "",
    "name": "",
    "slug": "",
    "enabled": True,
    "source": "medium",      # Protect stream channel used as source
    "manual_url": "",        # optional: RTSP(S) URL copied from Protect UI
    "width": 1280,           # MJPEG output width, 0 = original
    "fps": 10,               # MJPEG frame rate
    "quality": 5,            # ffmpeg -q:v (2 = best ... 15 = small)
    "rotate": 0,             # 0/90/180/270
    "snapshot": "api_hq",    # api_hq | api | go2rtc
    "preload": "rtsp",       # none | rtsp | mjpeg
}


def log(msg):
    sys.stderr.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")


def load_config():
    with open(CFGFILE, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    cfg.setdefault("protect", {})
    cfg.setdefault("server", {})
    cfg.setdefault("cameras", [])
    for cam in cfg["cameras"]:
        for k, v in CAMERA_DEFAULTS.items():
            cam.setdefault(k, v)
    return cfg


def slugify(name):
    s = name.lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"), ("é", "e"), ("è", "e"), ("à", "a")):
        s = s.replace(a, b)
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s or "cam"


# --------------------------------------------------------------------------- API
class ProtectAPI:
    def __init__(self, cfg):
        p = cfg["protect"]
        # env overrides let the web UI test credentials before they are saved
        self.host = (os.environ.get("U2L_HOST") or p.get("host") or "").strip()
        self.key = (os.environ.get("U2L_KEY") or p.get("apikey") or "").strip()
        self.host = re.sub(r"^https?://", "", self.host).rstrip("/")
        self.ctx = ssl.create_default_context()
        if not p.get("verify_ssl", False):
            self.ctx.check_hostname = False
            self.ctx.verify_mode = ssl.CERT_NONE

    @property
    def usable(self):
        return bool(self.host and self.key)

    def request(self, path, method="GET", body=None, timeout=8, raw=False):
        url = "https://%s/proxy/protect/integration/v1%s" % (self.host, path)
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("X-API-KEY", self.key)
        req.add_header("Accept", "image/jpeg" if raw else "application/json")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, context=self.ctx, timeout=timeout) as r:
            payload = r.read()
        return payload if raw else (json.loads(payload) if payload else None)

    def cameras(self):
        return self.request("/cameras")

    def rtsps(self, cam_id, quality):
        streams = self.request("/cameras/%s/rtsps-stream" % cam_id) or {}
        url = streams.get(quality)
        if not url:
            created = self.request("/cameras/%s/rtsps-stream" % cam_id, "POST", {"qualities": [quality]}) or {}
            url = created.get(quality)
        return url


# --------------------------------------------------------------------------- URL handling
def convert_url(url, cfg):
    """Turn the Protect RTSPS URL into the transport chosen in config."""
    transport = cfg["protect"].get("transport", "rtspx")
    host = (cfg["protect"].get("host") or "").strip()
    host = re.sub(r"^https?://", "", host).split("/")[0]
    if host.count(":") == 1:  # strip a web port like 192.168.1.1:443
        host = host.split(":")[0]
    u = urllib.parse.urlsplit(url)
    token = u.path.lstrip("/")
    if not host:
        host = u.hostname
    if u.scheme in ("rtsps", "rtspx") or u.port in (7441, 7447):
        if transport == "rtsp":
            return "rtsp://%s:7447/%s" % (host, token)
        return "rtspx://%s:7441/%s" % (host, token)
    return url  # foreign URL: leave untouched


def load_cache():
    try:
        with open(CACHEFILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_cache(cache):
    tmp = CACHEFILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=1)
    os.replace(tmp, CACHEFILE)


def resolve_sources(cfg):
    api = ProtectAPI(cfg)
    cache = load_cache()
    out = {}
    for cam in cfg["cameras"]:
        if not cam.get("enabled"):
            continue
        slug = cam["slug"] or slugify(cam["name"])
        url = None
        if cam.get("manual_url"):
            url = cam["manual_url"].strip()
        elif api.usable and cam.get("id"):
            try:
                url = api.rtsps(cam["id"], cam.get("source", "medium"))
                if url:
                    cache[slug] = url
            except Exception as e:  # API down -> fall back to last known token
                log("WARN: API stream lookup failed for %s: %s" % (slug, e))
        if not url:
            url = cache.get(slug)
        if not url:
            log("ERROR: no stream URL for camera %s - skipped" % slug)
            continue
        out[slug] = convert_url(url, cfg)
    try:
        save_cache(cache)
    except Exception as e:
        log("WARN: cannot write cache: %s" % e)
    return out


# --------------------------------------------------------------------------- go2rtc config
def build_go2rtc(cfg, sources):
    srv = cfg["server"]
    port = int(srv.get("port", 1984))
    hw = srv.get("hwaccel", "off")
    loglevel = srv.get("loglevel", "warn")

    g = {
        "log": {"level": loglevel, "format": "text", "ffmpeg": "error"},
        "api": {"listen": ":%d" % port, "origin": "*"},
        "rtsp": {"listen": ("0.0.0.0:8554" if srv.get("rtsp_lan") else "127.0.0.1:8554")},
        "webrtc": {"listen": ""},
        "ffmpeg": {
            "bin": "ffmpeg",
            # full-range 4:2:0 JPEG frames: best compatibility with Loxone app/miniserver
            "mjpeg": "-c:v mjpeg -pix_fmt:v yuvj420p -huffman:v optimal",
            # shorter stream probing: first MJPEG frame ~1s earlier (measured 2.6s -> 0.6-1.6s)
            "rtsp": "-fflags nobuffer -flags low_delay -analyzeduration 500000 -probesize 500000 "
                    "-timeout {timeout} -user_agent go2rtc/ffmpeg -rtsp_flags prefer_tcp -i {input}",
        },
        "streams": {},
        "preload": {},
    }
    if srv.get("username") and srv.get("password"):
        g["api"]["username"] = srv["username"]
        g["api"]["password"] = srv["password"]
        g["rtsp"]["username"] = srv["username"]
        g["rtsp"]["password"] = srv["password"]

    for cam in cfg["cameras"]:
        slug = cam["slug"] or slugify(cam["name"])
        if slug not in sources:
            continue
        g["streams"][slug] = [sources[slug]]

        # per camera encoder settings live in a named template -> no escaping trouble
        q = max(2, min(31, int(cam.get("quality", 5))))
        fps = max(1, min(30, int(cam.get("fps", 10))))
        tpl = "u2l_%s" % slug
        g["ffmpeg"][tpl] = "-q:v %d -r %d" % (q, fps)

        src = "ffmpeg:%s#video=mjpeg#raw=%s" % (slug, tpl)
        width = int(cam.get("width", 0) or 0)
        if width > 0:
            src += "#width=%d" % width
        rot = int(cam.get("rotate", 0) or 0)
        if rot in (90, 180, 270):
            src += "#rotate=%d" % rot
        if hw and hw != "off":
            src += "#hardware" if hw == "auto" else "#hardware=%s" % hw
        g["streams"][slug + "_mjpeg"] = [src]

        pre = cam.get("preload", "rtsp")
        if pre == "rtsp":
            g["preload"][slug] = "video"
        elif pre == "mjpeg":
            g["preload"][slug + "_mjpeg"] = "video"

    if not g["preload"]:
        del g["preload"]
    return g


def api_error(e):
    """Language neutral error: the web UI translates 'code', 'error' is technical detail."""
    if isinstance(e, urllib.error.HTTPError):
        code = "unauthorized" if e.code in (401, 403) else "http"
        return {"ok": False, "code": code, "error": "HTTP %s" % e.code}
    return {"ok": False, "code": "unreachable", "error": str(getattr(e, "reason", e))}


def cmd_generate():
    cfg = load_config()
    os.makedirs(DATADIR, exist_ok=True)
    sources = resolve_sources(cfg)
    g = build_go2rtc(cfg, sources)
    tmp = GO2RTC_YAML + ".tmp"
    # YAML is a superset of JSON -> go2rtc reads this directly, no PyYAML needed
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(g, f, indent=2)
    os.chmod(tmp, 0o600)
    os.replace(tmp, GO2RTC_YAML)
    log("INFO: go2rtc config written with %d camera(s)" % len(sources))
    return 0


def cmd_discover():
    cfg = load_config()
    api = ProtectAPI(cfg)
    if not api.usable:
        print(json.dumps({"ok": False, "code": "missing_cred"}))
        return 1
    try:
        cams = api.cameras() or []
    except Exception as e:
        print(json.dumps(api_error(e)))
        return 1
    res = []
    for c in cams:
        res.append({
            "id": c.get("id"),
            "name": c.get("name") or c.get("id"),
            "model": c.get("modelKey") or c.get("type") or "",
            "state": c.get("state", ""),
            "slug": slugify(c.get("name") or c.get("id") or "cam"),
            "has_package": bool((c.get("featureFlags") or {}).get("hasPackageCamera")),
        })
    print(json.dumps({"ok": True, "cameras": res}))
    return 0


def cmd_test():
    cfg = load_config()
    api = ProtectAPI(cfg)
    if not api.usable:
        print(json.dumps({"ok": False, "code": "missing_cred"}))
        return 1
    t = time.time()
    try:
        cams = api.cameras() or []
        print(json.dumps({"ok": True, "cameras": len(cams), "ms": int((time.time() - t) * 1000)}))
        return 0
    except Exception as e:
        print(json.dumps(api_error(e)))
    return 1


def main(argv):
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "generate":
        return cmd_generate()
    if cmd == "discover":
        return cmd_discover()
    if cmd == "test":
        return cmd_test()
    if cmd == "defaults":
        print(json.dumps(CAMERA_DEFAULTS))
        return 0
    sys.stderr.write(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
