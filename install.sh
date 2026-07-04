#!/usr/bin/env bash
set -euo pipefail

IS_MACOS=false
[[ "$(uname -s)" == "Darwin" ]] && IS_MACOS=true

INSTALL_DIR="/opt/zentune"
VENV_DIR="$INSTALL_DIR/venv"
VENV_PYTHON="$VENV_DIR/bin/python3"
SRC_DIR="$INSTALL_DIR/src"
BIN_WRAPPER="/usr/local/bin/zentune"
if $IS_MACOS; then
    SERVICE_LABEL="com.horizonunix.zentune"
    SERVICE_FILE="/Library/LaunchDaemons/${SERVICE_LABEL}.plist"
else
    SERVICE_NAME="zentune.service"
    SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME"
fi
RELEASE_URL="https://github.com/HorizonUnix/ZenTune/releases/latest/download/ZenTune.zip"
TMP_DIR="$(mktemp -d)"

LOCAL_MODE=false
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
LOCAL_SRC_DIR="$SCRIPT_DIR/ZenTune"

_R='\033[0m'; _B='\033[1m'; _D='\033[2m'; _G='\033[32m'; _Y='\033[33m'; _E='\033[31m'

info() { echo -e "  ${_D}· $*${_R}"; }
ok()   { echo -e "  ${_G}✓${_R} $*"; }
warn() { echo -e "  ${_Y}!${_R} $*"; }
die()  { echo -e "\n  ${_E}✗${_R} $*\n"; exit 1; }
hr()   { echo -e "  ${_D}$(printf '─%.0s' {1..58})${_R}"; }

trap '[[ -n "$TMP_DIR" && ( "$TMP_DIR" == /tmp/* || "$TMP_DIR" == /var/tmp/* ) ]] && rm -rf -- "$TMP_DIR"' EXIT

[[ $EUID -eq 0 ]] && die "Do not run as root, run as your normal user:  bash install.sh"

CURRENT_USER="$(whoami)"
CURRENT_GROUP="$(id -gn)"
HAS_SERVICE_MANAGER=false
if $IS_MACOS; then
    HAS_SERVICE_MANAGER=true
else
    command -v systemctl &>/dev/null && HAS_SERVICE_MANAGER=true
fi

resolve_release_tag() {
    local tag=""
    if command -v curl &>/dev/null; then
        tag="$(curl -fsSL -o /dev/null -w '%{url_effective}' \
            "https://github.com/HorizonUnix/ZenTune/releases/latest" 2>/dev/null \
            | sed 's|.*/tag/||')" || true
    elif command -v wget &>/dev/null; then
        tag="$(wget -q --server-response --spider \
            "https://github.com/HorizonUnix/ZenTune/releases/latest" 2>&1 \
            | awk '/Location:/{print $2}' | tail -1 | sed 's|.*/tag/||')" || true
    fi
    echo "${tag:-latest}"
}

detect_pm() {
    if   $IS_MACOS; then echo "macos"
    elif command -v apt-get &>/dev/null; then echo "apt"
    elif command -v dnf     &>/dev/null; then echo "dnf"
    elif command -v yum     &>/dev/null; then echo "yum"
    elif command -v pacman  &>/dev/null; then echo "pacman"
    elif command -v zypper  &>/dev/null; then echo "zypper"
    else echo "unknown"
    fi
}

ensure_python310() {
    local py=""
    for candidate in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
        if command -v "$candidate" &>/dev/null; then
            if "$candidate" -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" 2>/dev/null; then
                py="$candidate"
                break
            fi
        fi
    done

    if [[ -n "$py" ]]; then
        ok "Python: $($py --version)"
        return
    fi

    warn "Python 3.10+ not found, installing..."
    case "$1" in
        macos)
            die "Python 3.10+ not found. Install it via 'brew install python@3.13' or from https://www.python.org/downloads/macos/ and re-run this script."
            ;;
        apt)
            if grep -qi "ubuntu" /etc/os-release 2>/dev/null; then
                sudo apt-get install -y -qq software-properties-common &>/dev/null
                sudo add-apt-repository -y ppa:deadsnakes/ppa &>/dev/null
                sudo apt-get update -qq &>/dev/null
            fi
            local best=""
            for v in 3.14 3.13 3.12 3.11 3.10; do
                if sudo apt-get install -y -qq --dry-run "python${v}" "python${v}-venv" &>/dev/null; then
                    best="$v"; break
                fi
            done
            [[ -n "$best" ]] || die "No Python 3.10+ package found in apt repos."
            sudo apt-get install -y -qq "python${best}" "python${best}-venv" &>/dev/null \
                || die "Failed to install python${best}."
            ;;
        dnf)
            sudo dnf install -y -q python3 python3-pip &>/dev/null \
                || die "Failed to install Python via dnf."
            ;;
        yum)
            sudo yum install -y -q python3 python3-pip &>/dev/null \
                || die "Failed to install Python via yum."
            ;;
        pacman)
            sudo pacman -Sy --noconfirm --quiet python &>/dev/null \
                || die "Failed to install Python via pacman."
            ;;
        zypper)
            sudo zypper install -y --quiet python3 python3-pip &>/dev/null \
                || die "Failed to install Python via zypper."
            ;;
        unknown)
            die "Python 3.10+ is required but not found and cannot be installed automatically.\nInstall it with your distro's package manager and re-run."
            ;;
    esac

    for candidate in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
        if command -v "$candidate" &>/dev/null; then
            if "$candidate" -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" 2>/dev/null; then
                ok "Python: $($candidate --version)"
                return
            fi
        fi
    done

    die "Could not install Python 3.10+. Install it manually and re-run."
}

