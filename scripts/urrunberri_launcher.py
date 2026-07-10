#!/usr/bin/env python3
# =============================================================================
#  UrrunBerri OS — GTK WebView Launcher
#  Replaces Firefox kiosk for the login interface
#  Author : Mathieu Cadi — Openema SARL
#  GitHub : https://github.com/matthewc00002/urrunberri1
# =============================================================================

import gi
import sys
import signal
import os

gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.1')
from gi.repository import Gtk, WebKit2, Gdk, GLib

URL = "http://127.0.0.1:7070/splash/login.html"
WIN_W = 520
WIN_H = 820
TITLE = "UrrunBerri OS"


class UrrunBerriWindow(Gtk.Window):

    def __init__(self):
        super().__init__(title=TITLE)

        # Window setup
        self.set_default_size(WIN_W, WIN_H)
        self.set_resizable(False)
        self.set_decorated(False)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_keep_above(True)

        # Set background color
        css = Gtk.CssProvider()
        css.load_from_data(b"window { background-color: #eef2f7; }")
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # WebView setup
        settings = WebKit2.Settings()
        settings.set_property('enable-developer-extras', False)
        settings.set_property('enable-javascript', True)
        settings.set_property('enable-plugins', False)
        settings.set_property('enable-page-cache', False)

        # Disable password autofill/suggestions
        try:
            settings.set_property('enable-private-browsing', True)
        except:
            pass

        self.webview = WebKit2.WebView()
        self.webview.set_settings(settings)

        # Disable context menu (right-click)
        self.webview.connect('context-menu', lambda *a: True)

        # Load the login page
        self.webview.load_uri(URL)

        self.add(self.webview)
        self.connect('destroy', self.on_destroy)
        self.connect('delete-event', self.on_delete)

    def on_destroy(self, widget):
        Gtk.main_quit()

    def on_delete(self, widget, event):
        Gtk.main_quit()
        return False


def on_signal(sig, frame):
    """Handle SIGTERM/SIGINT for clean shutdown"""
    Gtk.main_quit()


def main():
    # Handle signals for clean shutdown (when boot.sh kills us)
    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)

    # Also handle via GLib for thread safety
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, Gtk.main_quit)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, Gtk.main_quit)

    win = UrrunBerriWindow()
    win.show_all()
    Gtk.main()


if __name__ == '__main__':
    main()
