#!/bin/bash
# =============================================================================
#  UrrunBerri OS — Build Offline ISO (Option 2 — No Internet Required)
#  Openema SARL — Mathieu Cadi
#
#  This script uses simple-cdd to build a fully self-contained Debian ISO
#  with ALL UrrunBerri OS packages pre-included. No internet is needed
#  during installation on the target machine.
#
#  Requires: simple-cdd, curl, root access, ~2GB disk space
#  Run on: Debian dual-boot machine
#
#  Usage: sudo bash build-offline-iso.sh
# =============================================================================

set -e

WORK_DIR="/tmp/urrunberri-offline-build"
PROFILE_DIR="$WORK_DIR/profiles"
OUTPUT_DIR="$WORK_DIR/images"
GITHUB_RAW="https://raw.githubusercontent.com/openemasarl/urrunberri1"
BRANCH="test"

echo "=================================================="
echo "  UrrunBerri OS — ISO Builder (Offline / Complete)"
echo "  Openema SARL"
echo "=================================================="
echo ""

[[ $EUID -ne 0 ]] && echo "[ERREUR] Lancez en root : sudo bash $0" && exit 1

# ── INSTALL DEPENDENCIES ─────────────────────────────────────────────────────
echo "[1/5] Installation des dependances..."
apt-get update -qq
apt-get install -y simple-cdd curl reprepro xorriso

# ── CREATE PROFILE ───────────────────────────────────────────────────────────
echo "[2/5] Creation du profil UrrunBerri..."
mkdir -p "$PROFILE_DIR"

# Package list — all packages UrrunBerri needs
cat > "$PROFILE_DIR/urrunberri.packages" << 'EOF'
curl
ca-certificates
openssh-server
sudo
openbox
lightdm
lightdm-gtk-greeter
xterm
zenity
freerdp3-x11
x11-xserver-utils
fonts-dejavu
python3
python3-gi
python3-gi-cairo
gir1.2-gtk-3.0
gir1.2-webkit2-4.1
xdg-utils
netcat-openbsd
plymouth
plymouth-themes
EOF

# Preseed for the profile
cat > "$PROFILE_DIR/urrunberri.preseed" << 'PRESEED'
# ── LOCALE & KEYBOARD ────────────────────────────────────────────────────────
d-i keyboard-configuration/xkb-keymap select fr

# ── NETWORK ───────────────────────────────────────────────────────────────────
d-i netcfg/disable_autoconfig boolean true
# Network fields NOT preseeded — installer will ask

# ── CLOCK & TIMEZONE ──────────────────────────────────────────────────────────
d-i clock-setup/utc boolean true
d-i time/zone string Europe/Paris
d-i clock-setup/ntp boolean true

# ── ROOT ACCOUNT ──────────────────────────────────────────────────────────────
d-i passwd/root-login boolean true

# ── USER ACCOUNT ──────────────────────────────────────────────────────────────
d-i passwd/make-user boolean true
d-i passwd/user-fullname string Mathieu Cadi
d-i passwd/username string matt
d-i passwd/user-password-again password openema
d-i passwd/user-password password openema

# ── PARTITIONING ──────────────────────────────────────────────────────────────
d-i partman-auto/method string regular
d-i partman-auto/choose_recipe select atomic
d-i partman-partitioning/confirm_write_new_label boolean true
d-i partman/choose_partition select finish
d-i partman/confirm boolean true
d-i partman/confirm_nooverwrite boolean true

# ── APT ───────────────────────────────────────────────────────────────────────
d-i apt-setup/non-free-firmware boolean true
d-i apt-setup/contrib boolean true
d-i apt-setup/non-free boolean true

# ── PACKAGES ──────────────────────────────────────────────────────────────────
d-i pkgsel/upgrade select full-upgrade
popularity-contest popularity-contest/participate boolean false

# ── GRUB ──────────────────────────────────────────────────────────────────────
d-i grub-installer/only_debian boolean true
d-i grub-installer/bootdev string default

# ── FINISH ────────────────────────────────────────────────────────────────────
d-i finish-install/reboot_in_progress note
PRESEED

# Post-install script — downloads UrrunBerri scripts from GitHub
cat > "$PROFILE_DIR/urrunberri.postinst" << POSTINST
#!/bin/bash
# UrrunBerri OS — Post-Installation Script (runs in target chroot)

# Enable root SSH
sed -i 's/^#PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config
sed -i 's/^PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config

# Create directories
mkdir -p /opt/urrunberri-os/scripts
mkdir -p /opt/urrunberri-os/splash
mkdir -p /etc/urrunberri-os

# Download all UrrunBerri files from GitHub
BRANCH="$BRANCH"
BASE="$GITHUB_RAW/\$BRANCH"

