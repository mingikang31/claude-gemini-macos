#!/bin/bash

# Build script for AI Assistant macOS application

echo "🚀 Building AI Assistant macOS Application..."

# Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf build dist

# Check if py2app is installed
if ! python3 -c "import py2app" 2>/dev/null; then
    echo "📦 Installing py2app..."
    pip3 install py2app
fi

# Build the application
echo "🔨 Building application bundle..."
python3 setup_app.py py2app

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Build successful!"
    echo ""
    echo "📂 Your application is located at:"
    echo "   $(pwd)/dist/AI Assistant.app"
    echo ""
    echo "🎯 To install the app:"
    echo "   1. Open Finder and navigate to: $(pwd)/dist/"
    echo "   2. Drag 'AI Assistant.app' to your Applications folder"
    echo "   3. Launch from Applications or Spotlight"
    echo ""
    echo "⚠️  First run:"
    echo "   - You may need to right-click and 'Open' to bypass Gatekeeper"
    echo "   - Grant Accessibility permissions when prompted"
    echo ""
    
    # Open the dist folder in Finder
    open dist/
else
    echo ""
    echo "❌ Build failed. Check the error messages above."
    exit 1
fi