install_deps() {
    info "Installing system dependencies..."
    case "$1" in
        apt)
            export DEBIAN_FRONTEND=noninteractive
            sudo apt-get update -qq &>/dev/null
            sudo apt-get install -y -qq --no-install-recommends \
                python3 python3-venv python3-pip \
                wget unzip curl &>/dev/null
            ;;
        dnf)
            sudo dnf install -y -q \
                python3 python3-pip \
                wget unzip curl &>/dev/null
            ;;
        yum)
            sudo yum install -y -q \
                python3 python3-pip \
                wget unzip curl &>/dev/null
            ;;
        pacman)
            sudo pacman -Sy --noconfirm --quiet \
                python python-pip \
                wget unzip curl &>/dev/null
            ;;
        zypper)
            sudo zypper install -y --quiet \
                python3 python3-pip \
                wget unzip curl &>/dev/null
            ;;
        macos)
            local missing=()
            command -v unzip &>/dev/null || missing+=("unzip")
            command -v curl  &>/dev/null || missing+=("curl")
            if [[ ${#missing[@]} -gt 0 ]]; then
                echo ""
                warn "Missing required tools. Install them and re-run:"
                for pkg in "${missing[@]}"; do info "  · $pkg"; done
                echo ""
                die "Missing required tools."
            fi
            ok "Required tools already present."
            ;;
        unknown)
            local missing=()
            command -v unzip     &>/dev/null || missing+=("unzip")
            { command -v wget &>/dev/null || command -v curl &>/dev/null; } \
                || missing+=("wget or curl")
            if [[ ${#missing[@]} -gt 0 ]]; then
                echo ""
                warn "No supported package manager found. Please install the following and re-run:"
                for pkg in "${missing[@]}"; do info "  · $pkg"; done
                echo ""
                die "Missing required tools."
            fi
            ok "Required tools already present."
            ;;
    esac
    ok "Dependencies installed."
}

download_release() {
    info "Downloading release..."
    local err="$TMP_DIR/dl.err"
    if command -v wget &>/dev/null; then
        local -a wget_progress_flag=()
        if ! wget --version 2>&1 | grep -q "GNU Wget2"; then
            wget_progress_flag+=(--show-progress)
        fi
        wget -q "${wget_progress_flag[@]}" -O "$TMP_DIR/release.zip" "$RELEASE_URL" 2>"$err" \
            || { cat "$err" >&2; die "Download failed."; }
    elif command -v curl &>/dev/null; then
        curl -fsSL -o "$TMP_DIR/release.zip" "$RELEASE_URL" 2>"$err" \
            || { cat "$err" >&2; die "Download failed."; }
    else
        die "Neither wget nor curl found."
    fi
    ok "Download complete."
}

install_files() {
    local src
    if $LOCAL_MODE; then
        info "Using local checkout at $LOCAL_SRC_DIR..."
        [[ -f "$LOCAL_SRC_DIR/zentune.py" ]] \
            || die "Local checkout not found at $LOCAL_SRC_DIR (run --local from inside the cloned repo)."
        src="$LOCAL_SRC_DIR"
    else
        info "Extracting files..."
        unzip -q "$TMP_DIR/release.zip" -d "$TMP_DIR/extracted" || die "Failed to extract archive."
        src="$(find "$TMP_DIR/extracted" -maxdepth 1 -mindepth 1 -type d | head -1)"
        [[ -d "$src" ]] || die "Could not find source directory in archive."
    fi

    sudo mkdir -p "$INSTALL_DIR"
    sudo chown "$CURRENT_USER:$CURRENT_GROUP" "$INSTALL_DIR"

    local bak="$TMP_DIR/preserve"
    mkdir -p "$bak"
    if [[ -f "$SRC_DIR/Assets/config.ini" ]]; then
        cp "$SRC_DIR/Assets/config.ini" "$bak/"
        info "Preserving existing settings."
    fi
    if [[ -f "$SRC_DIR/Assets/custom.json" ]]; then
        cp "$SRC_DIR/Assets/custom.json" "$bak/"
        info "Preserving custom presets."
    fi

    sudo rm -rf "$SRC_DIR"
    cp -r "$src" "$SRC_DIR"

    if [[ -f "$bak/config.ini" ]]; then
        cp "$bak/config.ini" "$SRC_DIR/Assets/config.ini"
    fi
    if [[ -f "$bak/custom.json" ]]; then
        cp "$bak/custom.json" "$SRC_DIR/Assets/custom.json"
    fi
    ok "Installed to $SRC_DIR"
}

find_python_executable() {
    command -v python3.14 || command -v python3.13 || command -v python3.12 || \
    command -v python3.11 || command -v python3.10 || command -v python3 || true
}

setup_venv() {
    info "Setting up Python environment..."
    local py
    py="$(find_python_executable)"
    [[ -n "$py" ]] || die "python3 not found."

    if [[ -d "$VENV_DIR" ]] && ! "$VENV_PYTHON" -c "" &>/dev/null; then
        warn "Broken venv, recreating..."
        rm -rf "$VENV_DIR"
    fi

    if [[ ! -d "$VENV_DIR" ]]; then
        "$py" -m venv --without-pip "$VENV_DIR" &>/dev/null \
            || "$py" -m venv "$VENV_DIR" &>/dev/null \
            || die "Failed to create virtual environment."
        "$VENV_PYTHON" -m ensurepip --upgrade --default-pip &>/dev/null || true
    fi

    "$VENV_PYTHON" -m pip install --quiet --no-cache-dir --upgrade pip &>/dev/null || true

    [[ -f "$SRC_DIR/requirements.txt" ]] || die "requirements.txt not found in $SRC_DIR"
    "$VENV_PYTHON" -m pip install --quiet --no-cache-dir -r "$SRC_DIR/requirements.txt" &>/dev/null \
        || die "Failed to install Python requirements."
    ok "Python environment ready."
}

set_permissions() {
    info "Setting permissions..."
    chmod +x "$SRC_DIR/zentune.py"
    ok "Permissions set."
}

install_wrapper() {
    info "Installing launcher..."
    sudo tee "$BIN_WRAPPER" > /dev/null <<EOF
#!/usr/bin/env bash
exec "$VENV_PYTHON" "$SRC_DIR/zentune.py" "\$@"
EOF
    sudo chmod +x "$BIN_WRAPPER"
    [[ -x "$BIN_WRAPPER" ]] || die "Failed to install launcher at $BIN_WRAPPER"
    ok "Launcher installed: $BIN_WRAPPER"
}

daemon_is_installed() {
    $HAS_SERVICE_MANAGER && [[ -f "$SERVICE_FILE" ]]
}

restart_daemon() {
    $HAS_SERVICE_MANAGER || return 0
    info "Restarting daemon..."
    if $IS_MACOS; then
        sudo launchctl kickstart -k "system/${SERVICE_LABEL}" \
            && ok "Daemon restarted." \
            || warn "Could not restart daemon, run: sudo launchctl kickstart -k system/${SERVICE_LABEL}"
    else
        sudo systemctl daemon-reload
        sudo systemctl restart "$SERVICE_NAME" \
            && ok "Daemon restarted." \
            || warn "Could not restart daemon, run: sudo systemctl status $SERVICE_NAME"
    fi
}

print_logo() {
    echo ""
    echo -e "${_B}███████╗███████╗███╗   ██╗████████╗██╗   ██╗███╗   ██╗███████╗"
    echo -e "╚══███╔╝██╔════╝████╗  ██║╚══██╔══╝██║   ██║████╗  ██║██╔════╝"
    echo -e "  ███╔╝ █████╗  ██╔██╗ ██║   ██║   ██║   ██║██╔██╗ ██║█████╗"
    echo -e " ███╔╝  ██╔══╝  ██║╚██╗██║   ██║   ██║   ██║██║╚██╗██║██╔══╝"
    echo -e "███████╗███████╗██║ ╚████║   ██║   ╚██████╔╝██║ ╚████║███████╗"
    echo -e "╚══════╝╚══════╝╚═╝  ╚═══╝   ╚═╝    ╚═════╝ ╚═╝  ╚═══╝╚══════╝${_R}"
    echo ""
}

print_banner() {
    local tag="$1"
    clear
    print_logo
    echo -e "  ${_D}Installer  ·  ${tag}${_R}"
    hr
    echo -e "  ${_D}Install  : $INSTALL_DIR${_R}"
    echo -e "  ${_D}Source   : $SRC_DIR${_R}"
    echo -e "  ${_D}Launcher : $BIN_WRAPPER${_R}"
    hr
    echo ""
}

uninstall() {
    clear
    print_logo
    echo -e "  ${_D}Uninstaller${_R}"
    hr
    echo ""
    warn "This will completely remove ZenTune:"
    info "Service  : $SERVICE_FILE"
    info "Launcher : $BIN_WRAPPER"
    info "Files    : $INSTALL_DIR"
    echo ""
    local reply=""
    if [[ "${ZENTUNE_ASSUME_YES:-}" == "1" ]]; then
        reply="y"
    elif [[ -e /dev/tty ]]; then
        read -rp "  Continue? [y/N] " reply </dev/tty || reply=""
    fi
    [[ "$reply" =~ ^[Yy]$ ]] || { echo ""; info "Cancelled."; echo ""; exit 0; }
    echo ""
    hr
    echo ""

    if $HAS_SERVICE_MANAGER && [[ -f "$SERVICE_FILE" ]]; then
        info "Removing daemon service..."
        if $IS_MACOS; then
            sudo launchctl bootout "system/${SERVICE_LABEL}" 2>/dev/null || true
            sudo rm -f "$SERVICE_FILE"
        else
            sudo systemctl stop "$SERVICE_NAME" 2>/dev/null || true
            sudo systemctl disable "$SERVICE_NAME" 2>/dev/null || true
            sudo rm -f "$SERVICE_FILE"
            sudo systemctl daemon-reload 2>/dev/null || true
        fi
        ok "Daemon service removed."
    else
        info "No daemon service to remove."
    fi

    if [[ -e "$BIN_WRAPPER" ]]; then
        sudo rm -f "$BIN_WRAPPER"
        ok "Launcher removed: $BIN_WRAPPER"
    else
        info "No launcher to remove."
    fi

    if [[ -d "$INSTALL_DIR" ]]; then
        sudo rm -rf "$INSTALL_DIR"
        ok "Files removed: $INSTALL_DIR"
    else
        info "No installation files to remove."
    fi

    sudo rm -f /run/zentune.sock /run/zentune_daemon.lock 2>/dev/null || true
    rm -f /tmp/zentune_tui.lock 2>/dev/null || true

    echo ""
    hr
    ok "ZenTune has been uninstalled."
    hr
    echo ""
}

run_setup() {
    echo ""
    hr
    ok "Installation complete."
    hr
    echo ""

    if daemon_is_installed; then
        restart_daemon
        echo ""
    fi

    echo -e "  ${_G}Done!${_R} Run the app with:"
    echo ""
    echo -e "    ${_B}$(basename "$BIN_WRAPPER")${_R}"
    echo ""

    if ! $HAS_SERVICE_MANAGER; then
        if $IS_MACOS; then
            warn "launchd not available, the daemon must be started manually."
        else
            warn "No systemd detected, the daemon must be started manually."
        fi
        info "Start the daemon (needs root) before running the app:"
        echo ""
        echo -e "    ${_B}sudo $VENV_PYTHON $SRC_DIR/Assets/daemon/daemon.py${_R}"
        echo ""
        if ! $IS_MACOS; then
            info "For OpenRC / runit / s6 service examples, see the wiki:"
            info "https://github.com/HorizonUnix/ZenTune/wiki/Linux-Installation"
            echo ""
        fi
    fi
}

main() {
    if [[ "${1:-}" == "--local" ]]; then
        LOCAL_MODE=true
        shift
    fi

    case "${1:-}" in
        --uninstall|-u)
            uninstall
            return
            ;;
        --help|-h)
            echo "Usage: bash install.sh [--local] [--uninstall]"
            echo "  (no args)      Install or update ZenTune from the latest GitHub release."
            echo "  --local        Install from this local checkout instead of downloading a release (for testing)."
            echo "  --uninstall    Remove ZenTune (service, launcher, and files)."
            return
            ;;
    esac

    local tag
    if $LOCAL_MODE; then
        tag="local checkout"
    else
        tag="$(resolve_release_tag)"
    fi
    print_banner "$tag"

    local pm
    pm="$(detect_pm)"

    if [[ "$pm" == "unknown" ]]; then
        warn "No supported package manager found, checking for required tools."
    else
        info "Package manager: $pm"
    fi

    if ! $HAS_SERVICE_MANAGER; then
        if $IS_MACOS; then
            warn "launchd not available, daemon will need to be started manually after install."
        else
            warn "systemd not found, daemon will need to be started manually after install."
        fi
        echo ""
    fi

    if daemon_is_installed; then
        echo ""
        warn "Existing installation found, updating files and restarting daemon."
    fi

    hr
    echo ""

    ensure_python310 "$pm"
    install_deps "$pm"
    if ! $LOCAL_MODE; then
        download_release
    fi
    install_files
    setup_venv
    set_permissions
    install_wrapper

    run_setup
}

main "$@"
