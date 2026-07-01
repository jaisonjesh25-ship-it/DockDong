import threading
import logging
import os
import time
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

def get_resource_path(filename):
    if 'RESOURCEPATH' in os.environ:
        return os.path.join(os.environ['RESOURCEPATH'], filename)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

def dispatch_to_main(func):
    """Helper to run functions on the main thread for UI updates"""
    Foundation.dispatch_async(Foundation.dispatch_get_main_queue(), func)

class ScriptHandler(NSObject):
    appDelegate = objc.IBOutlet()

    def userContentController_didReceiveScriptMessage_(self, userContentController, message):
        cmd = message.body()
        logging.debug(f"Received JS command: {cmd}")
        self.appDelegate.handleCommand_(cmd)

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
            image.setSize_(NSMakeSize(22, 22))
            image.setTemplate_(False) # Keep color (red tape)
            self.statusItem.button().setImage_(image)
        else:
            self.statusItem.button().setTitle_("DOCKDONG")

        self.statusItem.button().setAction_(objc.selector(self.togglePopover_, signature=b'v@:@'))
        self.statusItem.button().setTarget_(self)
        
        self.popover = NSPopover.alloc().init()
        self.popover.setBehavior_(NSPopoverBehaviorTransient)
        self.popover.setAnimates_(True)
        
        rect = NSMakeRect(0, 0, 240, 240)
        
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
        
        html_path = get_resource_path("ui.html")
        if os.path.exists(html_path):
            with open(html_path, 'r') as f:
                html_string = f.read()
            self.webview.loadHTMLString_baseURL_(html_string, None)
        else:
            self.webview.loadHTMLString_baseURL_("<html><body>ui.html not found</body></html>", None)
            
        vc = NSViewController.alloc().init()
        vc.setView_(self.webview)
        self.popover.setContentViewController_(vc)
        
        # Start a background timer for checking music (every 5 seconds)
        self.timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            5.0, self, objc.selector(self.checkMusic_, signature=b'v@:@'), None, True
        )

    def togglePopover_(self, sender):
        if self.popover.isShown():
            self.popover.performClose_(sender)
        else:
            self.popover.showRelativeToRect_ofView_preferredEdge_(sender.bounds(), sender, NSRectEdgeMinY)

    def handleCommand_(self, cmd):
        if cmd == "quit":
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

    def checkMusic_(self, sender):
        if self.running:
            self.run_backend_once()

    def update_js_status(self, text):
        js = f"window.setStatusText('{text}');"
        self.webview.evaluateJavaScript_completionHandler_(js, None)
        
    def show_notification(self, title, subtitle, info):
        notification = NSUserNotification.alloc().init()
        notification.setTitle_(title)
        notification.setSubtitle_(subtitle)
        notification.setInformativeText_(info)
        NSUserNotificationCenter.defaultUserNotificationCenter().deliverNotification_(notification)

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
