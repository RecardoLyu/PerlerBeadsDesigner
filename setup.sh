#!/bin/bash
# Setup script for Perler Beads Designer

echo "========================================="
echo "Perler Beads Designer Setup"
echo "========================================="
echo ""

# Detect OS
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    OS="Windows"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macOS"
else
    OS="Linux"
fi

echo "Detected OS: $OS"
echo ""

# Check Python version
echo "Checking Python installation..."
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "ERROR: Python is not installed!"
    exit 1
fi

$PYTHON_CMD --version

# Create virtual environment
echo ""
echo "Creating virtual environment..."
$PYTHON_CMD -m venv venv

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to create virtual environment"
    exit 1
fi

echo "Virtual environment created successfully"
echo ""

# Activate virtual environment
if [ "$OS" == "Windows" ]; then
    source venv/Scripts/activate.ps1 2>/dev/null || source venv/Scripts/activate
else
    source venv/bin/activate
fi

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip setuptools wheel

echo "Installing core dependencies..."
pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install dependencies"
    exit 1
fi

echo ""
echo "========================================="
echo "Setup complete!"
echo "========================================="
echo ""
echo "Next steps:"
if [ "$OS" == "Windows" ]; then
    echo "1. Activate virtual environment:"
    echo "   .\\venv\\Scripts\\Activate.ps1"
else
    echo "1. Virtual environment is already activated"
fi
echo ""
echo "2. Run the application:"
echo "   python -m src.main"
echo ""
echo "3. Or run in VS Code:"
echo "   Press F5 to start debugging"
echo ""
