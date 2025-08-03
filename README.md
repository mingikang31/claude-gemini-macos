<p align="center">
  <h1 align="center"><code>macos-gemini-overlay</code></h1>
</p>

<p align="center">
A simple macOS overlay application for pinning <code>gemini.google.com</code> to a dedicated window and key command <code>⌥ + Space</code>.
</p>

![Launcher Sample](images/macos-gemini-overlay.png)


## Supported shortcuts within Gemini
* `Cmd + N` starts a new conversation.
* `Ctrl + Cmd + S` toggles Sidebar.
* `Cmd + ,` opens the Settings page (memory).


## Installation

  The easiest approach is to download and execute the DMG installer (by clicking the image below) to place the program into your Applications folder.

[![DMG Installer](images/dmg-installer-preview.png)](https://github.com/jzelenkov/macos-gemini-overlay/releases/download/0.0.3/macos-gemini-overlay.dmg)

  Otherwise, you can install the latest stable release from a Terminal with:

```bash
python3 -m pip install macos-gemini-overlay
```

  Once you've installed the package, you can enable it to be automatically launched at startup with:

```bash
macos-gemini-overlay --install-startup
```

  You will get a request like this to enable Accessibility the first time this launches.

![Accessibility Request](images/macos-gemini-overlay-accessibility.png)

  The Accessibility access is required for the background task to listen for the `⌥ + Space` keyboard command. But please don't just take my word for it, look at the [listener code yourself](macos_gemini_overlay/listener.py) and see. ;)

  Within a few seconds of approving Accessibility access, you should see a little icon like this appear along the top of your screen.

![Menu Sample](images/macos-gemini-overlay-menu.png)

  And you're done! Now this should launch automatically and constantly run in the background. If you ever decide you do not want it, see the uninstall instructions below.


## Usage

  Once the application is launched, it should immediately open a window dedicated to `gemini.google.com`. You'll need to log in there, but you should only need to do that once. After installing, pressing `⌥ + Space` while the window is open will hide it, and pressing it again at any point will reveal it and pin it as the top-most window overlay on top of other applications. This enables quick and easy access to Google Gemini on macOS.

  There is a dropdown menu with basic options that shows when you click the menubar icon. Personally I find that using `⌥ + Space` to summon and dismiss the dialogue as needed is the most convenient.

  If you decide you want to uninstall the application, you can do that by clicking the option in the menubar dropdown, or from the command line with:

```bash
macos-gemini-overlay --uninstall-startup
```


## How it works

  This is a very thin `pyobjc` application written to contain a web view of the current production Google Gemini website. Most of the logic contained in this small application is for stylistic purposes, making the overlay shaped correctly, resizeable, draggable, and able to be summoned anywhere easily with a single (modifiable) keyboard command. There's also a few steps needed to listen specifically for the `⌥ + Space` keyboard command, which requires Accessibility access to macOS.


## Local development

Clone the repository and install dependencies:

```bash
git clone https://github.com/jzelenkov/macos-gemini-overlay.git
cd macos-gemini-overlay
python3 -m pip install -r macos_gemini_overlay/about/requirements.txt
```

To run the application directly for development:

```bash
python3 -m macos_gemini_overlay.main
```

For a development workflow that auto-reloads on code changes, you can use:

```bash
pip install watchdog
watchmedo auto-restart --directory=macos_gemini_overlay/ --pattern=\*.py --recursive -- python3 -m macos_gemini_overlay.main
```

You can also run tests (if any) with:

```bash
python3 -m unittest discover
```


## Final thoughts

  This project was forked from [macos-grok-overlay](https://github.com/tchlux/macos-grok-overlay) and modified to work with Google Gemini. All credits go to the original author.

  This was a small fun weekend project, and is not a product of Google Gemini, xAI team nor is it formally affiliated with them.


  