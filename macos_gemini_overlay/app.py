# Python libraries
import os
import sys

# Apple libraries
import objc
from AppKit import *
from WebKit import *
from Quartz import *
from Foundation import NSObject, NSURL, NSURLRequest, NSDate, NSTimer

# Local libraries
from .constants import (
    APP_TITLE,
    CORNER_RADIUS,
    DRAG_AREA_HEIGHT,
    LOGO_BLACK_PATH,
    LOGO_WHITE_PATH,
    FRAME_SAVE_NAME,
    STATUS_ITEM_CONTEXT,
    # WEBSITE,
    GEMINI_WEBSITE_URL,
    CLAUDE_WEBSITE_URL,
    DEFAULT_WEBSITE_URL,
    MENU_ITEM_SWITCH_TO_CLAUDE,
    MENU_ITEM_SWITCH_TO_GEMINI,
)
from .launcher import (
    install_startup,
    uninstall_startup,
)
from .listener import (
    global_show_hide_listener,
    load_custom_launcher_trigger,
    set_custom_launcher_trigger,
)


# Custom window (contains entire application).
class AppWindow(NSWindow):
    # Explicitly allow key window status
    def canBecomeKeyWindow(self):
        return True

    # Required to capture "Command+..." sequences.
    def keyDown_(self, event):
        self.delegate().keyDown_(event)


# Custom view (contains click-and-drag area on top sliver of overlay).
class DragArea(NSView):
    def initWithFrame_(self, frame):
        objc.super(DragArea, self).initWithFrame_(frame)
        self.setWantsLayer_(True)
        return self

    # Used to update top-bar background to (roughly) match app color.
    def setBackgroundColor_(self, color):
        self.layer().setBackgroundColor_(color.CGColor())

    # Used to capture the click-and-drag event.
    def mouseDown_(self, event):
        self.window().performWindowDragWithEvent_(event)


