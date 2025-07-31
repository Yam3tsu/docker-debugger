# dokcer-debugger
This tool should help to debug binary hosted by a docker using socat. The goal of the tool is to help with the debugging part in pwn CTF.

The tool is a stand-alone. You just need to download **docker-debugger.py**


```
Usage: docker-debugger /path/to/challenge/binary/in/docker


OPTIONS:
    -r --restore-backup: restore the backups (Usable only if there are Dockerfile.bak and dokcer-compose.bak files)
    -u --docker-path: path to the Dokcerfile and docker-compose.yml (default: ./)
    -p --port: port where gdbserver will listen (default: 1234)
    -h --help: print this message
```

Some example of challenge used as test cases are in the folder **test_env**

## Example

We use as example the challenge **cac**. Its Dockerfile and docker-compose.yaml are shown below:

```
# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
FROM ubuntu@sha256:5d070ad5f7fe63623cbb99b4fc0fd997f5591303d4b03ccce50f403957d0ddc4 as chroot

# ubuntu24 includes the ubuntu user by default
RUN /usr/sbin/userdel -r ubuntu && /usr/sbin/useradd --no-create-home -u 1000 user

COPY flag /
COPY chal /home/user/

FROM gcr.io/kctf-docker/challenge@sha256:9f15314c26bd681a043557c9f136e7823414e9e662c08dde54d14a6bfd0b619f

COPY --from=chroot / /chroot

COPY nsjail.cfg /home/user/

CMD socat \
      TCP-LISTEN:1337,reuseaddr,fork \
      EXEC:"kctf_pow nsjail --config /home/user/nsjail.cfg -- /home/user/chal"

```

```
services:
  cac:
    container_name: cac
    build: .
    restart: unless-stopped
    networks:
      - cac-net
    privileged: true
    ports:
      - "1337:1337"
    environment:
      POW_DIFFICULTY_SECONDS: "0"

networks:
  cac-net:
    driver: bridge 
```

The tool is effective even if socat doesn't directly run the challenge binary. In this case the path to be passed to the tool is ```/home/user/chal```. The path doesn't have to be the real path of the challenge inside the docker, but it has to be equal to the name of the proccess of the challenge. I choose this challenge as an example becouse inside the docker the challenge binary cannot be find at that path.

Running the tool using ```python3 docker-debugger /home/user/chal``` in the folder of the Dockerfile (and docker-compose*) will write the binary **debugging_bin** in that folder and patch Dockerfile and docker-compose

*The tool support extensions .yml and .yaml. In case of .yaml the tool will rename the file as .yml

The patch of the Dockerfile should install gdbserver and replace the socat command with a command which run debugging_bin:

```
# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
FROM ubuntu@sha256:5d070ad5f7fe63623cbb99b4fc0fd997f5591303d4b03ccce50f403957d0ddc4 as chroot

# ubuntu24 includes the ubuntu user by default
RUN /usr/sbin/userdel -r ubuntu && /usr/sbin/useradd --no-create-home -u 1000 user

COPY flag /
COPY chal /home/user/

FROM gcr.io/kctf-docker/challenge@sha256:9f15314c26bd681a043557c9f136e7823414e9e662c08dde54d14a6bfd0b619f

COPY --from=chroot / /chroot

COPY nsjail.cfg /home/user/



# DOCKER SETUP BY docker-debugger
COPY debugging_bin /debugging_bin
RUN apt update
RUN apt install -y gdbserver

# OLD EXECUTION COMMAND
# CMD socat \
#      TCP-LISTEN:1337,reuseaddr,fork \
#      EXEC:"kctf_pow nsjail --config /home/user/nsjail.cfg -- /home/user/chal"
#

CMD /debugging_bin /home/user/chal  socat -d -d TCP-LISTEN:1337,reuseaddr,fork EXEC:"kctf_pow nsjail --config /home/user/nsjail.cfg -- /home/user/chal"
```

The patch to the docker-compose should add options which allow debugging inside the docker (some CTF gives dockers which doesn't allow for debugging by default) and expose the port for the gdbserver.

```
services:
  cac:
    container_name: cac
    build: .
    restart: unless-stopped
    networks:
      - cac-net
    privileged: true
    cap_add:
      - SYS_PTRACE
    security_opt:
      - seccomp=unconfined
    ports:
      - 1234:1234
      - "1337:1337"
    environment:
      POW_DIFFICULTY_SECONDS: "0"

networks:
  cac-net:
    driver: bridge 
```

## debugging_bin.c
This file should start a proccess (using fork) which run the original command of the Dockerfile adding the verbose option for socat (-d -d). At the same time it listens for output from that proccess, each time it receives something it will check if a new instance of the challenge started, in that case it will attach gdbserver to it

## compiler.sh
It's a script which should compile **debugging_bin.c** and then update **docker-debugger.py** which contains the binary encoded in base64

## test.sh
This script tests the tool on all the challenges in test_env/. To test it the script will copy all the challenges in /tmp/docker_debugger/ and tun the tool on them. To check if it worked test.sh will check if the netcat service will produce output and then if there is a gdbserver session open while a netcat session is open. If the challenge will not produce output at start the check will always be negative.