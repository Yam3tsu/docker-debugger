#!/usr/bin/python3

import sys

GDBSERVER_PORT = 1234
HELP = '''
Usage: docker-debugger /path/fo/binary/in/docker [gdbserver port]

DEFAULT OPTIONS:
    gdbserver default port: 1234

OPTIONS:
    --restore-backup: restore the backups (Usable only if there are Dockerfile.bak and dokcer-compose.bak files)
'''


try:
    arg1 = sys.argv[1]
except:
    print(HELP)
    exit(1)

try:
    GDBSERVER_PORT = sys.argv[2]
except:
    pass

if arg1 == "-h" or arg1 == "--help":
    print(HELP)
    exit()

# BACKUP RESTORE ROUTINE
restored = False
if arg1 == "--restore-backup":
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


BIN_PATH = arg1

DBG_SH = f'''

sleep 1
PID=$(pgrep {BIN_PATH.split("/")[-1]} | sort -n | tail -n 1)
gdbserver :{GDBSERVER_PORT} --attach $PID

'''

INIT_SH = '''

/xxx-debugger.sh &
{SOCAT_COMMAND}

'''

DOCKER_SETUP = '''

# DOCKER SETUP BY docker-debugger
COPY xxx-init.sh /xxx-init.sh
COPY xxx-debugger.sh /xxx-debugger.sh
RUN chmod +x /xxx-init.sh
RUN chmod +x /xxx-debugger.sh
RUN apt update
RUN apt install -y procps
RUN apt install -y gdbserver

'''

# RETRIVE SOCAT COMMAND
f = open("Dockerfile", "r")
dockerfile = f.read()
f.close()

if "# DOCKER SETUP BY docker-debugger" in dockerfile:
    print("Project alredy patched, restore the backup before using docker-debugger again")
    exit(1)

command = dockerfile[dockerfile.find("CMD"):]
if not "socat" in command:
    print("This docker doesn't use socat...")
    exit(1)

command = command[command.find("EXEC:") + 5:].replace("\"", "")
INIT_SH = INIT_SH.format(SOCAT_COMMAND=command)

# WRITE xxx-init AND xxx-debugger
f = open("./xxx-init.sh", "w")
f.write(INIT_SH)
f.close()

f = open("./xxx-debugger.sh", "w")
f.write(DBG_SH)
f.close()

# WRITE A BACKUP OF Dockerfile
f = open("Dockerfile.bak", "w")
f.write(dockerfile)
f.close()

# PATCH Dockerfile
nuovo = dockerfile.split("CMD")
nuovo[0] = nuovo[0] + DOCKER_SETUP + "# OLD EXECUTION COMMAND\n" + "# CMD"
nuovo[1] =  nuovo[1].replace("\n", "\n#") + "\n\nCMD" + nuovo[1].replace(BIN_PATH, "/xxx-init.sh")
nuovo = "".join(nuovo)
f = open("Dockerfile", "w")
f.write(nuovo)
f.close()

# WRITE BACKUP FOR docker-compose.yml
f = open("docker-compose.yml", "r")
docker_compose = f.read()
f.close()
f = open("docker-compose.bak", "w")
f.write(docker_compose)
f.close()

# PATCH docker-compose.yml
nuovo = docker_compose.split("ports:")
identation = nuovo[1].split("\n")[1]
identation = identation[:identation.find("-")]
nuovo[0] = nuovo[0] + "ports:\n"
nuovo[1] = (identation + f"- {GDBSERVER_PORT}:{GDBSERVER_PORT}") + nuovo[1]
nuovo = "".join(nuovo)
f = open("docker-compose.yml", "w")
f.write(nuovo)
f.close()
