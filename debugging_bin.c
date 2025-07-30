#define BINARY_ARGS 'socat', 'TCP-LISTEN:1337,reuseaddr,fork', 'EXEC:"kctf_pow nsjail --config /home/user/nsjail.cfg -- /home/user/chal"', NULL
#define PID_OFFSET 0
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <fcntl.h>
#include <string.h>
#include <signal.h>

// char* bin_args[] = {BINARY_ARGS};
char* separator = "\n-----------------------------------------------------------------------------------\n";
int pid_counter = 0;

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

void kill_gdb(){
    int pid = find_min_pid(pid_counter, "gdbserver");
    kill(pid, SIGKILL);
}

void run_gdb(int pid){
    pid_t debugger;
    int dev_null;
    char* debugger_args[5];
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
    waitpid(debugger, NULL, 0);
}

void print_argv(int argc, char** argv){
    for (int i = 0; i < argc; i++){
        printf("%s\n", argv[i]);
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
        // execvp(bin_args[0], bin_args);
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
        printf("%s%s%s", separator, buffer, separator);
        pid = find_max_pid(pid_counter, binary_name);
        if (pid > pid_counter){
            pid_counter = pid;
            printf("TROVATO PID DA ATTACCARE");
            run_gdb(pid);
        }
        else{
            printf("\nCERCATO SENZA SUCCESSO!\n");
        }
    }
    fclose(stream);
    waitpid(binary, NULL, 0);
}