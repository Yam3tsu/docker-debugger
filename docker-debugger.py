#!/usr/bin/python3

import sys
import os
import subprocess

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
COPY debugging_bin /debugging_bin
RUN apt update
RUN apt install -y procps
RUN apt install -y gdbserver

'''
C_TEMPLATE = '''
// #define BINARY_ARGS {COMMAND}, NULL
#define DEBUG_ARGS "gdbserver", "gdbserver", ""
#define PID_OFFSET 0
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <fcntl.h>
#include <string.h>

char* bin_args[] = { {BINARY_ARGS}, NULL };
char* separator = "\\n-----------------------------------------------------------------------------------\\n";

int read_until(int fd, char* buf, char terminator){
    char car;
    int i = 0;
    do{
        if (read(fd, &car, 1) != 0){
            buf[i] = car;
            i = i + 1;
        }
        else
            break;
    }while(car != terminator);
    return i;
}

int find_pid (int start_pid ,char* bin_name){
    char found = 0;
    int fd;
    char* path = malloc(0x50);
    int current;
    char* command = malloc(0x100);
    for (current = start_pid;found == 0;current++){
        sprintf(path, "/proc/%d/cmdline", current);
        fd = open(path, O_RDONLY);
        read_until(fd, command, 0);
        if (strstr(bin_name, command) != NULL)
            found = 1;
    }
    return (current - 1);
}

int main(int argc, char** argv){
    setbuf(stdout, NULL);
    pid_t binary, debugger;
    int pid;
    char* dbg_args[] = {"gdbserver" ,":1234", "--attach", malloc(20), NULL};
    int pipefd[2];
    pipe(pipefd);

    binary = fork();
    if (binary == 0){
        // Child: redirect stdout and stderr to pipe
        close(pipefd[0]); // Close unused read end
        dup2(pipefd[1], STDOUT_FILENO);
        dup2(pipefd[1], STDERR_FILENO);
        close(pipefd[1]);
        execvp(bin_args[0], bin_args);
        perror("Binary execution failed!");
        exit(1);
    }
    close(pipefd[1]); // Parent: close unused write end
    // Now pipefd[0] can be used to read output from binary
    FILE *stream = fdopen(pipefd[0], "r");
    if (stream == NULL) {
        perror("fdopen failed");
        exit(1);
    }
    setbuf(stream, NULL);
    char buffer[1024];
    while (fgets(buffer, sizeof(buffer), stream) != NULL) {
        // Process the output as needed
        printf("%s%s%s", separator, buffer, separator);
    }
    fclose(stream);
    waitpid(binary, NULL, 0);
}
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


# PARSE ARGUMENTS FROM THE COMMAND RUNNING ON DOCKER (socat)
def docker_cmd_arg_extract(command):
    # PUT ALL IN ONE LINE IF COMMAND IS MULTILINE
    inline_command = command.split("\\")
    for i in range(len(inline_command)):
        inline_command[i] = inline_command[i].strip() + " "
    inline_command = "".join(inline_command)

    command_args = inline_command[len("CMD socat "):]
    args_list = ["socat"]
    new_arg = ""
    in_string = False
    for car in command_args:
        if car == " " and in_string == False:
            args_list.append(new_arg)
            new_arg = ""
            continue
        elif car == '"':
            in_string = not in_string
        new_arg = new_arg + car
    if new_arg != "":
        args_list.append(new_arg)
    return args_list


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
    command = dockerfile[dockerfile.find("CMD "):]
    if not "socat" in command:
        print("This docker doesn't use socat...")
        exit(1)
    
    # PARSE args_list TO USE IT IN THE C_TEMPLATE
    args_list = docker_cmd_arg_extract(command)
    args = str(args_list)[1:-1].split(", ")
    for i in range(len(args)):
        args[i] = '"' + args[i][1:-1].replace('"', '\\"') + '", '
    args[-1] = args[-1][:-2]
    args = "".join(args)

    # WRITING AND COMPILING debugging_bin
    debugging_bin_source = C_TEMPLATE.replace("{BINARY_ARGS}", args)
    f = open("debugging_bin.c", "w")
    f.write(debugging_bin_source)
    f.close()
    out = subprocess.run(["gcc", "debugging_bin.c", "-o", "debugging_bin"], capture_output=True, text=True)

    # WRITE A BACKUP OF Dockerfile IN Dockerfile.bak
    f = open(dockerfile_path + ".bak", "w")
    f.write(dockerfile)
    f.close()

    # PATCH Dockerfile
    patched_command = "CMD /debugging_bin"
    nuovo = dockerfile.split("CMD")
    nuovo[0] = nuovo[0] + DOCKER_SETUP + "# OLD EXECUTION COMMAND\n" + "# CMD"
    nuovo[1] =  nuovo[1].replace("\n", "\n#") + "\n\n" + patched_command
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