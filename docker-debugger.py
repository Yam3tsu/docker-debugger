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
DOCKER_SETUP = '''

# DOCKER SETUP BY docker-debugger
COPY debugging_bin /debugging_bin
RUN apt update
RUN apt install -y procps
RUN apt install -y gdbserver

'''
C_TEMPLATE = '''
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <fcntl.h>
#include <string.h>
#include <signal.h>

char* separator = "\\n-----------------------------------------------------------------------------------\\n";
int pid_counter = 0;
int gdbserver_pid = -1;

// Read from fd into buf untill the first occurence of terimnator
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

// Return the max pid of processes with name == bin_name
// The search begin from pid == start_pid (optimization purpose)
int find_max_pid(int start_pid, char* bin_name) {
    int max_pid = -1;
    int fd;
    char path[64];
    char command[256];
    for (int pid = start_pid; pid < 32768; pid++) {
        sprintf(path, "/proc/%d/cmdline", pid);
        fd = open(path, O_RDONLY);
        if (fd < 0)
            continue;
        int len = read_until(fd, command, 0);
        close(fd);
        if (len > 0 && strstr(command, bin_name) == command) {
            if (pid > max_pid)
                max_pid = pid;
        }
    }
    return max_pid;
}

// Return the min pid greater then start_pid of processes with name == bin_name
int find_min_pid (int start_pid, char* bin_name){
    char found = 0;
    int fd;
    char* path = malloc(0x50);
    int current;
    char* command = malloc(0x100);
    int res = -1;
    for (current = start_pid; found == 0 || current >= 327568; current++){
        sprintf(path, "/proc/%d/cmdline", current);
        fd = open(path, O_RDONLY);
        read_until(fd, command, 0);
        if (strstr(bin_name, command) == bin_name)
            res = current;
            break;
    }
    return res;
}


void run_gdb(int pid){
    pid_t debugger;
    int dev_null;
    char* debugger_args[5];

    if (gdbserver_pid > 0){
        if (kill(gdbserver_pid, SIGKILL) == 0){
            printf("Killed gdbserver (PID=%d)", gdbserver_pid);
        }
    }

    debugger = fork();
    if (debugger == 0){
        dev_null = open("/dev/null", O_RDWR);
        // dup2(dev_null, STDIN_FILENO);
        // dup2(dev_null, STDOUT_FILENO);
        close(dev_null);
        debugger_args[0] = "gdbserver";
        debugger_args[1] = ":1234";
        debugger_args[2] = "--attach";
        debugger_args[3] = malloc(0x10);
        sprintf(debugger_args[3], "%d", pid);
        debugger_args[4] = NULL;
        execvp("gdbserver", debugger_args);
    }
    else{
        gdbserver_pid = debugger;
        printf("Starting gdbserver (PID=%d)", gdbserver_pid);
    }
}

void print_argv(int argc, char** argv){
    for (int i = 0; i < argc; i++){
        printf("%s\\n", argv[i]);
    }

}

int main(int argc, char** argv){
    setbuf(stdout, NULL);
    print_argv(argc, argv);
    pid_t binary;
    int pid;
    char** binary_arguments;
    char* binary_name;
    int pipefd[2];

    if (argc < 2){
        perror("Not enough arguments!");
        exit(1);
    }
    binary_name = argv[1];
    binary_arguments = malloc( sizeof(char*) * (argc - 1) );
    for (int i = 2;i < argc; i++){
        binary_arguments[i - 2] = argv[i];
    }
    binary_arguments[argc - 2] = NULL;
    print_argv(argc - 2, binary_arguments);
    pipe(pipefd);
    binary = fork();
    if (binary == 0){
        // kill_gdb();
        // Child: redirect stdout and stderr to pipe
        close(pipefd[0]); // Close unused read end
        dup2(pipefd[1], STDOUT_FILENO);
        dup2(pipefd[1], STDERR_FILENO);
        close(pipefd[1]);
        execvp(binary_arguments[0], binary_arguments);
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
        pid = find_max_pid(pid_counter, binary_name);
        if (pid > pid_counter){
            pid_counter = pid;
            run_gdb(pid);
        }
    }
    fclose(stream);
    waitpid(binary, NULL, 0);
}
'''

# Routine to restore the backup if -r (--restore-backup) argument is passed
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

# Parse command line arguments
def arg_parser():
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

