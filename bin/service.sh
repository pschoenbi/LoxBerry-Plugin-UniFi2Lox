#!/bin/bash
# Start/stop the go2rtc streaming engine of the unifi2lox plugin.
# Usage: service.sh start|stop|restart|status|watchdog

SELF_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"   # $LBHOMEDIR/bin/plugins/<folder>
LBHOMEDIR="${LBHOMEDIR:-$(cd "$SELF_DIR/../../.." && pwd)}"
PLUGIN="$(basename "$SELF_DIR")"
BIN="$LBHOMEDIR/bin/plugins/$PLUGIN"
CFG="$LBHOMEDIR/config/plugins/$PLUGIN/config.json"
DATA="$LBHOMEDIR/data/plugins/$PLUGIN"
LOGDIR="$LBHOMEDIR/log/plugins/$PLUGIN"
LOG="$LOGDIR/go2rtc.log"
PIDFILE="$DATA/go2rtc.pid"
GO2RTC="$BIN/go2rtc"
YAML="$DATA/go2rtc.yaml"

export LBHOMEDIR
mkdir -p "$DATA" "$LOGDIR"

is_running() {
    [ -f "$PIDFILE" ] || return 1
    local pid; pid=$(cat "$PIDFILE" 2>/dev/null)
    [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null && grep -q go2rtc "/proc/$pid/cmdline" 2>/dev/null
}

enabled() {
    [ -f "$CFG" ] || return 1
    python3 -c "import json,sys; c=json.load(open('$CFG')); sys.exit(0 if c.get('server',{}).get('enabled',True) and any(x.get('enabled') for x in c.get('cameras',[])) else 1)" 2>/dev/null
}

start() {
    if is_running; then echo "ALREADY $(cat "$PIDFILE")"; return 0; fi
    if [ ! -x "$GO2RTC" ]; then echo "go2rtc missing: $GO2RTC" >>"$LOG"; echo "NO_GO2RTC"; return 1; fi
    if ! enabled; then echo "DISABLED"; return 0; fi
    python3 "$BIN/unifi2lox.py" generate >>"$LOG" 2>&1 || { echo "CONFIG_ERROR"; return 1; }
    echo "$(date '+%F %T') starting go2rtc" >>"$LOG"
    local before; before=$(stat -c %s "$LOG" 2>/dev/null || echo 0)
    cd "$DATA" || return 1
    # When started from the web UI we inherit Apache's sockets (port 80!).
    # Close every inherited descriptor so go2rtc never blocks Apache restarts.
    for fd in $(ls /proc/$$/fd); do
        [ "$fd" -gt 2 ] 2>/dev/null && eval "exec $fd>&-" 2>/dev/null
    done
    setsid nohup "$GO2RTC" -config "$YAML" </dev/null >>"$LOG" 2>&1 &
    echo $! >"$PIDFILE"
    sleep 1.5
    if tail -c +"$((before + 1))" "$LOG" | grep -q "address already in use"; then
        echo "PORT_BUSY"
        stop >/dev/null; return 1
    fi
    if ! is_running; then  # setsid may have forked - look the process up by its binary
        for p in $(pgrep -x go2rtc); do
            [ "$(readlink -f "/proc/$p/exe" 2>/dev/null)" = "$(readlink -f "$GO2RTC")" ] && echo "$p" >"$PIDFILE"
        done
    fi
    if is_running; then echo "STARTED $(cat "$PIDFILE")"; return 0; fi
    echo "FAILED"; return 1
}

stop() {
    if is_running; then
        local pid; pid=$(cat "$PIDFILE")
        kill "$pid" 2>/dev/null
        for _ in 1 2 3 4 5 6 7 8 9 10; do kill -0 "$pid" 2>/dev/null || break; sleep 0.3; done
        kill -9 "$pid" 2>/dev/null
    fi
    rm -f "$PIDFILE"
    # orphaned instances (e.g. after a crash of the pidfile)
    # only processes running exactly our binary
    for p in $(pgrep -x go2rtc); do
        [ "$(readlink -f "/proc/$p/exe" 2>/dev/null)" = "$(readlink -f "$GO2RTC")" ] && kill "$p" 2>/dev/null
    done
    echo "STOPPED"
}

trim_log() {
    # logs live on tmpfs - keep them small
    if [ -f "$LOG" ] && [ "$(stat -c %s "$LOG")" -gt 2000000 ]; then
        tail -c 500000 "$LOG" >"$LOG.tmp" && mv "$LOG.tmp" "$LOG"
    fi
}

case "$1" in
    start)   start ;;
    stop)    stop ;;
    restart) stop; start ;;
    status)  if is_running; then echo "RUNNING $(cat "$PIDFILE")"; else echo "STOPPED"; exit 1; fi ;;
    watchdog)
        trim_log
        [ -f "$DATA/stopped.flag" ] && exit 0
        if ! is_running && enabled; then
            echo "$(date '+%F %T') watchdog: go2rtc not running - restarting" >>"$LOG"
            start >/dev/null
        fi ;;
    *) echo "Usage: $0 start|stop|restart|status|watchdog"; exit 2 ;;
esac
