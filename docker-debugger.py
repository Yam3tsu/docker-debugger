#!/usr/bin/python3

import sys
import os

POSITIONAL_ARGUMENTS = 1
GDBSERVER_PORT = 1234
DOCKER_PATH = "./"
HELP = '''
Usage: docker-debugger /path/fo/binary/in/docker


OPTIONS:
    -r --restore-backup: restore the backups (Usable only if there are Dockerfile.bak and dokcer-compose.bak files)
    -u --docker-path: path to the Dokcerfile and docker-compose.yml (default: ./)
    -p --port: port where gdbserver will listen (default: 1234)
    -h --help: print this message
'''
BIN_PATH = ""
DEBUGGER_TEMPLATE = '''

sleep 1
PID=$(pgrep {BIN_NAME} | sort -n | tail -n 1)
gdbserver :{GDBSERVER_PORT} --attach $PID

'''
INIT_TEMPLATE = '''

/.debugger.sh &
{SOCAT_COMMAND}

'''
DOCKER_SETUP = '''

# DOCKER SETUP BY docker-debugger
COPY .init.sh /.init.sh
COPY .debugger.sh /.debugger.sh
RUN chmod +x /.init.sh
RUN chmod +x /.debugger.sh
RUN apt update
RUN apt install -y procps
RUN apt install -y gdbserver

'''


# BACKUP RESTORE ROUTINE
def restore():
    restored = False
    try:
        f1 = open("Dockerfile.bak", "r")
        f2 = open("docker-compose.bak", "r")
        dockerfile = f1.read()
        docker_compose = f2.read()
        f1.close()
        f2.close()
        f = open("Dockerfile", "w")
        f.write(dockerfile)
        f.close()
        f = open("docker-compose.yml", "w")
        f.write(docker_compose)
        f.close()
        print("Backup successfully restored")
        restored = True
        exit(0)
    except:
        if restored == True:
            exit()
        print("Backup restore failed")
        exit(1)

# PARSE COMMAND LINE ARGUMENTS
def argparser():
    global DOCKER_PATH, GDBSERVER_PORT, BIN_PATH
    if len(sys.argv) < 2:
        print(HELP)
        exit(1)
    positional_arguments = 0
    for i in range(1, len(sys.argv)):
        arg = sys.argv[i]

        if arg == "-h" or arg == "--help":
            print(HELP)
            exit()

        elif arg == "-r" or arg == "--restore-backup":
            restore()

        elif arg == "-u" or arg == "--docker-path":
            if (i + 1) >= len(sys.argv):
                print(HELP)
                exit(1)
            path = sys.argv[i + 1]
            if os.path.exists(path):
                DOCKER_PATH = path
            else:
                print("Invalid path!")
                exit(1)
        
        elif arg == "-p" or arg == "--port":
            if (i + 1) >= len(sys.argv):
                print(HELP)
                exit(1)
            port = sys.argv[i + 1]
            try:
                port = int(port)
            except:
                print("Port must be an integer!")
                exit(1)
            if port <= 0 or port > 65535:
                print("Port must be in range 1-65535")
                exit(1)
            GDBSERVER_PORT = port
        
        else:
            if positional_arguments >= POSITIONAL_ARGUMENTS:
                print(HELP)
                exit(1)
            if positional_arguments == 0:
                BIN_PATH = arg
            positional_arguments = positional_arguments + 1


def main():
    argparser()

    # Check for Dockerfile
    dockerfile_path = os.path.join(DOCKER_PATH, "Dockerfile")
    compose_yml_path = os.path.join(DOCKER_PATH, "docker-compose.yml")
    compose_yaml_path = os.path.join(DOCKER_PATH, "docker-compose.yaml")

    if not os.path.isfile(dockerfile_path):
        print("Dockerfile not found in the specified path.")
        exit(1)

    if os.path.isfile(compose_yaml_path) and not os.path.isfile(compose_yml_path):
        # Rename docker-compose.yaml to docker-compose.yml
        os.rename(compose_yaml_path, compose_yml_path)

    if not os.path.isfile(compose_yml_path):
        print("docker-compose.yml not found in the specified path.")
        exit(1)

    # OPEN Dockerfile
    f = open(dockerfile_path, "r")
    dockerfile = f.read()
    f.close()

    # CHECK IF DOCKER IS ALREDY PATCHED
    if "# DOCKER SETUP BY docker-debugger" in dockerfile:
        print("Project alredy patched, restore the backup before using docker-debugger again")
        exit(1)

    # CHECK IF DOCKER USE SOCAT
    command = dockerfile[dockerfile.find("CMD"):]
    if not "socat" in command:
        print("This docker doesn't use socat...")
        exit(1)

    # RETRIVE SOCAT COMMAND
    command = command[command.find("EXEC:") + 5:].replace("\"", "")
    init = INIT_TEMPLATE.format(SOCAT_COMMAND=command)
    debugger = DEBUGGER_TEMPLATE.format(BIN_NAME = BIN_PATH.split("/")[-1], GDBSERVER_PORT = GDBSERVER_PORT)

    # WRITE .init
    f = open("./.init.sh", "w")
    f.write(init)
    f.close()

    # WRITE .debugger
    f = open("./.debugger.sh", "w")
    f.write(debugger)
    f.close()

    # WRITE A BACKUP OF Dockerfile IN Dockerfile.bak
    f = open(dockerfile_path + ".bak", "w")
    f.write(dockerfile)
    f.close()

    # PATCH Dockerfile
    nuovo = dockerfile.split("CMD")
    nuovo[0] = nuovo[0] + DOCKER_SETUP + "# OLD EXECUTION COMMAND\n" + "# CMD"
    nuovo[1] =  nuovo[1].replace("\n", "\n#") + "\n\nCMD" + nuovo[1].replace(BIN_PATH, "/.init.sh")
    nuovo = "".join(nuovo)
    f = open("Dockerfile", "w")
    f.write(nuovo)
    f.close()

    # WRITE BACKUP FOR docker-compose.yml IN docker-compose.bak
    f = open(compose_yml_path, "r")
    docker_compose = f.read()
    f.close()
    f = open(compose_yml_path.replace("yml", "bak"), "w")
    f.write(docker_compose)
    f.close()

    # PATCH docker-compose.yml
    nuovo = docker_compose.split("ports:")
    identation = nuovo[1].split("\n")[1]
    identation = identation[:identation.find("-")]
    nuovo[0] = nuovo[0] + "ports:\n"
    nuovo[1] = (identation + f"- {GDBSERVER_PORT}:{GDBSERVER_PORT}") + nuovo[1]
    nuovo = "".join(nuovo)
    f = open(compose_yml_path, "w")
    f.write(nuovo)
    f.close()

if __name__ == "__main__":
    main()