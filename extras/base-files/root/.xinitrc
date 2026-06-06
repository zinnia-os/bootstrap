#!/bin/sh

export NO_AT_BRIDGE=1
export GTK_A11Y=none

export GDK_PIXBUF_MODULE_FILE=/usr/lib/gdk-pixbuf-2.0/2.10.0/loaders.cache

mkdir -p /var/cache/zinnia
gdk-pixbuf-query-loaders --update-cache 2>/dev/null

if [ ! -e /var/cache/zinnia/desktop-init-v2 ]; then
    fc-cache -f 2>/dev/null
    for d in /usr/share/icons/*/; do
        [ -f "${d}index.theme" ] && gtk-update-icon-cache -qf "$d" 2>/dev/null
    done
    : > /var/cache/zinnia/desktop-init-v2
fi

exec startxfce4
