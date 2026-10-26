#!/usr/bin/env bash
set -e

# Change directory to script location
cd "$(dirname "$0")"

SETUP_LOG="setup.log"
MARKER_FILE=".venv/.setup_ok"
REQ_FILE="requirements.txt"
FORCE_CPU=0
REINSTALL=0

# Parse arguments
for arg in "$@"; do
    case $arg in
        --cpu) FORCE_CPU=1 ;;
        --reinstall) REINSTALL=1 ;;
    esac
done

if [ "$REINSTALL" -eq 1 ]; then
    rm -f "$MARKER_FILE"
    echo "[Setup] Reinstall requested. Cache marker removed."
fi

# Locate Python 3.10+
PYTHON_BIN=""
if command -v python3 >/dev/null 2>&1 && python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1 && python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null; then
    PYTHON_BIN="python"
else
    echo "=============================================================================="
    echo "[ERROR] Python 3.10 or newer is required but was not found."
    echo "Install python3-venv and python3-pip using your distribution package manager."
    echo "=============================================================================="
    exit 1
fi

# Create venv if missing
if [ ! -f ".venv/bin/python" ]; then
    echo "[1/4] Creating virtual environment (.venv)..."
    "$PYTHON_BIN" -m venv .venv > "$SETUP_LOG" 2>&1
fi

CURRENT_REQ_HASH=$(sha256sum "$REQ_FILE" 2>/dev/null | awk '{print $1}' || shasum -a 256 "$REQ_FILE" | awk '{print $1}')
NEEDS_SETUP=0

if [ ! -f "$MARKER_FILE" ]; then
    NEEDS_SETUP=1
else
    STORED_HASH=$(cat "$MARKER_FILE" 2>/dev/null || echo "")
    if [ "$STORED_HASH" != "$CURRENT_REQ_HASH" ]; then
        NEEDS_SETUP=1
    fi
fi

if [ "$NEEDS_SETUP" -eq 1 ]; then
    echo "=============================================================================="
    echo "  First-Run Forensic Module Setup (Logging to setup.log)"
    echo "=============================================================================="
    > "$SETUP_LOG"

    echo "[1/4] Upgrading pip..."
    .venv/bin/python -m pip install --upgrade pip >> "$SETUP_LOG" 2>&1

    HAS_NVIDIA=0
    if command -v nvidia-smi >/dev/null 2>&1; then
        HAS_NVIDIA=1
    fi

    if [ "$FORCE_CPU" -eq 1 ]; then
        echo "[2/4] Installing PyTorch in CPU mode as requested..."
        .venv/bin/python -m pip install torch torchvision >> "$SETUP_LOG" 2>&1
    elif [ "$HAS_NVIDIA" -eq 1 ]; then
        echo "[2/4] NVIDIA GPU detected. Installing PyTorch with CUDA 12.8 support..."
        .venv/bin/python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128 >> "$SETUP_LOG" 2>&1
    else
        echo "[2/4] No NVIDIA GPU detected. Installing PyTorch in CPU mode..."
        .venv/bin/python -m pip install torch torchvision >> "$SETUP_LOG" 2>&1
    fi

    echo "[3/4] Installing requirements..."
    .venv/bin/python -m pip install -r "$REQ_FILE" >> "$SETUP_LOG" 2>&1

    echo "[4/4] Finalizing setup..."
    echo "$CURRENT_REQ_HASH" > "$MARKER_FILE"
    echo "[Setup Complete] All dependencies verified."
    echo ""
fi

# Launch application
exec .venv/bin/python launch.py "$@"
