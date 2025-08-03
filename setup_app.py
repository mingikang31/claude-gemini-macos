"""
Setup script to build the AI Assistant macOS application using py2app.
"""

from setuptools import setup
import os
import sys

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

APP = ['run_app.py']
APP_NAME = 'AI Assistant'
DATA_FILES = [
    ('macos_gemini_overlay/logo', [
        'macos_gemini_overlay/logo/logo_white.png',
        'macos_gemini_overlay/logo/logo_black.png',
        'macos_gemini_overlay/logo/icon.icns'
    ]),
]

# Find libffi.8.dylib in the conda environment
import glob
libffi_paths = glob.glob('/Users/mingikang/miniconda3/envs/*/lib/libffi.8.dylib')
if libffi_paths:
    # Add libffi to Frameworks directory
    DATA_FILES.append(('Frameworks', [libffi_paths[0]]))

OPTIONS = {
    'argv_emulation': False,
    'iconfile': 'macos_gemini_overlay/logo/icon.icns',
    'plist': {
        'CFBundleName': APP_NAME,
        'CFBundleDisplayName': APP_NAME,
        'CFBundleIdentifier': 'com.aiassistant.overlay',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHighResolutionCapable': True,
        'LSUIElement': True,  # Run as background app (no dock icon)
        'NSSupportsAutomaticGraphicsSwitching': True,
        'LSMinimumSystemVersion': '10.14',
        'NSAppleEventsUsageDescription': 'This app needs to send Apple Events to manage window focus.',
        'NSAccessibilityUsageDescription': 'This app needs accessibility access to listen for keyboard shortcuts globally.',
    },
    'packages': ['objc', 'WebKit', 'AppKit', 'Foundation', 'Quartz'],
    'includes': [
        'objc._objc',
        'macos_gemini_overlay',
        'macos_gemini_overlay.app',
        'macos_gemini_overlay.main',
        'macos_gemini_overlay.constants',
        'macos_gemini_overlay.launcher',
        'macos_gemini_overlay.listener',
        'macos_gemini_overlay.health_checks',
    ],
    'excludes': ['tkinter', 'test', 'distutils'],
    'strip': False,  # Don't strip binaries to avoid breaking dylib dependencies
    'optimize': 0,   # Disable optimization to avoid issues
    'arch': 'universal2',  # Build universal binary
    'dylib_excludes': [],  # Don't exclude any dylibs
}

setup(
    name=APP_NAME,
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
    python_requires='>=3.8',
)