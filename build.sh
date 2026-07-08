#!/bin/bash

# Build script for Perler Beads Designer (macOS/Linux)

echo ""
echo "========================================"
echo "Perler Beads Designer Build Script"
echo "========================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python3 is not installed"
    echo "Please install Python3 from https://www.python.org"
    exit 1
fi

python3 --version

# Check if PyInstaller is installed
if ! pip3 show pyinstaller &> /dev/null; then
    echo ""
    echo "Installing PyInstaller..."
    pip3 install pyinstaller
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to install PyInstaller"
        exit 1
    fi
fi

# Clean old builds
echo ""
echo "Cleaning old builds..."
rm -rf build dist

# Build executable
echo ""
echo "Building executable..."
pyinstaller pyinstaller.spec

if [ $? -ne 0 ]; then
    echo "ERROR: Build failed"
    exit 1
fi

echo ""
echo "========================================"
echo "Build successful!"
echo "========================================"
echo ""
echo "Executable location:"
echo "  dist/PerlerBeadsDesigner/PerlerBeadsDesigner"
echo ""