curl -fsSL "\$BASE/scripts/boot.sh" -o /opt/urrunberri-os/scripts/boot.sh
curl -fsSL "\$BASE/scripts/urrunberri_server.py" -o /opt/urrunberri-os/scripts/urrunberri_server.py
curl -fsSL "\$BASE/scripts/urrunberri_launcher.py" -o /opt/urrunberri-os/scripts/urrunberri_launcher.py
curl -fsSL "\$BASE/client-ui/splash/login.html" -o /opt/urrunberri-os/splash/login.html
curl -fsSL "\$BASE/client-ui/splash/logo.png" -o /opt/urrunberri-os/splash/logo.png
curl -fsSL "\$BASE/client-ui/splash/urrunberri.png" -o /opt/urrunberri-os/splash/urrunberri.png

chmod +x /opt/urrunberri-os/scripts/boot.sh

# Write version
cat > /etc/urrunberri-os/version << VEREOF
version=5.0
branche=\$BRANCH
installation=iso-offline
date=\$(date +%Y-%m-%d)
VEREOF

touch /etc/urrunberri-os/saved_connections.csv

# Configure LightDM autologin as root
mkdir -p /etc/lightdm/lightdm.conf.d
cat > /etc/lightdm/lightdm.conf.d/50-urrunberri.conf << LDMEOF
[Seat:*]
autologin-user=root
autologin-user-timeout=0
user-session=openbox
greeter-session=lightdm-gtk-greeter
LDMEOF

# Allow root autologin in PAM
sed -i 's/^auth.*required.*pam_succeed_if.so.*user != root.*/# &/' /etc/pam.d/lightdm-autologin 2>/dev/null || true

# Configure Openbox autostart
mkdir -p /root/.config/openbox
cat > /root/.config/openbox/autostart << OBEOF
/opt/urrunberri-os/scripts/boot.sh &
OBEOF

cat > /root/.config/openbox/rc.xml << RCEOF
<?xml version="1.0" encoding="UTF-8"?>
<openbox_config xmlns="http://openbox.org/3.4/rc">
  <resistance><strength>10</strength><screen_edge_strength>20</screen_edge_strength></resistance>
  <focus><followMouse>no</followMouse></focus>
  <desktops><number>1</number></desktops>
  <keyboard></keyboard>
  <mouse></mouse>
  <menu><file>menu.xml</file></menu>
</openbox_config>
RCEOF

# Configure GRUB for silent boot
sed -i 's/GRUB_CMDLINE_LINUX_DEFAULT=.*/GRUB_CMDLINE_LINUX_DEFAULT="quiet splash"/' /etc/default/grub
sed -i 's/GRUB_TIMEOUT=.*/GRUB_TIMEOUT=0/' /etc/default/grub
update-grub 2>/dev/null || true

echo "[UrrunBerri OS] Post-installation terminee."
POSTINST

chmod +x "$PROFILE_DIR/urrunberri.postinst"

# ── BUILD ISO ─────────────────────────────────────────────────────────────────
echo "[3/5] Construction de l'ISO (cette etape peut prendre 15-30 minutes)..."
mkdir -p "$OUTPUT_DIR"

cd "$WORK_DIR"
mkdir -p "$WORK_DIR/local-debs"
cd "$WORK_DIR"
build-simple-cdd \
    --dist trixie \
    --profiles urrunberri \
    --auto-profiles urrunberri \
    --profiles-udeb-dist trixie \
    --local-packages "$WORK_DIR/local-debs" \
    --debian-mirror http://deb.debian.org/debian/ \
    --security-mirror http://security.debian.org/debian-security/ \
    2>&1 | tail -30

# ── FIND OUTPUT ──────────────────────────────────────────────────────────────
echo "[4/5] Recherche de l'ISO generee..."
ISO_FILE=$(find "$WORK_DIR" -name "*.iso" -type f 2>/dev/null | head -1)

if [[ -z "$ISO_FILE" ]]; then
    echo "[ERREUR] ISO non trouvee. Verifier les logs ci-dessus."
    exit 1
fi

FINAL_ISO="$WORK_DIR/urrunberri-os-offline.iso"
mv "$ISO_FILE" "$FINAL_ISO"

# ── DONE ──────────────────────────────────────────────────────────────────────
ISO_SIZE=$(du -h "$FINAL_ISO" | cut -f1)
echo "[5/5] Termine."
echo ""
echo "=================================================="
echo "  ISO generee : $FINAL_ISO"
echo "  Taille : $ISO_SIZE"
echo ""
echo "  Graver sur USB :"
echo "  sudo dd if=$FINAL_ISO of=/dev/sdX bs=4M status=progress"
echo ""
echo "  L'ISO va :"
echo "  1. Demander : langue, hostname, IP, mot de passe root"
echo "  2. Installer Debian 13 + tous les paquets UrrunBerri"
echo "  3. Configurer UrrunBerri OS automatiquement"
echo "  4. Redemarrer sur UrrunBerri OS pret a l'emploi"
echo ""
echo "  AUCUNE connexion Internet requise sur la machine cible."
echo "=================================================="
