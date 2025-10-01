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
    PERPLEXITY_WEBSITE_URL,
    DEFAULT_WEBSITE_URL,
    MENU_ITEM_SWITCH_TO_CLAUDE,
    MENU_ITEM_SWITCH_TO_GEMINI,
    MENU_ITEM_SWITCH_TO_PERPLEXITY,
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


# The main delegate for running the dual-service AI overlay app.
# Manages switching between Claude and Gemini webviews while maintaining state.
class AppDelegate(NSObject):
    @objc.python_method
    def _create_configured_webview(self, frame_rect):
        config = WKWebViewConfiguration.alloc().init()
        config.preferences().setJavaScriptCanOpenWindowsAutomatically_(True)

        # Setup for background color script message handler
        user_content_controller = config.userContentController()
        user_content_controller.addScriptMessageHandler_name_(self, "backgroundColorHandler")

        # Inject JavaScript to monitor background color changes and reduce font size
        script = """
            function sendBackgroundColor() {
                var bgColor = window.getComputedStyle(document.body).backgroundColor;
                window.webkit.messageHandlers.backgroundColorHandler.postMessage(bgColor);
            }
            
            function applyZoomReduction() {
                // Create or update zoom style
                var zoomStyle = document.getElementById('ai-assistant-zoom');
                if (!zoomStyle) {
                    zoomStyle = document.createElement('style');
                    zoomStyle.id = 'ai-assistant-zoom';
                    document.head.appendChild(zoomStyle);
                }
                
                // Apply 85% zoom to make content smaller (similar to browser zoom)
                zoomStyle.textContent = `
                    body {
                        zoom: 0.85 !important;
                        transform-origin: top left !important;
                    }
                    
                    /* Fallback for browsers that don't support zoom */
                    @supports not (zoom: 0.85) {
                        body {
                            transform: scale(0.85) !important;
                            transform-origin: top left !important;
                            width: 117.65% !important; /* 100/0.85 to compensate for scaling */
                            height: 117.65% !important;
                        }
                    }
                `;
            }
            
            window.addEventListener('load', function() {
                sendBackgroundColor();
                applyZoomReduction();
            });
            
            // Apply zoom reduction immediately and on DOM changes
            applyZoomReduction();
            new MutationObserver(function() {
                sendBackgroundColor();
                applyZoomReduction();
            }).observe(document.body, { attributes: true, attributeFilter: ['style'] });
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
        elif self.current_service == "perplexity":
            return self.perplexity_webview
        else:
            return self.gemini_webview

    # The main application setup.
    def applicationDidFinishLaunching_(self, notification):
        # Run as accessory app
        NSApp.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
        self.current_service = "gemini"
        self.switching_in_progress = False
        self.switch_indicator = None
        self.webviews_loaded = {"gemini": False, "claude": False, "perplexity": False}
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

        # Create all three webviews
        self.gemini_webview = self._create_configured_webview(initial_webview_frame)
        self.claude_webview = self._create_configured_webview(initial_webview_frame)
        self.perplexity_webview = self._create_configured_webview(initial_webview_frame)

        # Load initial content only for Gemini (lazy loading for others)
        gemini_url = NSURL.URLWithString_(GEMINI_WEBSITE_URL)
        gemini_request = NSURLRequest.requestWithURL_(gemini_url)
        self.gemini_webview.loadRequest_(gemini_request)
        self.webviews_loaded["gemini"] = True

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
        
        # Add service indicator label to show current service
        self.service_label = NSTextField.alloc().initWithFrame_(NSMakeRect(30, 5, 100, 20))
        self.service_label.setStringValue_("Gemini")
        self.service_label.setBezeled_(False)
        self.service_label.setDrawsBackground_(False)
        self.service_label.setEditable_(False)
        self.service_label.setSelectable_(False)
        self.service_label.setFont_(NSFont.boldSystemFontOfSize_(12))
        self.service_label.setTextColor_(NSColor.labelColor())
        self.drag_area.addSubview_(self.service_label)

        # Add all webviews to the content view. Gemini is the default active service.
        content_view.addSubview_(self.claude_webview)
        content_view.addSubview_(self.perplexity_webview)
        content_view.addSubview_(self.gemini_webview) # Gemini starts as the active service

        self.claude_webview.setHidden_(True) # Claude starts hidden
        self.perplexity_webview.setHidden_(True) # Perplexity starts hidden

        # Update the webview sizing and insert it below drag area.
        webview_frame = NSMakeRect(0, 0, content_bounds.size.width, content_bounds.size.height - DRAG_AREA_HEIGHT)
        self.gemini_webview.setFrame_(webview_frame)
        self.claude_webview.setFrame_(webview_frame)
        self.perplexity_webview.setFrame_(webview_frame)

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

        # Add switch to Perplexity menu item
        self.switch_to_perplexity_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(MENU_ITEM_SWITCH_TO_PERPLEXITY, "switchToPerplexity:", "")
        self.switch_to_perplexity_item.setTarget_(self)
        menu.addItem_(self.switch_to_perplexity_item)

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
        elif self.current_service == "perplexity":
            url = NSURL.URLWithString_(PERPLEXITY_WEBSITE_URL)
        else:  # gemini
            url = NSURL.URLWithString_(GEMINI_WEBSITE_URL)
        request = NSURLRequest.requestWithURL_(url)
        self.active_webview.loadRequest_(request)

    def switchToClaude_(self, sender):
        if self.switching_in_progress or self.current_service == "claude":
            return
        
        self.switching_in_progress = True
        self._showSwitchIndicator("Switching to Claude...")
        
        try:
            self.current_service = "claude"
            
            # Lazy load Claude if not yet loaded
            if not self.webviews_loaded["claude"]:
                claude_url = NSURL.URLWithString_(CLAUDE_WEBSITE_URL)
                claude_request = NSURLRequest.requestWithURL_(claude_url)
                self.claude_webview.loadRequest_(claude_request)
                self.webviews_loaded["claude"] = True
            
            # Animate the transition with cross-fade effect
            self.claude_webview.setAlphaValue_(0.0)
            self.claude_webview.setHidden_(False)
            
            # Ensure the Claude webview is brought to the front in the view hierarchy
            self.window.contentView().addSubview_positioned_relativeTo_(self.claude_webview, NSWindowAbove, self.gemini_webview)
            
            # Animate fade-in for Claude and fade-out for others
            def animation_group(context):
                context.setDuration_(0.2)
                self.claude_webview.animator().setAlphaValue_(1.0)
                self.gemini_webview.animator().setAlphaValue_(0.0)
                self.perplexity_webview.animator().setAlphaValue_(0.0)
            
            def completion_handler():
                if self.gemini_webview:
                    self.gemini_webview.setHidden_(True)
                    self.gemini_webview.setAlphaValue_(1.0)  # Reset for next transition
                if self.perplexity_webview:
                    self.perplexity_webview.setHidden_(True)
                    self.perplexity_webview.setAlphaValue_(1.0)  # Reset for next transition
            
            NSAnimationContext.runAnimationGroup_completionHandler_(
                animation_group,
                completion_handler
            )
            
            self.updateSwitchMenuItemsState()
            # Use timer for delayed focus to ensure webview is ready
            NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                0.3, self, '_switchCompleteTimerFired:', None, False)
        except Exception as e:
            print(f"Error switching to Claude: {e}")
            self._hideSwitchIndicator()
            self.switching_in_progress = False

    def switchToGemini_(self, sender):
        if self.switching_in_progress or self.current_service == "gemini":
            return
        
        self.switching_in_progress = True
        self._showSwitchIndicator("Switching to Gemini...")
        
        try:
            self.current_service = "gemini"
            
            # Lazy load Gemini if not yet loaded
            if not self.webviews_loaded["gemini"]:
                gemini_url = NSURL.URLWithString_(GEMINI_WEBSITE_URL)
                gemini_request = NSURLRequest.requestWithURL_(gemini_url)
                self.gemini_webview.loadRequest_(gemini_request)
                self.webviews_loaded["gemini"] = True
            
            # Animate the transition with cross-fade effect
            self.gemini_webview.setAlphaValue_(0.0)
            self.gemini_webview.setHidden_(False)
            
            # Ensure the Gemini webview is brought to the front
            self.window.contentView().addSubview_positioned_relativeTo_(self.gemini_webview, NSWindowAbove, self.claude_webview)
            
            # Animate fade-in for Gemini and fade-out for others
            def animation_group(context):
                context.setDuration_(0.2)
                self.gemini_webview.animator().setAlphaValue_(1.0)
                self.claude_webview.animator().setAlphaValue_(0.0)
                self.perplexity_webview.animator().setAlphaValue_(0.0)
            
            def completion_handler():
                if self.claude_webview:
                    self.claude_webview.setHidden_(True)
                    self.claude_webview.setAlphaValue_(1.0)  # Reset for next transition
                if self.perplexity_webview:
                    self.perplexity_webview.setHidden_(True)
                    self.perplexity_webview.setAlphaValue_(1.0)  # Reset for next transition
            
            NSAnimationContext.runAnimationGroup_completionHandler_(
                animation_group,
                completion_handler
            )
            
            self.updateSwitchMenuItemsState()
            # Use timer for delayed focus to ensure webview is ready
            NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                0.3, self, '_switchCompleteTimerFired:', None, False)
        except Exception as e:
            print(f"Error switching to Gemini: {e}")
            self._hideSwitchIndicator()
            self.switching_in_progress = False

    def switchToPerplexity_(self, sender):
        if self.switching_in_progress or self.current_service == "perplexity":
            return
        
        self.switching_in_progress = True
        self._showSwitchIndicator("Switching to Perplexity...")
        
        try:
            self.current_service = "perplexity"
            
            # Lazy load Perplexity if not yet loaded
            if not self.webviews_loaded["perplexity"]:
                perplexity_url = NSURL.URLWithString_(PERPLEXITY_WEBSITE_URL)
                perplexity_request = NSURLRequest.requestWithURL_(perplexity_url)
                self.perplexity_webview.loadRequest_(perplexity_request)
                self.webviews_loaded["perplexity"] = True
            
            # Animate the transition with cross-fade effect
            self.perplexity_webview.setAlphaValue_(0.0)
            self.perplexity_webview.setHidden_(False)
            
            # Ensure the Perplexity webview is brought to the front
            self.window.contentView().addSubview_positioned_relativeTo_(self.perplexity_webview, NSWindowAbove, self.gemini_webview)
            
            # Animate fade-in for Perplexity and fade-out for others
            def animation_group(context):
                context.setDuration_(0.2)
                self.perplexity_webview.animator().setAlphaValue_(1.0)
                self.gemini_webview.animator().setAlphaValue_(0.0)
                self.claude_webview.animator().setAlphaValue_(0.0)
            
            def completion_handler():
                if self.gemini_webview:
                    self.gemini_webview.setHidden_(True)
                    self.gemini_webview.setAlphaValue_(1.0)  # Reset for next transition
                if self.claude_webview:
                    self.claude_webview.setHidden_(True)
                    self.claude_webview.setAlphaValue_(1.0)  # Reset for next transition
            
            NSAnimationContext.runAnimationGroup_completionHandler_(
                animation_group,
                completion_handler
            )
            
            self.updateSwitchMenuItemsState()
            # Use timer for delayed focus to ensure webview is ready
            NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                0.3, self, '_switchCompleteTimerFired:', None, False)
        except Exception as e:
            print(f"Error switching to Perplexity: {e}")
            self._hideSwitchIndicator()
            self.switching_in_progress = False

    def updateSwitchMenuItemsState(self):
        if self.current_service == "claude":
            self.switch_to_claude_item.setEnabled_(False)
            self.switch_to_gemini_item.setEnabled_(True)
            self.switch_to_perplexity_item.setEnabled_(True)
            self.service_label.setStringValue_("Claude")
        elif self.current_service == "perplexity":
            self.switch_to_claude_item.setEnabled_(True)
            self.switch_to_gemini_item.setEnabled_(True)
            self.switch_to_perplexity_item.setEnabled_(False)
            self.service_label.setStringValue_("Perplexity")
        else:  # gemini
            self.switch_to_claude_item.setEnabled_(True)
            self.switch_to_gemini_item.setEnabled_(False)
            self.switch_to_perplexity_item.setEnabled_(True)
            self.service_label.setStringValue_("Gemini")

    # Clear the webview cache data (in case cookies cause errors).
    def clearWebViewData_(self, sender):
        try:
            dataStore = self.active_webview.configuration().websiteDataStore()
            dataTypes = WKWebsiteDataStore.allWebsiteDataTypes()
            
            def completion_handler():
                print("Web cache data cleared successfully")
                self._showNotification("Cache cleared", "Web data has been cleared")
            
            dataStore.removeDataOfTypes_modifiedSince_completionHandler_(
                dataTypes,
                NSDate.distantPast(),
                completion_handler
            )
        except Exception as e:
            print(f"Error clearing web data: {e}")
            self._showNotification("Error", "Failed to clear web cache")

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

        # Option + C to switch services (cycle through all three)
        if key_alt and (not key_command) and (not key_control) and (not key_shift) and key.lower() == 'c':
            if self.current_service == "gemini":
                self.switchToClaude_(None)
            elif self.current_service == "claude":
                self.switchToPerplexity_(None)
            else:  # perplexity
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
                      try {
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
                        return 'success';
                      } catch (error) {
                        return 'error: ' + error.message;
                      }
                    })();
                    """ % CLAUDE_WEBSITE_URL
                else:  # gemini
                    js = """
                    (function(){
                      try {
                        const sel = '[aria-label="New chat"], [aria-label="New conversation"], [data-command="new-conversation"]';
                        const btn = document.querySelector(sel);
                        if(btn){ 
                          btn.click(); 
                          return 'success';
                        } else { 
                          location.href='%s'; 
                          return 'redirect';
                        }
                      } catch (error) {
                        return 'error: ' + error.message;
                      }
                    })();
                    """ % GEMINI_WEBSITE_URL
                
                def new_chat_completion_handler(result, error):
                    if error:
                        print(f"JavaScript error in new chat command: {error}")
                    elif result and result.startswith('error:'):
                        print(f"New chat script error: {result}")
                
                self.active_webview.evaluateJavaScript_completionHandler_(js, new_chat_completion_handler)
            # Toggle Sidebar (Ctrl+Cmd+S)
            elif key == 's' and key_control and key_command:
                js = """
                (function(){
                  try {
                    const selectors=[
                      '[aria-label="Main menu"]',
                      '[data-test-id="side-nav-menu-button"]'
                    ];
                    let btn=null;
                    for(const sel of selectors){ btn=document.querySelector(sel); if(btn) break; }
                    if(btn){ 
                      btn.click(); 
                      return 'success';
                    }
                    return 'no_button_found';
                  } catch (error) {
                    return 'error: ' + error.message;
                  }
                })();
                """
                
                def sidebar_completion_handler(result, error):
                    if error:
                        print(f"JavaScript error in sidebar toggle: {error}")
                    elif result and result.startswith('error:'):
                        print(f"Sidebar toggle script error: {result}")
                
                self.active_webview.evaluateJavaScript_completionHandler_(js, sidebar_completion_handler)
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
            # Undo - implemented safely via JavaScript
            elif key == 'z':
                js_undo = """
                (function(){
                  if (document.activeElement && (document.activeElement.tagName === 'TEXTAREA' || document.activeElement.tagName === 'INPUT' || document.activeElement.contentEditable === 'true')) {
                    document.execCommand('undo');
                  }
                })();
                """
                self.active_webview.evaluateJavaScript_completionHandler_(js_undo, None)

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
        self.perplexity_webview.setFrame_(webview_new_frame)

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

    # WKNavigationDelegate – called when navigation finishes successfully
    def webView_didFinishNavigation_(self, webview, navigation):
        # Page loaded, focus prompt area after small delay to ensure textarea exists
        # Delay 0.1 s, then focus prompt (use NSTimer – PyObjC provides selector call)
        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.1, self, '_focusPromptTimerFired:', None, False)
    
    # WKNavigationDelegate – called when navigation fails
    def webView_didFailNavigation_withError_(self, webview, navigation, error):
        print(f"Navigation failed: {error.localizedDescription()}")
        # Try to reload after a delay if it's a network error
        if "NSURLErrorDomain" in str(error):
            NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                5.0, self, '_retryNavigationTimerFired:', webview, False)
    
    # WKNavigationDelegate – called when provisional navigation fails
    def webView_didFailProvisionalNavigation_withError_(self, webview, navigation, error):
        print(f"Provisional navigation failed: {error.localizedDescription()}")
        # Try to reload after a delay if it's a network error
        if "NSURLErrorDomain" in str(error):
            NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                5.0, self, '_retryNavigationTimerFired:', webview, False)
    
    # Helper to retry navigation after network errors
    def _retryNavigationTimerFired_(self, timer):
        webview = timer.userInfo()
        if webview == self.claude_webview:
            url = NSURL.URLWithString_(CLAUDE_WEBSITE_URL)
        elif webview == self.perplexity_webview:
            url = NSURL.URLWithString_(PERPLEXITY_WEBSITE_URL)
        else:
            url = NSURL.URLWithString_(GEMINI_WEBSITE_URL)
        request = NSURLRequest.requestWithURL_(url)
        webview.loadRequest_(request)
        print("Retrying navigation...")

    # Helper called by timer
    def _focusPromptTimerFired_(self, timer):
        self._focus_prompt_area()
    
    # Helper called by timer after switching services
    def _switchCompleteTimerFired_(self, timer):
        self._focus_prompt_area()
        self._hideSwitchIndicator()
        self.switching_in_progress = False
    
    # Show visual indicator during service switching
    @objc.python_method
    def _showSwitchIndicator(self, message):
        if self.switch_indicator:
            self._hideSwitchIndicator()
            
        content_view = self.window.contentView()
        content_bounds = content_view.bounds()
        
        # Create indicator background
        indicator_width = 200
        indicator_height = 50
        indicator_x = (content_bounds.size.width - indicator_width) / 2
        indicator_y = (content_bounds.size.height - indicator_height) / 2
        
        self.switch_indicator = NSView.alloc().initWithFrame_(
            NSMakeRect(indicator_x, indicator_y, indicator_width, indicator_height)
        )
        self.switch_indicator.setWantsLayer_(True)
        self.switch_indicator.layer().setBackgroundColor_(NSColor.colorWithWhite_alpha_(0.0, 0.8).CGColor())
        self.switch_indicator.layer().setCornerRadius_(10)
        
        # Create label
        label = NSTextField.alloc().initWithFrame_(NSMakeRect(10, 15, indicator_width - 20, 20))
        label.setStringValue_(message)
        label.setBezeled_(False)
        label.setDrawsBackground_(False)
        label.setEditable_(False)
        label.setSelectable_(False)
        label.setAlignment_(NSTextAlignmentCenter)
        label.setFont_(NSFont.boldSystemFontOfSize_(14))
        label.setTextColor_(NSColor.whiteColor())
        
        self.switch_indicator.addSubview_(label)
        content_view.addSubview_(self.switch_indicator)
        
        # Animate appearance
        self.switch_indicator.setAlphaValue_(0.0)
        self.switch_indicator.animator().setAlphaValue_(1.0)
    
    # Hide visual indicator with animation
    @objc.python_method  
    def _hideSwitchIndicator(self):
        if self.switch_indicator:
            # Animate fade out then remove
            def animation_group(context):
                context.setDuration_(0.15)
                self.switch_indicator.animator().setAlphaValue_(0.0)
            
            def completion_handler():
                if self.switch_indicator and self.switch_indicator.superview():
                    self.switch_indicator.removeFromSuperview()
                self.switch_indicator = None
            
            NSAnimationContext.runAnimationGroup_completionHandler_(
                animation_group,
                completion_handler
            )
    
    # Show notification to user
    @objc.python_method
    def _showNotification(self, title, message):
        # Create notification view similar to switch indicator
        content_view = self.window.contentView()
        content_bounds = content_view.bounds()
        
        notification_width = 250
        notification_height = 70
        notification_x = content_bounds.size.width - notification_width - 20
        notification_y = content_bounds.size.height - notification_height - 50
        
        notification_view = NSView.alloc().initWithFrame_(
            NSMakeRect(notification_x, notification_y, notification_width, notification_height)
        )
        notification_view.setWantsLayer_(True)
        notification_view.layer().setBackgroundColor_(NSColor.colorWithWhite_alpha_(0.1, 0.9).CGColor())
        notification_view.layer().setCornerRadius_(8)
        
        # Title label
        title_label = NSTextField.alloc().initWithFrame_(NSMakeRect(10, 40, notification_width - 20, 20))
        title_label.setStringValue_(title)
        title_label.setBezeled_(False)
        title_label.setDrawsBackground_(False)
        title_label.setEditable_(False)
        title_label.setSelectable_(False)
        title_label.setFont_(NSFont.boldSystemFontOfSize_(13))
        title_label.setTextColor_(NSColor.labelColor())
        
        # Message label
        message_label = NSTextField.alloc().initWithFrame_(NSMakeRect(10, 10, notification_width - 20, 25))
        message_label.setStringValue_(message)
        message_label.setBezeled_(False)
        message_label.setDrawsBackground_(False)
        message_label.setEditable_(False)
        message_label.setSelectable_(False)
        message_label.setFont_(NSFont.systemFontOfSize_(11))
        message_label.setTextColor_(NSColor.secondaryLabelColor())
        
        notification_view.addSubview_(title_label)
        notification_view.addSubview_(message_label)
        content_view.addSubview_(notification_view)
        
        # Animate slide-in from right
        original_x = notification_x
        notification_view.setFrame_(NSMakeRect(content_bounds.size.width, notification_y, notification_width, notification_height))
        notification_view.animator().setFrame_(NSMakeRect(original_x, notification_y, notification_width, notification_height))
        
        # Auto-dismiss after 3 seconds with slide-out animation
        def dismiss_notification(timer):
            if notification_view.superview():
                NSAnimationContext.runAnimationGroup_completionHandler_(
                    lambda context: (
                        context.setDuration_(0.3),
                        notification_view.animator().setFrame_(NSMakeRect(content_bounds.size.width, notification_y, notification_width, notification_height))
                    ),
                    lambda: notification_view.removeFromSuperview()
                )
        
        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            3.0, self, '_dismissNotificationTimerFired:', notification_view, False)
    
    # Helper for notification auto-dismiss
    def _dismissNotificationTimerFired_(self, timer):
        notification_view = timer.userInfo()
        if notification_view is None:
            return
            
        content_bounds = self.window.contentView().bounds()
        current_frame = notification_view.frame()
        
        if notification_view.superview():
            def animation_group(context):
                context.setDuration_(0.3)
                notification_view.animator().setFrame_(NSMakeRect(content_bounds.size.width, current_frame.origin.y, current_frame.size.width, current_frame.size.height))
            
            def completion_handler():
                if notification_view and notification_view.superview():
                    notification_view.removeFromSuperview()
            
            NSAnimationContext.runAnimationGroup_completionHandler_(
                animation_group,
                completion_handler
            )

    # Python method to call JS that focuses the active service's textarea / prompt with error handling
    @objc.python_method
    def _focus_prompt_area(self):
        js_focus = """
        (function(){
          try {
            const selectors = [
              '[aria-label="Enter a prompt here"]', // Gemini
              '[data-placeholder="Ask Gemini"]', // Gemini
              '[data-placeholder="Message Claude"]', // Claude
              '[data-placeholder^="Send a message"]', // Claude (covers variations)
              '[placeholder="Ask anything..."]', // Perplexity
              '[aria-label="Ask anything"]', // Perplexity
              'textarea[placeholder*="Ask"]', // Generic Perplexity
              'textarea' // Generic fallback
            ];
            for (const sel of selectors) {
              const el = document.querySelector(sel);
              if (el) {
                el.focus();
                return 'success';
              }
            }
            return 'no_element_found';
          } catch (error) {
            return 'error: ' + error.message;
          }
        })();
        """
        
        def completion_handler(result, error):
            if error:
                print(f"JavaScript error in _focus_prompt_area: {error}")
            elif result and result.startswith('error:'):
                print(f"Focus script error: {result}")
        
        if self.active_webview:
            self.active_webview.evaluateJavaScript_completionHandler_(js_focus, completion_handler)
