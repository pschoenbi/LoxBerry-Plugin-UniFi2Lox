# VAAPI decode only (CPU MJPEG)

Select this hardware mode when the GPU can decode the source but cannot encode
MJPEG, for example Intel Haswell with an H.264 source and the i965 VAAPI driver.
It is optional; the default and existing hardware modes remain unchanged.

The mode uses `/dev/dri/renderD128`. The service user must have access to it and
an appropriate VAAPI driver must be installed. The driver is selected by libva;
this option does not globally set `LIBVA_DRIVER_NAME` or change permissions.
The download filter expects 8-bit NV12 surfaces; 10-bit sources are not supported
by this mode. The GPU must support the actual source codec and profile. Haswell
does not support HEVC hardware decoding. Hardware failures are not silently
retried with software decoding; select Off to return to software operation.

The generated go2rtc source uses a custom input template, without `#hardware`:

```text
-hwaccel vaapi -hwaccel_device /dev/dri/renderD128 -hwaccel_output_format vaapi ... -i INPUT
```

A single CPU filter graph starts with `hwdownload,format=nv12`, followed by
the configured software scale and rotation. The encoder remains `mjpeg` with
`yuvj420p`. Width and rotation are included in this graph, not also passed to
go2rtc, which would generate a second `-vf` and replace the download filter.
The input template's slash avoids collisions with per-camera template names.

The setting is global to the plugin and applies to all its MJPEG cameras.
Snapshots and raw streams are unchanged. Small streams may see little CPU
benefit because copying frames back to system memory adds overhead.

The installed mode was tested on an Intel Haswell Mobile SOYO mini-PC running
LoxBerry on Debian 13, with the i965 driver, FFmpeg 7.1.5 and go2rtc 1.9.14.
The H.264 source was 1280x720 at 24 fps, with MJPEG configured at width 1280,
10 fps, quality 5 and no rotation. The actual FFmpeg command used VAAPI input,
`hwdownload,format=nv12,scale=1280:-1` and the software `mjpeg` encoder.
The MJPEG endpoint returned HTTP 200, and the tester confirmed continued live
video in a browser and successful use in Loxone. No driver override was needed
by the installed service. This verifies functionality, not a controlled CPU
performance improvement or hardware coverage beyond this machine.

Validate the patched plugin with a Loxone live view, snapshot, reconnect, and
the desired scale/rotation. Inspect the actual FFmpeg command and GPU Video
activity. Back up the plugin and configuration before deployment and check
`vainfo` as the service user. Keep the previous mode available for
immediate rollback and restore original files/config if necessary. A restart
regenerates `go2rtc.yaml`; do not restore stale PID files.

Run configuration tests with:

```sh
python3 -m unittest discover -s tests -v
```
