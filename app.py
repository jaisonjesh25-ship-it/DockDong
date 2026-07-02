import threading
import logging
import os
import time
import json
import subprocess
import objc
from AppKit import *
from WebKit import WKWebView, WKWebViewConfiguration, WKUserContentController
import Foundation

from backend import update_wallpaper_once

# Basic logging setup
log_dir = os.path.expanduser("~/Library/Logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "dockdong.log")
logging.basicConfig(
    filename=log_file,
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
import sys
sys.stdout = open(log_file, 'a')
sys.stderr = open(log_file, 'a')

def get_resource_path(filename):
    if 'RESOURCEPATH' in os.environ:
        return os.path.join(os.environ['RESOURCEPATH'], filename)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

import PyObjCTools.AppHelper

def dispatch_to_main(func):
    """Helper to run functions on the main thread for UI updates"""
    PyObjCTools.AppHelper.callAfter(func)

class ScriptHandler(NSObject):
    appDelegate = objc.IBOutlet()

    def userContentController_didReceiveScriptMessage_(self, userContentController, message):
        cmd = message.body()
        logging.debug(f"Received JS command: {cmd}")
        self.appDelegate.handleCommand_(cmd)

class TrackingView(NSView):
    def updateTrackingAreas(self):
        objc.super(TrackingView, self).updateTrackingAreas()
        if hasattr(self, 'trackingArea') and self.trackingArea:
            self.removeTrackingArea_(self.trackingArea)
        options = NSTrackingMouseEnteredAndExited | NSTrackingActiveAlways | NSTrackingInVisibleRect
        self.trackingArea = NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(
            self.bounds(), options, self, None
        )
        self.addTrackingArea_(self.trackingArea)

    def mouseExited_(self, event):
        app = NSApplication.sharedApplication()
        delegate = app.delegate()
        if delegate and hasattr(delegate, 'fade_and_close'):
            delegate.fade_and_close()

class AppDelegate(NSObject):
    def applicationDidFinishLaunching_(self, notification):
        logging.info("dockdong app started")
        
        self.app_name = "spotify"
        self.last_track = None
        self.running = False
        self.busy = False
        self.status = "Idle"

        self.statusItem = NSStatusBar.systemStatusBar().statusItemWithLength_(NSSquareStatusItemLength)
        
        icon_path = get_resource_path("icon.png")
        if os.path.exists(icon_path):
            image = NSImage.alloc().initWithContentsOfFile_(icon_path)
            # Set the image size to 22x22 points so the 44x44 pixels render correctly on Retina displays
            image.setSize_((22, 22))
            image.setTemplate_(False) # Keep color (red tape)
            self.statusItem.button().setImage_(image)
        else:
            self.statusItem.button().setTitle_("DOCKDONG")

        self.statusItem.button().setAction_("togglePopover:")
        self.statusItem.button().setTarget_(self)
        
        self.popover = NSPopover.alloc().init()
        self.popover.setBehavior_(NSPopoverBehaviorApplicationDefined)
        self.popover.setAnimates_(True)
        
        rect = ((0, 0), (320, 290))
        
        # Setup WKWebView
        config = WKWebViewConfiguration.alloc().init()
        userContentController = WKUserContentController.alloc().init()
        
        self.handler = ScriptHandler.alloc().init()
        self.handler.appDelegate = self
        userContentController.addScriptMessageHandler_name_(self.handler, "python")
        config.setUserContentController_(userContentController)
        
        self.webview = WKWebView.alloc().initWithFrame_configuration_(rect, config)
        # Disable background drawing so it perfectly matches the popover
        self.webview.setValue_forKey_(False, "drawsBackground")
        
        self.tracking_view = TrackingView.alloc().initWithFrame_(rect)
        self.webview.setFrame_(self.tracking_view.bounds())
        self.tracking_view.addSubview_(self.webview)
        
        html_path = get_resource_path("ui.html")
        if os.path.exists(html_path):
            with open(html_path, 'r') as f:
                html_string = f.read()
            self.webview.loadHTMLString_baseURL_(html_string, None)
        else:
            self.webview.loadHTMLString_baseURL_("<html><body>ui.html not found</body></html>", None)
            
        vc = NSViewController.alloc().init()
        vc.setView_(self.tracking_view)
        self.popover.setContentViewController_(vc)
        
        # Start a background timer for checking music (every 5 seconds)
        self.timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            5.0, self, objc.selector(self.checkMusic_, signature=b'v@:@'), None, True
        )

    @objc.IBAction
    def togglePopover_(self, sender):
        if self.popover.isShown():
            self.popover.performClose_(sender)
        else:
            NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
            self.popover.showRelativeToRect_ofView_preferredEdge_(sender.bounds(), sender, NSRectEdgeMinY)
            
            # Make sure the popover window appears over full-screen apps
            window = self.popover.contentViewController().view().window()
            if window:
                window.setLevel_(NSStatusWindowLevel)
                window.setCollectionBehavior_(NSWindowCollectionBehaviorCanJoinAllSpaces | NSWindowCollectionBehaviorFullScreenAuxiliary)

    def handleCommand_(self, cmd):
        if cmd == "quit":
            NSStatusBar.systemStatusBar().removeStatusItem_(self.statusItem)
            NSApplication.sharedApplication().terminate_(self)
        elif cmd == "use_spotify":
            self.app_name = "spotify"
            self.last_track = None
            self.show_notification("dockdong", "Source changed", "Using Spotify")
        elif cmd == "use_apple_music":
            self.app_name = "apple_music"
            self.last_track = None
            self.show_notification("dockdong", "Source changed", "Using Apple Music")
        elif cmd == "start":
            self.running = True
        elif cmd == "stop":
            self.running = False
        elif cmd == "update_now":
            self.run_backend_once()
        elif cmd == "close_popover":
            self.popover.performClose_(self)

    def fade_and_close(self):
        if self.popover.isShown():
            js = "document.body.style.transition = 'opacity 0.2s ease-out'; document.body.style.opacity = '0';"
            self.webview.evaluateJavaScript_completionHandler_(js, None)
            NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                0.2, self, objc.selector(self.finishClose_, signature=b'v@:@'), None, False
            )
            
    def finishClose_(self, sender):
        self.popover.performClose_(self)
        js = "document.body.style.opacity = '1';"
        self.webview.evaluateJavaScript_completionHandler_(js, None)

    def checkMusic_(self, sender):
        if self.running:
            self.run_backend_once()

    def update_js_status(self, text):
        safe_text = json.dumps(str(text))
        js = f"window.setStatusText({safe_text});"
        self.webview.evaluateJavaScript_completionHandler_(js, None)
        
    def show_notification(self, title, subtitle, info):
        """Show a macOS notification using osascript (NSUserNotification is deprecated)."""
        # Escape double quotes for AppleScript string safety
        safe_title = str(title).replace('"', '\\"')
        safe_subtitle = str(subtitle).replace('"', '\\"')
        safe_info = str(info).replace('"', '\\"')
        script = f'display notification "{safe_info}" with title "{safe_title}" subtitle "{safe_subtitle}"'
        try:
            subprocess.Popen(
                ["osascript", "-e", script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            logging.warning(f"Notification failed: {e}")

    def run_backend_once(self):
        if self.busy:
            return
        self.busy = True
        logging.debug("Starting backend worker thread")
        thread = threading.Thread(target=self.backend_worker)
        thread.daemon = True
        thread.start()

    def backend_worker(self):
        try:
            result = update_wallpaper_once(self.app_name, self.last_track)
            logging.info(f"Update result: {result}")
            
            self.last_track = result.get("last_track", self.last_track)
            status = result.get("status", "unknown")
            status_text = status.replace('_', ' ').title()
            
            track = result.get("track", "Unknown track")
            artist = result.get("artist", "Unknown artist")

            def update_ui():
                self.update_js_status(status_text)
                if status == "updated":
                    self.show_notification("Wallpaper Updated", artist, track)
                    
            dispatch_to_main(update_ui)

        except Exception as error:
            logging.error(f"Update failed with error: {error}", exc_info=True)
            
            def handle_error():
                self.update_js_status("Error")
                self.show_notification("dockdong", "Update failed", str(error))
                
            dispatch_to_main(handle_error)
            
        finally:
            self.busy = False

def main():
    app = NSApplication.sharedApplication()
    delegate = AppDelegate.alloc().init()
    app.setDelegate_(delegate)
    app.run()

if __name__ == "__main__":
    main()
