#!/usr/bin/env bash
set -euo pipefail

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is not installed. Install it first, for example:"
  echo "  sudo apt update && sudo apt install -y python3 python3-venv python3-pip"
  exit 1
fi

if ! python3 -m venv --help >/dev/null 2>&1; then
  echo "The Python venv module is not available."
  echo "Install it with:"
  echo "  sudo apt update && sudo apt install -y python3-venv"
  exit 1
fi

echo "Creating virtual environment in .venv..."
python3 -m venv .venv

echo "Activating virtual environment..."
# shellcheck disable=SC1091
source .venv/bin/activate

echo "Upgrading pip..."
python -m pip install --upgrade pip

echo "Installing Python dependencies..."
python -m pip install -r requirements.txt

echo
echo "Setup complete."
echo "Activate later with: source .venv/bin/activate"
echo "Run the app with:     python app.py"