def add_verbose(arguments):
    new_args = []
    new_args.append(arguments[0])
    new_args.append("-d")
    new_args.append("-d")
    new_args = new_args + arguments[1:]
    return new_args


def add_compose_option(compose ,field, value):
    field_indentation = ""
    value_identation = ""
    is_value = False
    for line in compose.split("\n"):
        if is_value == True:
            value_identation = line[:line.find("-")]
            break
        if "ports:" in line:
            field_indentation = line[:line.find("ports:")]
            is_value = True

    new_compose = compose[:compose.find(f"{field_indentation}ports:")] +\
                  f"{field_indentation}{field}:\n{value_identation}- {value}\n" +\
                  compose[compose.find(f"{field_indentation}ports:"):]
    return new_compose
    

def main():
    arg_parser()

    # Check for Dockerfile
    dockerfile_path = os.path.join(DOCKER_PATH, "Dockerfile")
    compose_yml_path = os.path.join(DOCKER_PATH, "docker-compose.yml")
    compose_yaml_path = os.path.join(DOCKER_PATH, "docker-compose.yaml")

    if not os.path.isfile(dockerfile_path):
        print("Dockerfile not found in the specified path.")
        exit(1)

    # Rename docker-compose.yaml to docker-compose.yml
    if os.path.isfile(compose_yaml_path) and not os.path.isfile(compose_yml_path):
        os.rename(compose_yaml_path, compose_yml_path)

    if not os.path.isfile(compose_yml_path):
        print("docker-compose.yml not found in the specified path.")
        exit(1)

    # Open Dockerfile
    f = open(dockerfile_path, "r")
    dockerfile = f.read()
    f.close()

    # Check if Dockerfile has been patched yet
    if "# DOCKER SETUP BY docker-debugger" in dockerfile:
        print("Project alredy patched, restore the backup before using docker-debugger again")
        exit(1)

    # Check if Dockerfile use socat
    command = dockerfile[dockerfile.find("CMD "):]
    if not "socat" in command:
        print("This docker doesn't use socat...")
        exit(1)
    
    # Parse the command executed by Dockerfile and add verbose option to the socat command
    args_list = docker_cmd_arg_extract(command)
    args_list = add_verbose(args_list)

    # Write arguments to pass them as arguments in the new Dockerfile command
    cli_args = ""
    for elem in args_list:
        cli_args = cli_args + " " + elem

    # Generating debugging_bin
    f = open("debugging_bin.c", "w")
    f.write(C_TEMPLATE)
    f.close()
    out = subprocess.run(["gcc", "debugging_bin.c", "-o", "debugging_bin"], capture_output=True, text=True)

    # Write a backup of Dockerfile in Dockerfile.bak
    f = open(dockerfile_path + ".bak", "w")
    f.write(dockerfile)
    f.close()

    # patch Dockerfile
    patched_command = f"CMD /debugging_bin {BIN_PATH} {cli_args}"
    nuovo = dockerfile.split("CMD")
    nuovo[0] = nuovo[0] + DOCKER_SETUP + "# OLD EXECUTION COMMAND\n" + "# CMD"
    nuovo[1] =  nuovo[1].replace("\n", "\n#") + "\n\n" + patched_command
    nuovo = "".join(nuovo)
    f = open("Dockerfile", "w")
    f.write(nuovo)
    f.close()

    # Write backup for docker-compose.yml in docker-compose.bak
    f = open(compose_yml_path, "r")
    docker_compose = f.read()
    f.close()
    f = open(compose_yml_path.replace("yml", "bak"), "w")
    f.write(docker_compose)
    f.close()

    # Patch docker-compose.yml
    nuovo = docker_compose.split("ports:")
    identation = nuovo[1].split("\n")[1]
    identation = identation[:identation.find("-")]
    nuovo[0] = nuovo[0] + "ports:\n"
    nuovo[1] = (identation + f"- {GDBSERVER_PORT}:{GDBSERVER_PORT}") + nuovo[1]
    nuovo = "".join(nuovo)
    nuovo = add_compose_option(nuovo, "cap_add", "SYS_PTRACE")
    nuovo = add_compose_option(nuovo, "security_opt", "seccomp=unconfined")
    f = open(compose_yml_path, "w")
    f.write(nuovo)
    f.close()

if __name__ == "__main__":
    main()