# The main delegate for running the overlay app.
class AppDelegate(NSObject):
    @objc.python_method
    def _create_configured_webview(self, frame_rect):
        config = WKWebViewConfiguration.alloc().init()
        config.preferences().setJavaScriptCanOpenWindowsAutomatically_(True)

        # Setup for background color script message handler
        user_content_controller = config.userContentController()
        user_content_controller.addScriptMessageHandler_name_(self, "backgroundColorHandler")

        # Inject JavaScript to monitor background color changes (same as existing)
        script = """
            function sendBackgroundColor() {
                var bgColor = window.getComputedStyle(document.body).backgroundColor;
                window.webkit.messageHandlers.backgroundColorHandler.postMessage(bgColor);
            }
            window.addEventListener('load', sendBackgroundColor);
            new MutationObserver(sendBackgroundColor).observe(document.body, { attributes: true, attributeFilter: ['style'] });
        """
        user_script = WKUserScript.alloc().initWithSource_injectionTime_forMainFrameOnly_(script, WKUserScriptInjectionTimeAtDocumentEnd, True)
        user_content_controller.addUserScript_(user_script)

        webview = WKWebView.alloc().initWithFrame_configuration_(frame_rect, config)
        webview.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)

        safari_user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
        webview.setCustomUserAgent_(safari_user_agent)
        webview.setNavigationDelegate_(self)
        return webview

    @property
    @objc.python_method
    def active_webview(self):
        if self.current_service == "claude":
            return self.claude_webview
        else:
            return self.gemini_webview

    # The main application setup.
    def applicationDidFinishLaunching_(self, notification):
        # Run as accessory app
        NSApp.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
        self.current_service = "gemini"
        # Create a borderless, floating, resizable window
        self.window = AppWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(500, 200, 970, 750),
            NSBorderlessWindowMask | NSResizableWindowMask,
            NSBackingStoreBuffered,
            False
        )
        self.window.setLevel_(NSFloatingWindowLevel)
        self.window.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorStationary
        )
        # Save the last position and size
        self.window.setFrameAutosaveName_(FRAME_SAVE_NAME)
        # Make window transparent so that the corners can be rounded
        self.window.setOpaque_(False)
        self.window.setBackgroundColor_(NSColor.clearColor())
        # Set up content view with rounded corners
        content_view = NSView.alloc().initWithFrame_(self.window.contentView().bounds())
        content_view.setWantsLayer_(True)
        content_view.layer().setCornerRadius_(CORNER_RADIUS)
        content_view.layer().setBackgroundColor_(NSColor.whiteColor().CGColor())
        self.window.setContentView_(content_view)

        initial_webview_frame = ((0, 0), (content_view.bounds().size.width, content_view.bounds().size.height - DRAG_AREA_HEIGHT))

        self.gemini_webview = self._create_configured_webview(initial_webview_frame)
        self.claude_webview = self._create_configured_webview(initial_webview_frame)

        # Load initial content
        gemini_url = NSURL.URLWithString_(GEMINI_WEBSITE_URL)
        gemini_request = NSURLRequest.requestWithURL_(gemini_url)
        self.gemini_webview.loadRequest_(gemini_request)

        claude_url = NSURL.URLWithString_(CLAUDE_WEBSITE_URL)
        claude_request = NSURLRequest.requestWithURL_(claude_url)
        self.claude_webview.loadRequest_(claude_request)

        # Set up drag area (top sliver, full width)
        content_bounds = content_view.bounds()
        self.drag_area = DragArea.alloc().initWithFrame_(
            NSMakeRect(0, content_bounds.size.height - DRAG_AREA_HEIGHT, content_bounds.size.width, DRAG_AREA_HEIGHT)
        )
        content_view.addSubview_(self.drag_area)
        # Add close button to the drag area
        close_button = NSButton.alloc().initWithFrame_(NSMakeRect(5, 5, 20, 20))
        close_button.setBordered_(False)
        close_button.setImage_(NSImage.imageWithSystemSymbolName_accessibilityDescription_("xmark.circle.fill", None))
        close_button.setTarget_(self)
        close_button.setAction_("hideWindow:")
        self.drag_area.addSubview_(close_button)

        # Add both webviews to the content view. Gemini is initially visible.
        content_view.addSubview_(self.claude_webview)
        content_view.addSubview_(self.gemini_webview) # Gemini on top / visible

        self.claude_webview.setHidden_(True) # Claude starts hidden

        # Update the webview sizing and insert it below drag area.
        webview_frame = NSMakeRect(0, 0, content_bounds.size.width, content_bounds.size.height - DRAG_AREA_HEIGHT)
        self.gemini_webview.setFrame_(webview_frame)
        self.claude_webview.setFrame_(webview_frame)

        # Create status bar item with logo
        self.status_item = NSStatusBar.systemStatusBar().statusItemWithLength_(NSSquareStatusItemLength)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        logo_white_path = os.path.join(script_dir, LOGO_WHITE_PATH)
        self.logo_white = NSImage.alloc().initWithContentsOfFile_(logo_white_path)
        self.logo_white.setSize_(NSSize(18, 18))
        logo_black_path = os.path.join(script_dir, LOGO_BLACK_PATH)
        self.logo_black = NSImage.alloc().initWithContentsOfFile_(logo_black_path)
        self.logo_black.setSize_(NSSize(18, 18))
        # Set the initial logo image based on the current appearance
        self.updateStatusItemImage()
        # Observe system appearance changes
        self.status_item.button().addObserver_forKeyPath_options_context_(
            self, "effectiveAppearance", NSKeyValueObservingOptionNew, STATUS_ITEM_CONTEXT
        )
        # Create status bar menu
        menu = NSMenu.alloc().init()
        # Create and configure menu items with explicit targets
        show_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Show "+APP_TITLE, "showWindow:", "")
        show_item.setTarget_(self)
        menu.addItem_(show_item)
        hide_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Hide "+APP_TITLE, "hideWindow:", "h")
        hide_item.setTarget_(self)
        menu.addItem_(hide_item)
        home_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Home", "goToWebsite:", "g")
        home_item.setTarget_(self)
        menu.addItem_(home_item)

        # Add switch to Claude menu item
        self.switch_to_claude_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(MENU_ITEM_SWITCH_TO_CLAUDE, "switchToClaude:", "")
        self.switch_to_claude_item.setTarget_(self)
        menu.addItem_(self.switch_to_claude_item)

        # Add switch to Gemini menu item
        self.switch_to_gemini_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(MENU_ITEM_SWITCH_TO_GEMINI, "switchToGemini:", "")
        self.switch_to_gemini_item.setTarget_(self)
        menu.addItem_(self.switch_to_gemini_item)

        clear_data_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Clear Web Cache", "clearWebViewData:", "")
        clear_data_item.setTarget_(self)
        menu.addItem_(clear_data_item)
        set_trigger_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Set New Trigger", "setTrigger:", "")
        set_trigger_item.setTarget_(self)
        menu.addItem_(set_trigger_item)
        install_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Install Autolauncher", "install:", "")
        install_item.setTarget_(self)
        menu.addItem_(install_item)
        uninstall_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Uninstall Autolauncher", "uninstall:", "")
        uninstall_item.setTarget_(self)
        menu.addItem_(uninstall_item)
        quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Quit", "terminate:", "q")
        quit_item.setTarget_(NSApp)
        menu.addItem_(quit_item)
        # Set the menu for the status item
        self.status_item.setMenu_(menu)
        self.updateSwitchMenuItemsState()
        # Add resize observer
        NSNotificationCenter.defaultCenter().addObserver_selector_name_object_(
            self, 'windowDidResize:', NSWindowDidResizeNotification, self.window
        )
        # Add local mouse event monitor for left mouse down
        self.local_mouse_monitor = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
            NSEventMaskLeftMouseDown,  # Monitor left mouse-down events
            self.handleLocalMouseEvent  # Handler method
        )
        # Create the event tap for key-down events
        tap = CGEventTapCreate(
            kCGSessionEventTap, # Tap at the session level
            kCGHeadInsertEventTap, # Insert at the head of the event queue
            kCGEventTapOptionDefault, # Actively filter events
            CGEventMaskBit(kCGEventKeyDown), # Capture key-down events
            global_show_hide_listener(self), # Your callback function
            None # Optional user info (refcon)
        )
        if tap:
            # Integrate the tap into the run loop
            source = CFMachPortCreateRunLoopSource(None, tap, 0)
            CFRunLoopAddSource(CFRunLoopGetCurrent(), source, kCFRunLoopCommonModes)
            CGEventTapEnable(tap, True)
            CFRunLoopRun() # Start the run loop
        else:
            print("Failed to create event tap. Check Accessibility permissions.")
        # Load the custom launch trigger if the user set it.
        load_custom_launcher_trigger()
        # Set the delegate of the window to this parent application.
        self.window.setDelegate_(self)
        # Make sure this window is shown and focused.
        self.showWindow_(None)

    # Logic to show the overlay, make it the key window, and focus on the typing area.
    def showWindow_(self, sender):
        self.window.makeKeyAndOrderFront_(None)
        NSApp.activateIgnoringOtherApps_(True)
        self._focus_prompt_area()

    # Hide the overlay and allow focus to return to the next visible application.
    def hideWindow_(self, sender):
        NSApp.hide_(None)

    # Go to the default landing website for the overlay (in case accidentally navigated away).
    def goToWebsite_(self, sender):
        if self.current_service == "claude":
            url = NSURL.URLWithString_(CLAUDE_WEBSITE_URL)
        else:  # gemini
            url = NSURL.URLWithString_(GEMINI_WEBSITE_URL)
        request = NSURLRequest.requestWithURL_(url)
        self.active_webview.loadRequest_(request)

    def switchToClaude_(self, sender):
        if self.current_service != "claude":
            self.current_service = "claude"
            self.gemini_webview.setHidden_(True)
            self.claude_webview.setHidden_(False)
            # Ensure the Claude webview is brought to the front in the view hierarchy
            self.window.contentView().addSubview_positioned_relativeTo_(self.claude_webview, NSWindowAbove, self.gemini_webview)
            self.updateSwitchMenuItemsState()
            self._focus_prompt_area() # Focus the new active webview

    def switchToGemini_(self, sender):
        if self.current_service != "gemini":
            self.current_service = "gemini"
            self.claude_webview.setHidden_(True)
            self.gemini_webview.setHidden_(False)
            # Ensure the Gemini webview is brought to the front
            self.window.contentView().addSubview_positioned_relativeTo_(self.gemini_webview, NSWindowAbove, self.claude_webview)
            self.updateSwitchMenuItemsState()
            self._focus_prompt_area() # Focus the new active webview

    def updateSwitchMenuItemsState(self):
        if self.current_service == "claude":
            self.switch_to_claude_item.setEnabled_(False)
            self.switch_to_gemini_item.setEnabled_(True)
        else:  # gemini
            self.switch_to_claude_item.setEnabled_(True)
            self.switch_to_gemini_item.setEnabled_(False)

    # Clear the webview cache data (in case cookies cause errors).
    def clearWebViewData_(self, sender):
        dataStore = self.active_webview.configuration().websiteDataStore()
        dataTypes = WKWebsiteDataStore.allWebsiteDataTypes()
        dataStore.removeDataOfTypes_modifiedSince_completionHandler_(
            dataTypes,
            NSDate.distantPast(),
            lambda: print("Data cleared")
        )

    # Go to the default landing website for the overlay (in case accidentally navigated away).
    def install_(self, sender):
        if install_startup():
            # Exit the current process since a new one will launch.
            print("Installation successful, exiting.", flush=True)
            NSApp.terminate_(None)
        else:
            print("Installation unsuccessful.", flush=True)

    # Go to the default landing website for the overlay (in case accidentally navigated away).
    def uninstall_(self, sender):
        if uninstall_startup():
            NSApp.hide_(None)

    # Handle the 'Set Trigger' menu item click.
    def setTrigger_(self, sender):
        set_custom_launcher_trigger(self)

    # For capturing key commands while the key window (in focus).
    def keyDown_(self, event):
        modifiers = event.modifierFlags()
        key_command = modifiers & NSCommandKeyMask
        key_alt = modifiers & NSAlternateKeyMask
        key_shift = modifiers & NSShiftKeyMask
        key_control = modifiers & NSControlKeyMask
        key = event.charactersIgnoringModifiers()

        # Option + C to switch services
        if key_alt and (not key_command) and (not key_control) and (not key_shift) and key.lower() == 'c':
            if self.current_service == "gemini":
                self.switchToClaude_(None)
            else:
                self.switchToGemini_(None)
            return # Consume the event

        # Command (NOT alt)
        if (key_command or key_control) and (not key_alt):
            # Select all
            if key == 'a':
                self.window.firstResponder().selectAll_(None)
            # Copy
            elif key == 'c':
                self.window.firstResponder().copy_(None)
            # Cut
            elif key == 'x':
                self.window.firstResponder().cut_(None)
            # Paste
            elif key == 'v':
                self.window.firstResponder().paste_(None)
            # Hide
            elif key == 'h':
                self.hideWindow_(None)
            # New Chat (Command+N)
            elif key == 'n':
                js = ""
                if self.current_service == "claude":
                    js = """
                    (function(){
                      const selectors = [
                        'button[aria-label="Open new chat"]', // Claude
                        'button[aria-label*="New Chat"]' // Claude (covers variations)
                      ];
                      let btnFound = false;
                      for (const sel of selectors) {
                        const btn = document.querySelector(sel);
                        if (btn) {
                          btn.click();
                          btnFound = true;
                          break;
                        }
                      }
                      if (!btnFound) {
                        location.href = '%s';
                      }
                    })();
                    """ % CLAUDE_WEBSITE_URL
                else:  # gemini
                    js = """
                    (function(){
                      const sel = '[aria-label="New chat"], [aria-label="New conversation"], [data-command="new-conversation"]';
                      const btn = document.querySelector(sel);
                      if(btn){ btn.click(); } else { location.href='%s'; }
                    })();
                    """ % GEMINI_WEBSITE_URL
                self.active_webview.evaluateJavaScript_completionHandler_(js, None)
            # Toggle Sidebar (Ctrl+Cmd+S)
            elif key == 's' and key_control and key_command:
                js = """
                (function(){
                  const selectors=[
                    '[aria-label="Main menu"]',
                    '[data-test-id="side-nav-menu-button"]'
                  ];
                  let btn=null;
                  for(const sel of selectors){ btn=document.querySelector(sel); if(btn) break; }
                  if(btn){ btn.click(); }
                })();
                """
                self.active_webview.evaluateJavaScript_completionHandler_(js, None)
            # Quit
            elif key == 'q':
                NSApp.terminate_(None)
            # Open Saved Info (Cmd + ,)
            elif key == ',' and key_command and not key_control and not key_alt:
                js = """
                (function(){
                  function clickSettings(){
                    const btn=document.querySelector('[aria-label="Settings & help"], [data-test-id="settings-and-help-button"]');
                    if(btn){ btn.click(); return true; }
                    return false;
                  }
                  function clickSaved(){
                    let link=document.querySelector('a[href*="/saved-info"]');
                    if(!link){
                      // fallback: find menu item whose text includes "Saved info"
                      const items=document.querySelectorAll('a[role="menuitem"], button[role="menuitem"]');
                      for(const el of items){
                        if(el.textContent && el.textContent.trim().toLowerCase().includes('saved info')){ link=el; break; }
                      }
                    }
                    if(link){ link.click(); }
                  }
                  if(clickSettings()){
                    setTimeout(clickSaved, 50);
                  }
                })();
                """
                self.active_webview.evaluateJavaScript_completionHandler_(js, None)
            # # Undo (causes crash for some reason)
            # elif key == 'z':
            #     self.window.firstResponder().undo_(None)

    # Handler for capturing a click-and-drag event when not already the key window.
    @objc.python_method
    def handleLocalMouseEvent(self, event):
        if event.window() == self.window:
            # Get the click location in window coordinates
            click_location = event.locationInWindow()
            # Use hitTest_ to determine which view receives the click
            hit_view = self.window.contentView().hitTest_(click_location)
            # Check if the hit view is the drag area
            if hit_view == self.drag_area:
                # Bring the window to the front and make it key
                self.showWindow_(None)
                # Initiate window dragging with the event
                self.window.performWindowDragWithEvent_(event)
                return None  # Consume the event
        return event  # Pass unhandled events along

    # Handler for when the window resizes (adjusts the drag area).
    def windowDidResize_(self, notification):
        bounds = self.window.contentView().bounds()
        w, h = bounds.size.width, bounds.size.height
        self.drag_area.setFrame_(NSMakeRect(0, h - DRAG_AREA_HEIGHT, w, DRAG_AREA_HEIGHT))
        webview_new_frame = NSMakeRect(0, 0, w, h - DRAG_AREA_HEIGHT)
        self.gemini_webview.setFrame_(webview_new_frame)
        self.claude_webview.setFrame_(webview_new_frame)

    # Handler for setting the background color based on the web page background color.
    def userContentController_didReceiveScriptMessage_(self, userContentController, message):
        if message.name() == "backgroundColorHandler":
            bg_color_str = message.body()
            # Convert CSS color to NSColor (assuming RGB for simplicity)
            if bg_color_str.startswith("rgb") and ("(" in bg_color_str) and (")" in bg_color_str):
                rgb_values = [float(val) for val in bg_color_str[bg_color_str.index("(")+1:bg_color_str.index(")")].split(",")]
                r, g, b = [val / 255.0 for val in rgb_values[:3]]
                color = NSColor.colorWithCalibratedRed_green_blue_alpha_(r, g, b, 1.0)
                self.drag_area.setBackgroundColor_(color)

    # Logic for checking what color the logo in the status bar should be, and setting appropriate logo.
    def updateStatusItemImage(self):
        appearance = self.status_item.button().effectiveAppearance()
        if appearance.bestMatchFromAppearancesWithNames_([NSAppearanceNameAqua, NSAppearanceNameDarkAqua]) == NSAppearanceNameDarkAqua:
            self.status_item.button().setImage_(self.logo_white)
        else:
            self.status_item.button().setImage_(self.logo_black)

    # Observer that is triggered whenever the color of the status bar logo might need to be updated.
    def observeValueForKeyPath_ofObject_change_context_(self, keyPath, object, change, context):
        if context == STATUS_ITEM_CONTEXT and keyPath == "effectiveAppearance":
            self.updateStatusItemImage()

    # System triggered appearance changes that might affect logo color.
    def appearanceDidChange_(self, notification):
        # Update the logo image when the system appearance changes
        self.updateStatusItemImage()

    # WKNavigationDelegate – called when navigation finishes
    def webView_didFinishNavigation_(self, webview, navigation):
        # Page loaded, focus prompt area after small delay to ensure textarea exists
        # Delay 0.1 s, then focus prompt (use NSTimer – PyObjC provides selector call)
        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.1, self, '_focusPromptTimerFired:', None, False)

    # Helper called by timer
    def _focusPromptTimerFired_(self, timer):
        self._focus_prompt_area()

    # Python method to call JS that focuses the Gemini textarea / prompt
    @objc.python_method
    def _focus_prompt_area(self):
        js_focus = """
        (function(){
          const selectors = [
            '[aria-label="Enter a prompt here"]', // Gemini
            '[data-placeholder="Ask Gemini"]', // Gemini
            '[data-placeholder="Message Claude"]', // Claude
            '[data-placeholder^="Send a message"]', // Claude (covers variations)
            'textarea' // Generic fallback
          ];
          for (const sel of selectors) {
            const el = document.querySelector(sel);
            if (el) {
              el.focus();
              break;
            }
          }
        })();
        """
        self.active_webview.evaluateJavaScript_completionHandler_(js_focus, None)
