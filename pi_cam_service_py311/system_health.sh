#!/bin/bash
# System health monitor for Raspberry Pi
# Logs memory, swap, CPU, disk, and Python memory usage
# Both to screen and $LOGFILE

LOGFILE="$HOME/system_health.log"
PYTHON_PROCESS="main.py"

while true; do
    TIMESTAMP="=== $(date '+%Y-%m-%d %H:%M:%S') ==="
    echo "$TIMESTAMP" | tee -a "$LOGFILE"

    # Disk usage
    echo "== Disk ==" | tee -a "$LOGFILE"
    df -h / | tee -a "$LOGFILE"

    # Memory usage
    echo "== Memory ==" | tee -a "$LOGFILE"
    free -h | tee -a "$LOGFILE"

    # Swap usage
    echo "== Swap ==" | tee -a "$LOGFILE"
    swapon --show | tee -a "$LOGFILE"
    awk '/SwapTotal|SwapFree/ {print}' /proc/meminfo | tee -a "$LOGFILE"

    # Top memory-consuming processes
    echo "== Top Memory Processes ==" | tee -a "$LOGFILE"
    ps aux --sort=-%mem | head -n 10 | tee -a "$LOGFILE"

    # Python process RSS
    PY_RSS=$(ps -C python3 -o pid,rss,cmd --sort=-rss | grep "$PYTHON_PROCESS" || echo "None")
    echo "== Python Process RSS ==" | tee -a "$LOGFILE"
    echo "$PY_RSS" | tee -a "$LOGFILE"

    # Load & uptime
    echo "== Load & Uptime ==" | tee -a "$LOGFILE"
    uptime | tee -a "$LOGFILE"

    # CPU stats (if available)
    if command -v mpstat &> /dev/null; then
        echo "== CPU Stats ==" | tee -a "$LOGFILE"
        mpstat 1 1 | tee -a "$LOGFILE"
    else
        echo "== CPU Stats: mpstat not installed ==" | tee -a "$LOGFILE"
    fi

    # VMStat snapshot
    echo "== VMStat Snapshot ==" | tee -a "$LOGFILE"
    vmstat 1 2 | tail -n 2 | tee -a "$LOGFILE"

    echo "" | tee -a "$LOGFILE"

    # Wait time in seconds
    sleep 60
done
