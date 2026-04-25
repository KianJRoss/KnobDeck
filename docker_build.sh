#!/bin/bash
# Simplified Docker build script for QMK firmware
# Based on QMK's util/docker_cmd.sh but without interactive mode

set -e

KEYBOARD="keychron/v1/ansi_encoder"
KEYMAP="raw_hid_menu"

echo "=========================================="
echo "Building QMK Firmware with Docker"
echo "=========================================="
echo "Keyboard: $KEYBOARD"
echo "Keymap: $KEYMAP"
echo ""

# Get the firmware directory (Windows-compatible path)
QMK_DIR=$(pwd -W 2>/dev/null || pwd)

echo "QMK Firmware Directory: $QMK_DIR"
echo "Pulling latest Docker image..."
echo ""

# Pull the latest image
docker pull ghcr.io/qmk/qmk_cli

echo ""
echo "Building firmware..."
echo ""

# Run the build (without -it for non-interactive)
docker run --rm \
	-w //qmk_firmware \
	-v "$QMK_DIR"://qmk_firmware \
	-e SKIP_GIT="$SKIP_GIT" \
	-e SKIP_VERSION="$SKIP_VERSION" \
	ghcr.io/qmk/qmk_cli \
	make "$KEYBOARD:$KEYMAP"

echo ""
echo "=========================================="
echo "Build Complete!"
echo "=========================================="
echo ""
echo "Firmware location:"
ls -lh .build/${KEYBOARD//\//_}_${KEYMAP}.bin 2>/dev/null || echo "Build may have failed - check output above"
echo ""
