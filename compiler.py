import subprocess
import base64
import re

CYAN='\033[0;36m'
RED='\033[0;31m'
GREEN='\033[0;32m'
NC="\033[0m"
CHECK=f"{GREEN}✔{NC}"
CROSS=f"{RED}✖{NC}"
BINARY_NAME = "debugging_bin"

print(f"{CYAN}Compiling {BINARY_NAME}...{NC}")
try:
    result = subprocess.run(["gcc", f"{BINARY_NAME}.c", "-o", f"{BINARY_NAME}"], check=True)
    print(f"{CHECK} {BINARY_NAME} compiled successfully!{NC}")
except:
    print(f"{CROSS}Compilation failed!")
    exit(1)

print(f"{CYAN}Updating docker-debugger.py...{NC}")
f = open(BINARY_NAME, "rb")
binary = f.read()
f.close()
f = open("docker-debugger.py", "r")
docker_debugger = f.read()
f.close()

updated_docker_debugger = re.sub(
    r'^(BINARY = )b".*"$',
    fr'\1b"{base64.b64encode(binary).decode()}"',
    docker_debugger,
    flags=re.MULTILINE)

print(updated_docker_debugger)

# f = open("docker-debugger.py", "w")
# f.write(updated_docker_debugger)
# f.close()
# print(f"{CHECK} docker-debugger.py updated successfully")