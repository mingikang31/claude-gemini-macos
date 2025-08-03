#!/usr/bin/env python3
"""
Launcher script for the AI Assistant macOS application.
This script is used by py2app to create the .app bundle.
"""

import sys
import os

# Add the package to the path
app_dir = os.path.dirname(__file__)
if app_dir:
    sys.path.insert(0, app_dir)

# Import and run the main application
from macos_gemini_overlay.main import main

if __name__ == '__main__':
    main()