#!/bin/bash

# Colori
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

CHECK="${GREEN}✔${NC}"
CROSS="${RED}✖${NC}"

workdir=$(pwd)
test_dir="$workdir/test_env"
tmp_dir="/tmp/docker-debugger/"

cd $test_dir
# Iterate for each dir in $test_dir
for dir in */ ; do
    if [ ! -d "$dir" ]; then
        continue
    fi
    test_name="${dir%/}"
    echo -e "${CYAN}Checking ${YELLOW}$test_name${NC}..."
    mkdir -p "$tmp_dir"
    rm -rf "$tmp_dir$dir"
    cp -r $dir $tmp_dir
    cd $tmp_dir$dir
    cp $workdir/docker-debugger.py .
    echo -e "${CYAN}Running docker-debugger...${NC}"
    if [ "$test_name" = "cac" ]; then
        python3 docker-debugger.py /home/user/chal
    elif [ "$test_name" = "copy-in-out-system" ]; then
        python3 docker-debugger.py ./prob
    fi
    ports=$(grep -E '^\s*ports:' -A 2 "./docker-compose.yml" | grep -Eo '[0-9]+:[0-9]+' | awk -F: '{print $1}' | xargs)
    gdb_port=$(echo $ports | awk '{print $1}')
    socat_port=$(echo $ports | awk '{print $2}')
    echo -e "${CYAN}Starting docker compose...${NC}"
    docker compose up --build -d > /dev/null 2>&1
    echo -e "${CHECK} docker compose up completed"
    echo -e "${YELLOW}Testing connection to socat service on port $socat_port...${NC}"
    output=$(timeout 3 bash -c "echo 'test' | nc localhost $socat_port")
    sleep 1
    if [ -n "$output" ]; then
        echo -e "${CHECK} Received output from socat service on port $socat_port"
    else
        echo -e "${CROSS} No output received from socat service on port $socat_port"
        echo -e "${CYAN}Stopping docker compose...${NC}"
        docker compose down > /dev/null 2>&1
        echo -e "${CHECK} docker compose down completed"
        cd $test_dir
        continue
    fi

    echo -e "${YELLOW}Testing gdbserver on port $gdb_port...${NC}"
    # Keep socat session active while testing gdbserver
    socat_pid=""
    timeout 5 nc localhost $socat_port >/dev/null &
    socat_pid=$!
    sleep 1
    gdb_output=$(timeout 3 bash -c "echo -ne '\$qSupported#37' | nc localhost $gdb_port")
    if [ -n "$gdb_output" ]; then
        echo -e "${CHECK} gdbserver is available on port $gdb_port"
    else
        echo -e "${CROSS} gdbserver is NOT available on port $gdb_port"
        echo -e "${CYAN}Stopping docker compose...${NC}"
        docker compose down > /dev/null 2>&1
        echo -e "${CHECK} docker compose down completed"
        cd $test_dir
        continue
    fi
    # Cleanup socat session if still running
    if [ -n "$socat_pid" ] && kill -0 $socat_pid 2>/dev/null; then
        kill $socat_pid
    fi

    echo -e "${CYAN}Stopping docker compose...${NC}"
    docker compose down > /dev/null 2>&1
    echo -e "${CHECK} docker compose down completed"
    cd $test_dir
done