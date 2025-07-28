#define BINARY_ARGS "./prob", NULL
#define DEBUG_ARGS "gdbserver", "gdbserver", ""
#define PID_OFFSET 0
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <fcntl.h>
#include <string.h>

char* bin_args[] = {BINARY_ARGS};

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
    pid_t binary, debugger;
    int pid;
    char* dbg_args[] = {"gdbserver" ,":1234", "--attach", malloc(20), NULL};

    binary = fork();
    if (binary == 0){
        execvp(bin_args[0], bin_args);
        perror("Binary execution failed!");
    }
    sleep(1);
    debugger = fork();
    if (debugger == 0){
        int null_fd = open("/dev/null", O_RDWR);
        if (null_fd < 0) {
            perror("open /dev/null");
            exit(1);
        }
        pid = find_pid(binary, bin_args[0]);
        sprintf(dbg_args[3], "%d", pid);
        printf("Binary PID: %d, UID: %d\n", binary, getuid());

        dup2(null_fd, STDIN_FILENO);
        dup2(null_fd, STDOUT_FILENO);
        execvp("gdbserver", dbg_args);
        perror("gdbserver execution failed!");
    }
    waitpid(binary, NULL, 0);
    waitpid(debugger, NULL, 0);
}