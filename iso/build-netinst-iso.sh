#!/bin/bash
# =============================================================================
#  UrrunBerri OS — Construction de l'ISO d'installation
#  Openema SARL — Mathieu Cadi
#
#  Ce script prend l'ISO Debian 13 netinst standard et injecte la
#  configuration UrrunBerri (preseed.cfg). L'ISO resultante installe
#  Debian avec un minimum de questions, puis installe automatiquement
#  UrrunBerri OS au premier demarrage.
#
#  Prerequis : xorriso, isolinux, curl, wget, acces root
#  Usage : bash build-netinst-iso.sh
# =============================================================================

set -e

DEBIAN_ISO_URL="https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/debian-13.5.0-amd64-netinst.iso"
DEBIAN_ISO="/root/debian-netinst.iso"
PRESEED_URL="https://raw.githubusercontent.com/openemasarl/urrunberri1/iso/iso/preseed.cfg"
OUTPUT_ISO="/root/urrunberri-os.iso"
WORK_DIR="/root/iso-work"

echo "=================================================="
echo "  UrrunBerri OS — Construction de l'ISO"
echo "  Openema SARL"
echo "=================================================="
echo ""

[[ $EUID -ne 0 ]] && echo "[ERREUR] Lancez en root." && exit 1

# ── 1. INSTALLATION DES DEPENDANCES ──────────────────────────────────────────
echo "[1/6] Installation des dependances..."
apt-get update -qq
apt-get install -y xorriso isolinux wget curl

# ── 2. TELECHARGEMENT DE L'ISO DEBIAN ────────────────────────────────────────
if [[ ! -f "$DEBIAN_ISO" ]]; then
    echo "[2/6] Telechargement de l'ISO Debian 13 netinst (755 Mo)..."
    wget -O "$DEBIAN_ISO" "$DEBIAN_ISO_URL"
else
    echo "[2/6] ISO Debian deja presente, skip."
fi

# ── 3. EXTRACTION DE L'ISO ───────────────────────────────────────────────────
echo "[3/6] Extraction de l'ISO..."
rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR"
xorriso -osirrox on -indev "$DEBIAN_ISO" -extract / "$WORK_DIR"
chmod -R u+w "$WORK_DIR"

# ── 4. INJECTION DU PRESEED ──────────────────────────────────────────────────
echo "[4/6] Injection du preseed UrrunBerri..."
curl -fsSL -o "$WORK_DIR/preseed.cfg" "$PRESEED_URL"

# Modifier GRUB (UEFI)
sed -i '0,/---/{s|---|file=/cdrom/preseed.cfg ---|1}' "$WORK_DIR/boot/grub/grub.cfg"

# Modifier isolinux (BIOS)
sed -i '0,/append/{s|append |append preseed/file=/cdrom/preseed.cfg |1}' "$WORK_DIR/isolinux/txt.cfg"
sed -i 's/timeout 0/timeout 50/' "$WORK_DIR/isolinux/isolinux.cfg"

# ── 5. RECONSTRUCTION DE L'ISO ───────────────────────────────────────────────
echo "[5/6] Reconstruction de l'ISO..."
cd "$WORK_DIR"
find . -type f ! -name "md5sum.txt" -exec md5sum {} \; > md5sum.txt 2>/dev/null

xorriso -as mkisofs \
    -r -V "UrrunBerriOS" \
    -o "$OUTPUT_ISO" \
    -J -joliet-long \
    -b isolinux/isolinux.bin \
    -c isolinux/boot.cat \
    -no-emul-boot \
    -boot-load-size 4 \
    -boot-info-table \
    -isohybrid-mbr /usr/lib/ISOLINUX/isohdpfx.bin \
    -eltorito-alt-boot \
    -e boot/grub/efi.img \
    -no-emul-boot \
    -isohybrid-gpt-basdat \
    "$WORK_DIR"

cd /

# ── 6. NETTOYAGE ─────────────────────────────────────────────────────────────
echo "[6/6] Nettoyage..."
rm -rf "$WORK_DIR"

ISO_SIZE=$(du -h "$OUTPUT_ISO" | cut -f1)
echo ""
echo "=================================================="
echo "  ISO generee : $OUTPUT_ISO"
echo "  Taille : $ISO_SIZE"
echo ""
echo "  Copier sur cle USB Ventoy :"
echo "  mount /dev/sdX1 /mnt"
echo "  cp $OUTPUT_ISO /mnt/"
echo "  sync && umount /mnt"
echo ""
echo "  L'ISO va :"
echo "  1. Demander : langue, hostname, domaine, IP,"
echo "     masque, passerelle, DNS, mot de passe root"
echo "  2. Installer Debian 13 automatiquement"
echo "  3. Au premier demarrage : installer UrrunBerri OS"
echo "  4. Redemarrer sur UrrunBerri OS pret a l'emploi"
echo "=================================================="
