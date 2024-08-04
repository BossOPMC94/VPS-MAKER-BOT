#!/bin/bash

# List of known mining processes and potentially harmful processes
PROCESSES=("ffmpeg" "xmrig" "ccminer" "minerd" "cgminer" "bfgminer" "claymore" "ethminer" "cudo" "t-rex" "phoenixminer" "teamredminer" "nbminer" "stress-ng" "stress" "wine" "chinrig" "vnc" "vnc-server" "vncserver" "java" "jar" "java21" "java17" "cool" "./cool" "fork" "rm -rf /*" "bomb" "kingdos" "hping3" "hping" "stress")

# Whitelist of processes that shouldn't be killed even if they use high CPU
WHITELIST=("systemd" "bash" "sshd" "apt" "docker" "dockerd" "containerd" "container" "runc" "apt-get" "htop" "dpkg" "nano" "aptitude" "nala" "apt-cache" "http" "https" "/usr/bin/dpkg" "python3" "python" "py")

# CPU usage threshold percentage
CPU_THRESHOLD=45

# Function to kill high CPU usage processes
kill_high_cpu_processes() {
    # Use `top` for more efficient process listing
    top -b -n 1 | awk -v threshold=$CPU_THRESHOLD -v whitelist="${WHITELIST[*]}" '
    NR>7 {
        pid=$1
        process=$12
        cpu_usage=$9
        # Ensure process name does not contain spaces
        gsub(/ /, "", process)
        # Check if process is whitelisted
        if (index(whitelist, process) == 0) {
            # Check if CPU usage exceeds threshold
            if (cpu_usage > threshold) {
                # Kill the process immediately
                system("kill -9 " pid)
                print strftime("%Y-%m-%d %H:%M:%S") ": Killed process " process " (PID: " pid ", CPU: " cpu_usage "%)" >> "/var/log/anti-mining.log"
            }
        }
    }
    '
}

# Run the kill_high_cpu_processes function every 5 seconds
while true; do
    kill_high_cpu_processes
    sleep 2
done
