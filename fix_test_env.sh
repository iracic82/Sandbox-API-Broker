#!/bin/bash
# Fix test environment - Install Python 3.11 and recreate venv

set -e

echo "🔧 Fixing test environment..."
echo ""

# Check if Python 3.11 is installed
if command -v python3.11 &> /dev/null; then
    echo "✅ Python 3.11 found: $(python3.11 --version)"
else
    echo "📦 Installing Python 3.11 via Homebrew..."
    brew install python@3.11
fi

echo ""
echo "🗑️  Removing old venv with Python 3.13..."
rm -rf venv

echo "📦 Creating new venv with Python 3.11..."
python3.11 -m venv venv

echo "🔌 Activating venv..."
source venv/bin/activate

echo "⬆️  Upgrading pip..."
pip install --quiet --upgrade pip

echo "📚 Installing application dependencies..."
pip install --quiet -r requirements.txt

echo "🧪 Installing test dependencies..."
pip install --quiet pytest pytest-asyncio pytest-cov httpx pytest-mock

echo ""
echo "✅ Environment fixed! Python version:"
python --version

echo ""
echo "🧪 Running unit tests..."
pytest tests/unit/ -v --tb=short --no-cov

echo ""
echo "✅ All done! To activate venv in future:"
echo "   source venv/bin/activate"
