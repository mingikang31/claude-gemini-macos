# Building AI Assistant macOS Desktop Application

This guide will help you create a standalone macOS desktop application from your Python code.

## Prerequisites

1. **macOS 10.14 or later**
2. **Python 3.8 or later**
3. **Xcode Command Line Tools** (install with: `xcode-select --install`)

## Quick Build

The easiest way to build the app:

```bash
./build_app.sh
```

This script will:
- Install required dependencies
- Build the application bundle
- Open the `dist/` folder with your new app

## Manual Build Process

If you prefer to build manually:

### 1. Install Build Dependencies

```bash
pip3 install -r requirements-build.txt
```

### 2. Build the Application

```bash
python3 setup_app.py py2app
```

### 3. Find Your App

The built application will be located at:
```
dist/AI Assistant.app
```

## Installation

1. **Copy to Applications**: Drag `AI Assistant.app` to your `/Applications` folder
2. **First Launch**: Right-click the app and select "Open" to bypass Gatekeeper warnings
3. **Grant Permissions**: Allow Accessibility access when prompted for keyboard shortcuts

## App Features

- **Background App**: Runs without a dock icon (accessible via menu bar)
- **Global Shortcuts**: Option+Space to show/hide, Option+C to switch services
- **Auto-startup**: Use the menu to enable/disable launch at login
- **Self-contained**: No need for Python to be installed on other machines

## Troubleshooting

### Build Issues

**Error: "No module named 'py2app'"**
```bash
pip3 install py2app
```

**Error: "No module named 'objc'"**
```bash
pip3 install pyobjc
```

### Runtime Issues

**App won't launch**: 
- Check Console.app for error messages
- Ensure you have the latest macOS updates

**Keyboard shortcuts don't work**:
- Grant Accessibility permissions in System Preferences > Security & Privacy > Privacy > Accessibility

**Can't switch between Claude/Gemini**:
- Check your internet connection
- Clear web cache using the menu bar option

## Distribution

The built `.app` bundle can be:
- Shared with others (they don't need Python installed)
- Compressed into a `.zip` file for easy distribution
- Signed and notarized for distribution outside the App Store

## App Structure

```
AI Assistant.app/
├── Contents/
│   ├── Info.plist          # App metadata
│   ├── MacOS/              # Executable
│   ├── Resources/          # Python runtime + your code
│   └── Frameworks/         # Required frameworks
```

## Customization

To modify the app:
1. Edit the source code in `macos_gemini_overlay/`
2. Update version in `setup_app.py`
3. Rebuild with `./build_app.sh`

The app will automatically include all your improvements:
- Smooth animations
- Error handling
- Visual feedback
- Bug fixes