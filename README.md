<p align="center">
  <h1 align="center"><code>macos-ai-assistant-overlay</code></h1>
</p>

<p align="center">
A simple macOS overlay application for seamlessly switching between <code>Claude</code>, <code>Gemini</code>, and <code>Perplexity</code> in a dedicated window with key command <code>⌥ + Space</code>.
</p>

![Launcher Sample](images/macos-gemini-overlay.png)


## Features

* **Multi-AI Support**: Seamlessly switch between Claude, Gemini, and Perplexity
* **Quick Access**: Press `⌥ + Space` to show/hide the overlay window anywhere
* **Smart Service Switching**: Press `⌥ + C` to cycle through Claude → Perplexity → Gemini
* **Lazy Loading**: Services are loaded on-demand for better performance and reduced memory usage
* **Smooth Transitions**: Visual fade effects when switching between services


## Supported shortcuts

### Global Shortcuts
* `⌥ + Space` - Show/Hide the AI Assistant overlay
* `⌥ + C` - Cycle through Claude, Gemini, and Perplexity

### Within the Overlay
* `Cmd + N` - Start a new conversation
* `Ctrl + Cmd + S` - Toggle Sidebar (where available)
* `Cmd + ,` - Open Settings page
* `Cmd + H` - Hide the overlay


## Installation

  The easiest approach is to download and execute the DMG installer to place the program into your Applications folder.

  Otherwise, you can install the latest release from a Terminal with:

```bash
python3 -m pip install macos-ai-assistant-overlay
```

  Once you've installed the package, you can enable it to be automatically launched at startup with:

```bash
macos-ai-assistant-overlay --install-startup
```

  You will get a request to enable Accessibility the first time this launches.

  The Accessibility access is required for the background task to listen for the `⌥ + Space` and `⌥ + C` keyboard commands. But please don't just take my word for it, look at the [listener code yourself](macos_gemini_overlay/listener.py) and see. ;)

  Within a few seconds of approving Accessibility access, you should see a little icon appear along the top of your screen.

  And you're done! Now this should launch automatically and constantly run in the background. If you ever decide you do not want it, see the uninstall instructions below.


## Usage

  Once the application is launched, it opens a window dedicated to AI assistants (defaults to Gemini). You'll need to log in to each service, but you should only need to do that once. 
  
  After installing, pressing `⌥ + Space` while the window is open will hide it, and pressing it again at any point will reveal it and pin it as the top-most window overlay on top of other applications. This enables quick and easy access to your AI assistants on macOS.

  **Switching Between Services:**
  - Press `⌥ + C` to cycle through: Gemini → Claude → Perplexity → Gemini
  - Or use the menubar dropdown to select a specific service
  - The current service is displayed in the window's title bar

  **Performance Notes:**
  - Services are loaded on-demand (lazy loading) to improve startup time and reduce memory usage
  - Only the active service is visible and running; inactive services are suspended
  - Switching between services is optimized with smooth visual transitions

  There is a dropdown menu with basic options that shows when you click the menubar icon. Personally I find that using `⌥ + Space` to summon and dismiss the dialogue and `⌥ + C` to switch services is the most convenient.

  If you decide you want to uninstall the application, you can do that by clicking the option in the menubar dropdown, or from the command line with:

```bash
macos-ai-assistant-overlay --uninstall-startup
```


## How it works

  This is a very thin `pyobjc` application written to contain web views of Claude, Google Gemini, and Perplexity. Most of the logic contained in this small application is for stylistic purposes, making the overlay shaped correctly, resizeable, draggable, and able to be summoned anywhere easily with keyboard commands. 
  
  The app uses lazy loading to only load services when you first switch to them, reducing memory usage and improving startup performance. The `⌥ + Space` and `⌥ + C` keyboard commands require Accessibility access to macOS.


## Local development

Clone the repository and install dependencies:

```bash
git clone https://github.com/mingikang31/claude-gemini-macos.git
cd claude-gemini-macos
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

  This project was originally forked from [macos-grok-overlay](https://github.com/tchlux/macos-grok-overlay) and has been enhanced to support multiple AI services (Claude, Gemini, and Perplexity) with performance optimizations.

  This is a community-driven project and is not affiliated with Anthropic (Claude), Google (Gemini), or Perplexity AI.


  