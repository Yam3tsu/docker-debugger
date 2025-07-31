#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <fcntl.h>
#include <string.h>
#include <signal.h>

char* separator = "\n-----------------------------------------------------------------------------------\n";
int pid_counter = 0;
pid_t gdbserver_pid = -1;

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

// Run gdbserver attached to pid
void run_gdb(int pid, int port){
    pid_t debugger;
    int dev_null;
    char* debugger_args[5];

    // If the previous gdbserver process is still running, kill it
    if (gdbserver_pid > 0){
        if (kill(gdbserver_pid, SIGKILL) == 0){
            printf("Killed gdbserver (PID=%d)", gdbserver_pid);
        }
    }

    debugger = fork();
    if (debugger == 0){
        debugger_args[0] = "gdbserver";
        // debugger_args[1] = ":1234";
        debugger_args[1] = malloc(0x10);
        debugger_args[2] = "--attach";
        debugger_args[3] = malloc(0x10);
        sprintf(debugger_args[3], "%d", pid);
        sprintf(debugger_args[1], ":%d", port);
        debugger_args[4] = NULL;
        execvp("gdbserver", debugger_args);
    }
    else{
        // Set the current gdbserver pid
        gdbserver_pid = debugger;
        printf("Starting gdbserver (PID=%d)", gdbserver_pid);
    }
}

int main(int argc, char** argv){
    setbuf(stdout, NULL);
    pid_t binary;
    int pid;
    char** binary_arguments;
    char* binary_name;
    int gdbserver_port = 0;
    int pipefd[2];

    if (argc < 2){
        perror("Not enough arguments!");
        exit(1);
    }

    // Parsing command line arguments
    binary_name = argv[1];
    gdbserver_port = atoi(argv[2]);
    if (gdbserver_port <= 0 || gdbserver_port > 65535){
        perror("Insert a valid port!");
        exit(1);
    }
    binary_arguments = malloc( sizeof(char*) * (argc - 2) );
    for (int i = 3;i < argc; i++){
        binary_arguments[i - 3] = argv[i];
    }
    binary_arguments[argc - 3] = NULL;

    // Use a pipe to capture the output of socat
    pipe(pipefd);
    binary = fork();
    if (binary == 0){
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
    
    // Each time is received output form socat check if a new process is started for the challenge
    // In that case attach gdbserver to it
    while (fgets(buffer, sizeof(buffer), stream) != NULL) {
        pid = find_max_pid(pid_counter, binary_name);
        if (pid > pid_counter){
            pid_counter = pid;
            run_gdb(pid, gdbserver_port);
        }
    }
    fclose(stream);
    waitpid(binary, NULL, 0);
}