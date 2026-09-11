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

PRIV_TOOL=""
SKIP_DEPS=false
for arg in "$@"; do
    case "$arg" in
        --sudo) PRIV_TOOL="sudo" ;;
        --run0) PRIV_TOOL="run0" ;;
        --skip-deps) SKIP_DEPS=true ;;
    esac
done


case "$PRIV_TOOL" in
    sudo)
        if command -v sudo &>/dev/null; then
            SUDO="sudo"
        elif ! $IS_MACOS && command -v run0 &>/dev/null; then
            warn "sudo not found, falling back to run0."
            SUDO="run0 --background="
        else
            die "sudo not found (requested via --sudo or config)."
        fi
        ;;
    run0)
        if $IS_MACOS; then
            SUDO="sudo"
        elif command -v run0 &>/dev/null; then
            SUDO="run0 --background="
        elif command -v sudo &>/dev/null; then
            warn "run0 not found, falling back to sudo."
            SUDO="sudo"
        else
            die "run0 not found (requested via --run0 or config)."
        fi
        ;;
    *)
        if $IS_MACOS; then
            SUDO="sudo"
        elif command -v sudo &>/dev/null; then
            SUDO="sudo"
        elif command -v run0 &>/dev/null; then
            SUDO="run0 --background="
        else
            die "Neither sudo nor run0 found. Install one and re-run."
        fi
        ;;
esac

