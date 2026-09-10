#!/bin/bash
# =============================================================================
#  UrrunBerri OS — Install Script
#  Debian 13 Trixie — Root autologin — xfreerdp3
#  Author : Mathieu Cadi — Openema SARL
#  GitHub : https://github.com/openemasarl/urrunberri1
#  Branch : main (GTK WebView — sans Firefox)
# =============================================================================

set -e

GITHUB_RAW="https://raw.githubusercontent.com/openemasarl/urrunberri1/main"
INSTALL_DIR="/opt/urrunberri-os"

info()  { echo "[UrrunBerri OS] $1"; }
error() { echo "[ERREUR] $1"; exit 1; }

[[ $EUID -ne 0 ]] && error "Lancez ce script en root : bash install.sh"

info "=== UrrunBerri OS — Installation Debian 13 Trixie ==="
info "=== Branche : main (GTK WebView) ==="

# ── PACKAGES ──────────────────────────────────────────────────────────────────
info "Installation des paquets..."
sed -i "s|http://deb.debian.org/debian|http://ftp.fr.debian.org/debian|g" /etc/apt/sources.list
apt-get update -qq
apt-get install -y \
    xorg \
    numlockx \
    openbox \
    lightdm \
    lightdm-gtk-greeter \
    xterm \
    zenity \
    python3 \
    python3-gi \
    python3-gi-cairo \
    gir1.2-gtk-3.0 \
    gir1.2-webkit2-4.1 \
    freerdp3-x11 \
    tigervnc-viewer \
    tigervnc-tools \
    openssh-server \
    netcat-openbsd \
    x11-xserver-utils \
    fonts-dejavu \
    plymouth \
    plymouth-themes \
    curl \
    network-manager \
    wpasupplicant \
    resolvconf
info "Paquets installes"

# -- NETWORKMANAGER (requis par le module Wi-Fi) ------------------------------
info "Configuration de NetworkManager..."
mkdir -p /etc/NetworkManager/conf.d
cat > /etc/NetworkManager/conf.d/no-dns.conf << 'NMEOF'
[main]
dns=none
NMEOF
systemctl enable NetworkManager >/dev/null 2>&1 || true
systemctl start NetworkManager >/dev/null 2>&1 || true
info "NetworkManager active"

# -- DNS (resolvconf) ---------------------------------------------------------
info "Configuration DNS..."
mkdir -p /etc/resolvconf/resolv.conf.d
cat > /etc/resolvconf/resolv.conf.d/base << 'DNSEOF'
nameserver 8.8.8.8
nameserver 1.1.1.1
DNSEOF
resolvconf -u >/dev/null 2>&1 || true
info "DNS configure"

# ── CONFIG TIGERVNC (desactive infobulle et dialogue erreur) ──────────────────
mkdir -p /root/.config/tigervnc
cat > /root/.config/tigervnc/default << 'VNCEOF'
ShortcutModifiers=
AlertOnFatalError=0
VNCEOF
info "Configuration TigerVNC appliquee"

# ── SUPPRESSION UNCLUTTER (masquait le curseur souris) ────────────────────────
apt-get remove -y unclutter 2>/dev/null || true
pkill unclutter 2>/dev/null || true

# ── XFREERDP3 SYMLINK ─────────────────────────────────────────────────────────
ln -sf /usr/bin/xfreerdp3 /usr/local/bin/xfreerdp 2>/dev/null || true
info "xfreerdp → xfreerdp3"

# ── DIRECTORIES ───────────────────────────────────────────────────────────────
mkdir -p "$INSTALL_DIR/scripts"
mkdir -p "$INSTALL_DIR/splash"
mkdir -p /etc/urrunberri-os
touch /etc/urrunberri-os/saved_connections.csv

# ── VERSION FILE ──────────────────────────────────────────────────────────────
info "Enregistrement de la version..."
APP_VERSION=$(curl -fsSL "$GITHUB_RAW/VERSION" 2>/dev/null | head -1 | tr -d '[:space:]')
[[ -z "$APP_VERSION" ]] && APP_VERSION="?"
INSTALL_DATE=$(date '+%Y-%m-%d %H:%M:%S')
cat > /etc/urrunberri-os/version << VERSIONEOF
version=$APP_VERSION
date_installation=$INSTALL_DATE
branche=main
VERSIONEOF
info "Version installee : $APP_VERSION ($INSTALL_DATE) [branche main]"

# ── OPENBOX FOR ROOT ──────────────────────────────────────────────────────────
mkdir -p /root/.config/openbox
cat > /root/.config/openbox/autostart << 'AUTOSTART'
#!/bin/bash
xset s off
xset s noblank
xset -dpms
xsetroot -solid "#eef2f7"
sleep 2
bash /opt/urrunberri-os/scripts/boot.sh
AUTOSTART
chmod +x /root/.config/openbox/autostart

# ── OPENBOX RC.XML (disable menus and shortcuts) ─────────────────────────────
rm -f /root/.config/openbox/rc.xml

cat > /root/.config/openbox/menu.xml << 'MENUXML'
<?xml version="1.0" encoding="UTF-8"?>
<openbox_menu xmlns="http://openbox.org/3.4/menu">
  <menu id="root-menu" label="Menu">
  </menu>
</openbox_menu>
MENUXML
info "Menu desktop vide configure"
info "Openbox configure pour root"

