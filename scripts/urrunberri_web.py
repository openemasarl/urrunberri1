#!/usr/bin/env python3
# UrrunBerri OS — Navigateur web GTK/WebKit (barre d'adresse) — Sortie : Ctrl+Alt+Q
import sys
import os
os.environ.setdefault('WEBKIT_DISABLE_COMPOSITING_MODE', '1')

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.1')
from gi.repository import Gtk, Gdk, WebKit2, GLib


def normalize_url(text):
    text = text.strip()
    if not text:
        return None
    if '://' not in text:
        text = 'https://' + text
    return text


def main():
    if len(sys.argv) < 2:
        print("Usage: urrunberri_web.py <url>", file=sys.stderr)
        sys.exit(1)
    start_url = sys.argv[1]

    win = Gtk.Window()
    win.set_title("UrrunBerri Web")
    win.fullscreen()
    win.connect("destroy", Gtk.main_quit)

    ctx = WebKit2.WebContext.get_default()
    try:
        ctx.set_sandbox_enabled(False)
    except AttributeError:
        pass
    ctx.set_tls_errors_policy(WebKit2.TLSErrorsPolicy.IGNORE)

    view = WebKit2.WebView.new_with_context(ctx)

    bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
    bar.set_margin_top(4); bar.set_margin_bottom(4)
    bar.set_margin_start(4); bar.set_margin_end(4)

    btn_back = Gtk.Button(label="\u25C0")
    btn_fwd = Gtk.Button(label="\u25B6")
    btn_reload = Gtk.Button(label="\u21BB")
    url_entry = Gtk.Entry(); url_entry.set_hexpand(True)
    btn_go = Gtk.Button(label="Aller")
    btn_quit = Gtk.Button(label="\u2715 Quitter")

    bar.pack_start(btn_back, False, False, 0)
    bar.pack_start(btn_fwd, False, False, 0)
    bar.pack_start(btn_reload, False, False, 0)
    bar.pack_start(url_entry, True, True, 0)
    bar.pack_start(btn_go, False, False, 0)
    bar.pack_start(btn_quit, False, False, 0)

    def go(_=None):
        u = normalize_url(url_entry.get_text())
        if u:
            view.load_uri(u)

    btn_go.connect("clicked", go)
    url_entry.connect("activate", go)
    btn_back.connect("clicked", lambda _: view.go_back() if view.can_go_back() else None)
    btn_fwd.connect("clicked", lambda _: view.go_forward() if view.can_go_forward() else None)
    btn_reload.connect("clicked", lambda _: view.reload())
    btn_quit.connect("clicked", lambda _: Gtk.main_quit())

    def on_load_changed(v, event):
        if event == WebKit2.LoadEvent.COMMITTED:
            uri = v.get_uri()
            if uri:
                url_entry.set_text(uri)
            btn_back.set_sensitive(v.can_go_back())
            btn_fwd.set_sensitive(v.can_go_forward())

    view.connect("load-changed", on_load_changed)

    vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    vbox.pack_start(bar, False, False, 0)
    vbox.pack_start(view, True, True, 0)
    win.add(vbox)

    def on_key(widget, event):
        ctrl = event.state & Gdk.ModifierType.CONTROL_MASK
        alt = event.state & Gdk.ModifierType.MOD1_MASK
        if ctrl and alt and event.keyval in (Gdk.KEY_q, Gdk.KEY_Q):
            Gtk.main_quit()
            return True
        return False

    win.connect("key-press-event", on_key)
    view.load_uri(start_url)
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