ensure_privilege() {
    if [[ "$SUDO" == "sudo" ]]; then
        $SUDO -v || die "Administrator authorization was cancelled or failed."
    else
        $SUDO true || die "Administrator authorization was cancelled or failed."
    fi
}

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

    if $SKIP_DEPS; then
        die "Python 3.10+ is required but not found, and --skip-deps was specified.\nPlease install Python 3.10+ manually and re-run."
    fi

    warn "Python 3.10+ not found, installing..."
    case "$1" in
        macos)
            die "Python 3.10+ not found. Install it via 'brew install python@3.13' or from https://www.python.org/downloads/macos/ and re-run this script."
            ;;
        apt)
            if grep -qi "ubuntu" /etc/os-release 2>/dev/null; then
                $SUDO apt-get install -y -qq software-properties-common >/dev/null
                $SUDO add-apt-repository -y ppa:deadsnakes/ppa >/dev/null
                $SUDO apt-get update -qq >/dev/null
            fi
            local best=""
            for v in 3.14 3.13 3.12 3.11 3.10; do
                if apt-get install -y -qq --dry-run "python${v}" "python${v}-venv" >/dev/null 2>&1; then
                    best="$v"; break
                fi
            done
            [[ -n "$best" ]] || die "No Python 3.10+ package found in apt repos."
            $SUDO apt-get install -y -qq "python${best}" "python${best}-venv" >/dev/null \
                || die "Failed to install python${best}."
            ;;
        dnf)
            $SUDO dnf install -y -q python3 python3-pip >/dev/null \
                || die "Failed to install Python via dnf."
            ;;
        yum)
            $SUDO yum install -y -q python3 python3-pip >/dev/null \
                || die "Failed to install Python via yum."
            ;;
        pacman)
            $SUDO pacman -Sy --noconfirm --quiet python >/dev/null \
                || die "Failed to install Python via pacman."
            ;;
        zypper)
            $SUDO zypper install -y --quiet python3 python3-pip >/dev/null \
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
    if $SKIP_DEPS; then
        info "Skipping package manager dependency installation (--skip-deps)."
        local missing=()
        command -v python3 &>/dev/null || missing+=("python3")
        if ! $LOCAL_MODE; then
            command -v unzip &>/dev/null || missing+=("unzip")
            { command -v wget &>/dev/null || command -v curl &>/dev/null; } \
                || missing+=("wget or curl")
        fi
        if [[ ${#missing[@]} -gt 0 ]]; then
            echo ""
            warn "Missing required tools with --skip-deps enabled:"
            for pkg in "${missing[@]}"; do info "  · $pkg"; done
            echo ""
            die "Missing required tools. Install them manually or run without --skip-deps."
        fi
        ok "Required tools present."
        return
    fi

    local py
    py="$(find_python_executable)"
    local need_python_venv=true
    if [[ -n "$py" ]] && "$py" -c "import venv, ensurepip" &>/dev/null; then
        need_python_venv=false
    fi

    local need_unzip=true
    if $LOCAL_MODE || command -v unzip &>/dev/null; then
        need_unzip=false
    fi

    local need_downloader=true
    if $LOCAL_MODE || command -v curl &>/dev/null || command -v wget &>/dev/null; then
        need_downloader=false
    fi

    if ! $need_python_venv && ! $need_unzip && ! $need_downloader; then
        ok "System dependencies already satisfied."
        return 0
    fi

    info "Installing system dependencies..."
    case "$1" in
        apt)
            local to_install=()
            if $need_python_venv; then
                to_install+=("python3-venv" "python3-pip")
            fi
            if $need_unzip; then
                to_install+=("unzip")
            fi
            if $need_downloader; then
                to_install+=("curl" "wget")
            fi
            if [[ ${#to_install[@]} -gt 0 ]]; then
                $SUDO env DEBIAN_FRONTEND=noninteractive apt-get update -qq >/dev/null
                $SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends "${to_install[@]}" >/dev/null
            fi
            ;;
        dnf)
            local to_install=()
            if $need_python_venv; then
                to_install+=("python3-pip")
            fi
            if $need_unzip; then
                to_install+=("unzip")
            fi
            if $need_downloader; then
                to_install+=("curl" "wget")
            fi
            if [[ ${#to_install[@]} -gt 0 ]]; then
                $SUDO dnf install -y -q "${to_install[@]}" >/dev/null
            fi
            ;;
        yum)
            local to_install=()
            if $need_python_venv; then
                to_install+=("python3-pip")
            fi
            if $need_unzip; then
                to_install+=("unzip")
            fi
            if $need_downloader; then
                to_install+=("curl" "wget")
            fi
            if [[ ${#to_install[@]} -gt 0 ]]; then
                $SUDO yum install -y -q "${to_install[@]}" >/dev/null
            fi
            ;;
        pacman)
            local to_install=()
            if $need_python_venv; then
                to_install+=("python" "python-pip")
            fi
            if $need_unzip; then
                to_install+=("unzip")
            fi
            if $need_downloader; then
                to_install+=("curl" "wget")
            fi
            if [[ ${#to_install[@]} -gt 0 ]]; then
                $SUDO pacman -Sy --noconfirm --quiet "${to_install[@]}" >/dev/null
            fi
            ;;
        zypper)
            local to_install=()
            if $need_python_venv; then
                to_install+=("python3-pip")
            fi
            if $need_unzip; then
                to_install+=("unzip")
            fi
            if $need_downloader; then
                to_install+=("curl" "wget")
            fi
            if [[ ${#to_install[@]} -gt 0 ]]; then
                $SUDO zypper install -y --quiet "${to_install[@]}" >/dev/null
            fi
            ;;
        macos)
            local missing=()
            if $need_unzip; then missing+=("unzip"); fi
            if $need_downloader; then missing+=("curl"); fi
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
            if $need_python_venv; then missing+=("python3-venv"); fi
            if $need_unzip; then missing+=("unzip"); fi
            if $need_downloader; then missing+=("curl or wget"); fi
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

    $SUDO sh -c "mkdir -p '$INSTALL_DIR' && chown -R '$CURRENT_USER:$CURRENT_GROUP' '$INSTALL_DIR'"

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

    rm -rf "$SRC_DIR" 2>/dev/null || $SUDO rm -rf "$SRC_DIR"
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
    local tmp
    tmp="$(mktemp)"
    cat > "$tmp" <<EOF
#!/usr/bin/env bash
exec "$VENV_PYTHON" "$SRC_DIR/zentune.py" "\$@"
EOF
    $SUDO sh -c "cp '$tmp' '$BIN_WRAPPER' && chmod +x '$BIN_WRAPPER'"
    rm -f "$tmp"
    [[ -x "$BIN_WRAPPER" ]] || die "Failed to install launcher at $BIN_WRAPPER"
    ok "Launcher installed: $BIN_WRAPPER"
}

daemon_is_installed() {
    $HAS_SERVICE_MANAGER && [[ -f "$SERVICE_FILE" ]]
}

restart_daemon() {
    $HAS_SERVICE_MANAGER || return 0
    info "Restarting daemon..."
    local tool_name="sudo"; [[ "$SUDO" == run0* ]] && tool_name="run0"
    if $IS_MACOS; then
        $SUDO launchctl kickstart -k "system/${SERVICE_LABEL}" \
            && ok "Daemon restarted." \
            || warn "Could not restart daemon, run: sudo launchctl kickstart -k system/${SERVICE_LABEL}"
    else
        $SUDO sh -c "systemctl daemon-reload && systemctl restart '$SERVICE_NAME'" \
            && ok "Daemon restarted." \
            || warn "Could not restart daemon, run: $tool_name systemctl status $SERVICE_NAME"
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

    ensure_privilege

    if $HAS_SERVICE_MANAGER && [[ -f "$SERVICE_FILE" ]]; then
        info "Removing daemon service..."
        if $IS_MACOS; then
            $SUDO launchctl bootout "system/${SERVICE_LABEL}" 2>/dev/null || true
            $SUDO rm -f "$SERVICE_FILE"
        else
            $SUDO sh -c "systemctl stop '$SERVICE_NAME' 2>/dev/null || true; systemctl disable '$SERVICE_NAME' 2>/dev/null || true; rm -f '$SERVICE_FILE'; systemctl daemon-reload 2>/dev/null || true"
        fi
        ok "Daemon service removed."
    else
        info "No daemon service to remove."
    fi

    local to_remove=()
    [[ -e "$BIN_WRAPPER" ]] && to_remove+=("$BIN_WRAPPER")
    [[ -d "$INSTALL_DIR" ]] && to_remove+=("$INSTALL_DIR")
    to_remove+=("/run/zentune.sock" "/run/zentune_daemon.lock")

    $SUDO rm -rf "${to_remove[@]}" 2>/dev/null || true
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
        local tool_name="sudo"; [[ "$SUDO" == run0* ]] && tool_name="run0"
        echo -e "    ${_B}$tool_name $VENV_PYTHON $SRC_DIR/Assets/daemon/daemon.py${_R}"
        echo ""
        if ! $IS_MACOS; then
            info "For OpenRC / runit / s6 service examples, see the wiki:"
            info "https://github.com/HorizonUnix/ZenTune/wiki/Linux-Installation"
            echo ""
        fi
    fi
}

main() {
    for arg in "$@"; do
        case "$arg" in
            --uninstall|-u)
                uninstall
                return
                ;;
            --help|-h)
                echo "Usage: bash install.sh [--local] [--skip-deps] [--uninstall] [--sudo|--run0]"
                echo "  (no args)      Install or update ZenTune from the latest GitHub release."
                echo "  --local        Install from this local checkout instead of downloading a release (for testing)."
                echo "  --skip-deps    Skip package manager dependency installation if already present."
                echo "  --uninstall    Remove ZenTune (service, launcher, and files)."
                echo "  --sudo         Force sudo for privileged commands, even if run0 is also present."
                echo "  --run0         Force run0 for privileged commands, even if sudo is also present."
                return
                ;;
            --local)
                LOCAL_MODE=true
                ;;
            --skip-deps)
                SKIP_DEPS=true
                ;;
        esac
    done

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

    ensure_privilege
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
