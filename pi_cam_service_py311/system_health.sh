#!/bin/bash

# File to store the logs
LOGFILE="$HOME/system_health.log"

while true; do
    # Create a timestamp
    TIMESTAMP="=== $(date '+%Y-%m-%d %H:%M:%S') ==="
    
    # Print to screen and file
    echo "$TIMESTAMP" | tee -a "$LOGFILE"

    echo "== Disk ==" | tee -a "$LOGFILE"
    df -h / | tee -a "$LOGFILE"

    echo "== Memory ==" | tee -a "$LOGFILE"
    free -h | tee -a "$LOGFILE"

    echo "== Load & Uptime ==" | tee -a "$LOGFILE"
    uptime | tee -a "$LOGFILE"

    echo "" | tee -a "$LOGFILE"

    # Wait 10 minutes before next check
    sleep 600
done
