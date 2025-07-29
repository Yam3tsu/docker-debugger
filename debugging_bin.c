#define BINARY_ARGS 'socat', 'TCP-LISTEN:1337,reuseaddr,fork', 'EXEC:"kctf_pow', 'nsjail', '--config', '/home/user/nsjail.cfg', '--', '/home/user/chal"', NULL
#define PID_OFFSET 0
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <fcntl.h>
#include <string.h>

char* bin_args[] = {BINARY_ARGS};
char* separator = "\n-----------------------------------------------------------------------------------\n";

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
    char buffer[1024];
    while (fgets(buffer, sizeof(buffer), stream) != NULL) {
        // Process the output as needed
        printf("%s%s%s", separator, buffer, separator);
    }
    fclose(stream);
    waitpid(binary, NULL, 0);
}