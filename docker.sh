#!/bin/bash

set -e

RESET="\033[0m"
BOLD="\033[1m"
DIM="\033[2m"

RED="\033[91m"
GREEN="\033[92m"
YELLOW="\033[93m"
BLUE="\033[94m"
MAGENTA="\033[95m"
CYAN="\033[96m"
WHITE="\033[97m"
GREY="\033[90m"

SYM_OK="${GREEN}✔${RESET}"
SYM_ERR="${RED}✖${RESET}"
SYM_WARN="${YELLOW}⚠${RESET}"
SYM_INFO="${CYAN}ℹ${RESET}"
SYM_ARROW="${CYAN}→${RESET}"
SYM_DASH="${GREY}·${RESET}"
SYM_BULLET="${MAGENTA}•${RESET}"
SYM_DOCKER="${BLUE}🐳${RESET}"

tw() {
    tput cols 2>/dev/null || echo 80
}

h1() {
    local msg="$1"
    local w
    w=$(tw)
    local i
    echo ""
    for ((i=0; i<w-2; i++)); do echo -n "─"; done
    echo ""
    echo -e "  ${BOLD}${CYAN}${msg}${RESET}"
    for ((i=0; i<w-2; i++)); do echo -n "─"; done
    echo ""
}

h2() {
    echo -e "\n  ${BOLD}${WHITE}$1${RESET}"
}

ok() {
    echo -e "  ${SYM_OK}  $*"
}

err() {
    echo -e "  ${SYM_ERR}  ${RED}$*${RESET}"
}

warn() {
    echo -e "  ${SYM_WARN}  ${YELLOW}$*${RESET}"
}

info() {
    echo -e "  ${SYM_INFO}  $*"
}

step() {
    echo -e "  ${SYM_DASH}  $*"
}

kv() {
    local key="$1"
    local val="$2"
    local kw="${3:-14}"
    echo -n "  "
    printf "%-14s" "$(echo -e "${GREY}${key}${RESET}")"
    echo -e " $val"
}

sep() {
    local w i
    w=$(tw)
    echo -n "  "
    for ((i=0; i<w-4; i++)); do echo -n "─"; done
    echo ""
}

install_docker() {
    h1 "Installing Docker"
    
    if command -v docker &> /dev/null; then
        info "Docker already installed: $(docker --version)"
        return 0
    fi
    
    if command -v apt-get &> /dev/null; then
        step "Using apt-get..."
        apt-get update
        
        step "Installing prerequisites..."
        apt-get install -y ca-certificates curl gnupg lsb-release
        
        step "Adding Docker GPG key..."
        mkdir -p /etc/apt/keyrings
        curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg 2>/dev/null || true
        
        step "Adding Docker repository..."
        local distro=$(lsb_release -cs 2>/dev/null || echo "bullseye")
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian ${distro} stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
        
        step "Installing Docker packages..."
        apt-get update
        apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
        
        ok "Docker installed successfully"
        
    elif command -v pacman &> /dev/null; then
        step "Using pacman..."
        pacman -S --noconfirm docker docker-compose
        systemctl enable docker
        systemctl start docker
        ok "Docker installed successfully"
        
    else
        err "Unsupported package manager. Please install Docker manually."
        exit 1
    fi
}

build_image() {
    h1 "Building Docker Image"
    
    if docker build --network=host -t mcub-userbot . 2>&1 | while read line; do
        echo -e "  ${SYM_DOCKER}  ${line}"
    done; then
        ok "Image built: mcub-userbot"
    else
        err "Build failed"
        exit 1
    fi
}

run_container() {
    h1 "Running Container"
    
    if docker ps -a --format '{{.Names}}' | grep -q "^mcub-userbot$"; then
        step "Removing existing container..."
        docker rm -f mcub-userbot >/dev/null 2>&1
    fi
    
    step "Creating container..."
    docker run -d \
        --name mcub-userbot \
        --network host \
        -v $(pwd)/data:/app/data \
        -v $(pwd)/config.json:/app/config.json:ro \
        -e MCUB_NO_WEB=0 \
        -e MCUB_PORT=8080 \
        -e MCUB_HOST=0.0.0.0 \
        --restart unless-stopped \
        mcub-userbot >/dev/null 2>&1
        
    ok "Container started: mcub-userbot"
    ok "Web panel: http://localhost:8080"
}

show_status() {
    h1 "Container Status"
    
    if docker ps --format '{{.Names}}' | grep -q "^mcub-userbot$"; then
        local status=$(docker inspect --format='{{.State.Status}}' mcub-userbot 2>/dev/null)
        
        kv "Name:" "${CYAN}mcub-userbot${RESET}"
        kv "Status:" "${GREEN}${status}${RESET}"
        kv "Web:" "${WHITE}http://localhost:8080${RESET}"
        sep
    else
        err "Container not running"
    fi
}

show_logs() {
    h1 "Container Logs"
    docker logs --tail 20 mcub-userbot 2>&1 || err "No logs available"
}

case "${1:-install}" in
    install)
        install_docker
        build_image
        run_container
        show_status
        ;;
    build)
        build_image
        ;;
    run)
        run_container
        ;;
    start)
        docker start mcub-userbot
        ok "Container started"
        ;;
    stop)
        docker stop mcub-userbot
        ok "Container stopped"
        ;;
    restart)
        docker restart mcub-userbot
        ok "Container restarted"
        ;;
    logs)
        show_logs
        ;;
    status)
        show_status
        ;;
    rebuild)
        build_image
        run_container
        show_status
        ;;
    *)
        h1 "MCUB Docker Manager"
        echo ""
        echo -e "  ${SYM_DOCKER}  ${BOLD}Usage:${RESET} ./docker.sh <command>"
        echo ""
        echo -e "  ${SYM_BULLET}  ${CYAN}install${RESET}   - Install Docker, build and run (default)"
        echo -e "  ${SYM_BULLET}  ${CYAN}build${RESET}    - Build Docker image"
        echo -e "  ${SYM_BULLET}  ${CYAN}run${RESET}      - Run container"
        echo -e "  ${SYM_BULLET}  ${CYAN}start${RESET}    - Start container"
        echo -e "  ${SYM_BULLET}  ${CYAN}stop${RESET}     - Stop container"
        echo -e "  ${SYM_BULLET}  ${CYAN}restart${RESET}  - Restart container"
        echo -e "  ${SYM_BULLET}  ${CYAN}logs${RESET}     - Show logs"
        echo -e "  ${SYM_BULLET}  ${CYAN}status${RESET}   - Show status"
        echo -e "  ${SYM_BULLET}  ${CYAN}rebuild${RESET}  - Rebuild and run"
        echo ""
        exit 1
        ;;
esac