# ── LIGHTDM ROOT AUTOLOGIN ────────────────────────────────────────────────────
cat > /etc/lightdm/lightdm.conf << 'LIGHTDM'
[Seat:*]
autologin-user=root
autologin-user-timeout=0
user-session=openbox
greeter-hide-users=true
LIGHTDM
info "LightDM autologin root configure"

# ── FIX PAM ROOT AUTOLOGIN ────────────────────────────────────────────────────
sed -i 's/^auth\s*required\s*pam_succeed_if.so.*user != root.*/# &/' /etc/pam.d/lightdm-autologin
info "PAM root autologin fix applique"

# ── XORG VT SWITCH ────────────────────────────────────────────────────────────
mkdir -p /etc/X11/xorg.conf.d
cat > /etc/X11/xorg.conf.d/99-urrunberri.conf << 'XORG'
Section "ServerFlags"
    Option "DontVTSwitch" "false"
    Option "DontZap" "false"
EndSection
XORG

# ── SSH ROOT LOGIN ────────────────────────────────────────────────────────────
sed -i 's/#PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config
grep -q "PermitRootLogin yes" /etc/ssh/sshd_config || echo "PermitRootLogin yes" >> /etc/ssh/sshd_config

# ── DOWNLOAD APP FILES ────────────────────────────────────────────────────────
info "Telechargement des fichiers depuis GitHub (branche main)..."
curl -fsSL "$GITHUB_RAW/scripts/boot.sh" -o "$INSTALL_DIR/scripts/boot.sh"
curl -fsSL "$GITHUB_RAW/scripts/urrunberri_server.py" -o "$INSTALL_DIR/scripts/urrunberri_server.py"
curl -fsSL "$GITHUB_RAW/scripts/urrunberri_launcher.py" -o "$INSTALL_DIR/scripts/urrunberri_launcher.py"
curl -fsSL "$GITHUB_RAW/splash/login.html" -o "$INSTALL_DIR/splash/login.html"
curl -fsSL "$GITHUB_RAW/splash/network.html" -o "$INSTALL_DIR/splash/network.html"
curl -fsSL "$GITHUB_RAW/client-ui/splash/logo.png" -o "$INSTALL_DIR/splash/logo.png" 2>/dev/null || true
curl -fsSL "$GITHUB_RAW/client-ui/splash/urrunberri.png" -o "$INSTALL_DIR/splash/urrunberri.png" 2>/dev/null || true

chmod +x "$INSTALL_DIR/scripts/boot.sh"
chmod +x "$INSTALL_DIR/scripts/urrunberri_server.py"
chmod +x "$INSTALL_DIR/scripts/urrunberri_launcher.py"
info "Fichiers telecharges"

# ── PLYMOUTH THEME ────────────────────────────────────────────────────────────
info "Installation du theme Plymouth..."
mkdir -p /usr/share/plymouth/themes/urrunberri
curl -fsSL "$GITHUB_RAW/plymouth/urrunberri.plymouth" -o /usr/share/plymouth/themes/urrunberri/urrunberri.plymouth 2>/dev/null || true
curl -fsSL "$GITHUB_RAW/plymouth/urrunberri.script" -o /usr/share/plymouth/themes/urrunberri/urrunberri.script 2>/dev/null || true
curl -fsSL "$GITHUB_RAW/client-ui/splash/logo.png" -o /usr/share/plymouth/themes/urrunberri/logo.png 2>/dev/null || true
plymouth-set-default-theme urrunberri 2>/dev/null || true
update-initramfs -u 2>/dev/null || true
info "Theme Plymouth installe"

# ── GRUB SILENT BOOT ──────────────────────────────────────────────────────────
sed -i 's/GRUB_CMDLINE_LINUX_DEFAULT=.*/GRUB_CMDLINE_LINUX_DEFAULT="quiet splash loglevel=0 systemd.show_status=0"/' /etc/default/grub
sed -i 's/GRUB_TIMEOUT=.*/GRUB_TIMEOUT=0/' /etc/default/grub
update-grub 2>/dev/null || true
info "GRUB demarrage silencieux configure"

# ── ENABLE SERVICES ───────────────────────────────────────────────────────────
systemctl enable lightdm
systemctl enable ssh
systemctl start ssh
systemctl enable getty@tty2.service
systemctl start getty@tty2.service
systemctl daemon-reload

# Setup admin scripts
mkdir -p /root/install /root/uninstall
echo '#!/bin/bash' > /root/install/urrunberri.sh
echo 'curl -fsSL https://raw.githubusercontent.com/openemasarl/urrunberri1/main/scripts/install.sh | bash && reboot' >> /root/install/urrunberri.sh
echo '#!/bin/bash' > /root/uninstall/urrunberri.sh
echo 'curl -fsSL https://raw.githubusercontent.com/openemasarl/urrunberri1/main/scripts/urrunberri-reset.sh | bash' >> /root/uninstall/urrunberri.sh
chmod +x /root/install/urrunberri.sh /root/uninstall/urrunberri.sh
# Restauration des connexions sauvegardees
if [ -f /root/urrunberri-backup/saved_connections.csv ]; then
    cp /root/urrunberri-backup/saved_connections.csv /etc/urrunberri-os/saved_connections.csv
    info "Connexions precedentes restaurees depuis /root/urrunberri-backup/"
fi
info "Scripts admin disponibles dans /root/install/ et /root/uninstall/"
info "=== Installation terminee (branche main — GTK WebView) ==="
info "Version : $APP_VERSION"
info "Redemarrez avec : reboot"
info "SSH root : ssh root@IP (PermitRootLogin active)"
info "Verifier la version : cat /etc/urrunberri-os/version"
