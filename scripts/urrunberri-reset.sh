#!/bin/bash
# =============================================================================
#  UrrunBerri OS — Desinstallation complete et reinstallation
#  Openema SARL — Mathieu Cadi
#
#  Ce script supprime TOUT ce qui a ete installe par UrrunBerri OS,
#  purge toutes les configurations, puis reinstalle depuis GitHub.
#
#  NOTE : SSH n'est pas modifie pour permettre la reinstallation a distance.
#
#  Utilisation : bash urrunberri-reset.sh
# =============================================================================

set -e

[[ $EUID -ne 0 ]] && echo "[ERREUR] Lancez en root." && exit 1

echo "=================================================="
echo "   UrrunBerri OS - Desinstallation complete"
echo "   Openema SARL"
echo "=================================================="
echo ""

# ── 1. ARRETER TOUS LES PROCESSUS ────────────────────────────────────────────
echo "[1/7] Arret de tous les processus..."
systemctl stop lightdm 2>/dev/null || true
pkill -9 xfreerdp3 2>/dev/null || true
pkill -9 xfreerdp 2>/dev/null || true
pkill -9 -f boot.sh 2>/dev/null || true
pkill -9 -f urrunberri_server.py 2>/dev/null || true
pkill -9 -f urrunberri_launcher.py 2>/dev/null || true
pkill -9 firefox-esr 2>/dev/null || true
pkill -9 zenity 2>/dev/null || true
pkill -9 unclutter 2>/dev/null || true
pkill -9 openbox 2>/dev/null || true
pkill -9 -f Xorg 2>/dev/null || true
sleep 3
echo "   Processus arretes."

# ── 2. DESINSTALLER TOUS LES PAQUETS ─────────────────────────────────────────
echo "[2/7] Desinstallation de tous les paquets..."
apt-get remove --purge -y \
    openbox \
    lightdm \
    lightdm-gtk-greeter \
    firefox-esr \
    xterm \
    zenity \
    freerdp3-x11 \
    tigervnc-viewer \
    unclutter \
    x11-xserver-utils \
    fonts-dejavu \
    plymouth \
    plymouth-themes \
    python3-gi \
    python3-gi-cairo \
    gir1.2-gtk-3.0 \
    gir1.2-webkit2-4.1 \
    xdg-desktop-portal \
    xdg-desktop-portal-gtk \
    at-spi2-core \
    2>/dev/null || true
echo "   Paquets desinstalles."

# ── 3. SUPPRIMER LES DEPENDANCES ORPHELINES ──────────────────────────────────
echo "[3/7] Suppression des dependances orphelines..."
apt-get autoremove --purge -y 2>/dev/null || true
apt-get clean
echo "   Dependances orphelines supprimees."

# ── 4. SUPPRIMER TOUS LES FICHIERS APPLICATION ──────────────────────────────
echo "[4/7] Suppression des fichiers application..."
rm -rf /opt/urrunberri-os
rm -rf /etc/urrunberri-os
rm -f /tmp/urrunberri_action.txt
rm -f /tmp/urrunberri_login.txt
rm -f /tmp/usb-share 2>/dev/null
echo "   Fichiers application supprimes."

# ── 5. SUPPRIMER TOUTES LES CONFIGURATIONS SYSTEME ──────────────────────────
echo "[5/7] Suppression des configurations systeme..."
# Openbox
rm -rf /root/.config/openbox
# LightDM
rm -f /etc/lightdm/lightdm.conf
rm -rf /etc/lightdm/lightdm.conf.d
# Xorg
rm -f /etc/X11/xorg.conf.d/99-urrunberri.conf
# Firefox (toutes traces)
rm -rf /etc/firefox-esr
rm -rf /usr/lib/firefox-esr
rm -rf /root/.mozilla
rm -rf /root/.cache/mozilla
# Plymouth
rm -rf /usr/share/plymouth/themes/urrunberri
# FreeRDP
rm -rf /root/.config/freerdp
rm -rf /root/.local/share/freerdp
# Symlinks
rm -f /usr/local/bin/xfreerdp
# Cache GTK/WebKit
rm -rf /root/.cache/webkit
rm -rf /root/.local/share/webkit
rm -rf /root/.cache/gstreamer*
echo "   Configurations systeme supprimees."

# ── 6. RESTAURER PAM ─────────────────────────────────────────────────────────
echo "[6/7] Restauration PAM..."
if [ -f /etc/pam.d/lightdm-autologin ]; then
    sed -i 's/^# \(auth\s*required\s*pam_succeed_if.so.*user != root.*\)/\1/' /etc/pam.d/lightdm-autologin 2>/dev/null || true
fi
echo "   PAM restaure."

# ── 7. RESTAURER GRUB ────────────────────────────────────────────────────────
echo "[7/7] Restauration GRUB..."
if [ -f /etc/default/grub ]; then
    sed -i 's/GRUB_CMDLINE_LINUX_DEFAULT=.*/GRUB_CMDLINE_LINUX_DEFAULT="quiet"/' /etc/default/grub
    sed -i 's/GRUB_TIMEOUT=.*/GRUB_TIMEOUT=5/' /etc/default/grub
    update-grub 2>/dev/null || true
fi
echo "   GRUB restaure."

echo ""
echo "=================================================="
echo "   Desinstallation complete terminee."
echo ""
echo "   Le systeme est propre. SSH n'a pas ete modifie."
echo ""
echo "   Pour reinstaller (branche test) :"
echo "   curl -fsSL https://raw.githubusercontent.com/"
echo "   openemasarl/urrunberri1/test/scripts/"
echo "   install.sh | bash && reboot"
echo ""
echo "   Pour reinstaller (branche main) :"
echo "   curl -fsSL https://raw.githubusercontent.com/"
echo "   openemasarl/urrunberri1/main/scripts/"
echo "   install.sh | bash && reboot"
echo "=================================================="
