#!/bin/bash
clear
echo "================================================"
echo "  UrrunBerri OS - Installation automatique"
echo "  Openema SARL"
echo "================================================"
echo ""
echo "--- Mot de passe root ---"
while true; do
    read -s -p "Mot de passe root : " ROOTPASS
    echo ""
    read -s -p "Confirmez le mot de passe root : " ROOTPASS2
    echo ""
    if [ "$ROOTPASS" = "$ROOTPASS2" ]; then
        if [ -z "$ROOTPASS" ]; then
            echo "Mot de passe vide. Recommencez."
        else
            echo "Mot de passe root OK."
            break
        fi
    else
        echo "Mots de passe differents. Recommencez."
    fi
done
echo ""
echo "--- Compte utilisateur ---"
while true; do
    read -p "Nom d utilisateur : " USERNAME
    if echo "$USERNAME" | grep -qE "^[a-z][a-z0-9]*$"; then
        break
    else
        echo "Nom invalide. Lettres minuscules et chiffres uniquement."
    fi
done
while true; do
    read -s -p "Mot de passe pour $USERNAME : " USERPASS
    echo ""
    read -s -p "Confirmez le mot de passe : " USERPASS2
    echo ""
    if [ "$USERPASS" = "$USERPASS2" ]; then
        if [ -z "$USERPASS" ]; then
            echo "Mot de passe vide. Recommencez."
        else
            echo "Compte utilisateur OK."
            break
        fi
    else
        echo "Mots de passe differents. Recommencez."
    fi
done
echo ""
echo "--- Configuration reseau ---"
read -p "Utiliser le DHCP automatique ? (o/n) : " DHCP_CHOICE
echo ""
NETWORK_CONFIG=""
if [ "$DHCP_CHOICE" = "n" ] || [ "$DHCP_CHOICE" = "N" ]; then
    read -p "Adresse IP (ex: 192.168.1.100) : " STATIC_IP
    read -p "Masque (ex: 255.255.255.0) : " STATIC_MASK
    read -p "Passerelle (ex: 192.168.1.1) : " STATIC_GW
    read -p "DNS (ex: 8.8.8.8) : " STATIC_DNS
    echo ""
    echo "IP        : $STATIC_IP"
    echo "Masque    : $STATIC_MASK"
    echo "Passerelle: $STATIC_GW"
    echo "DNS       : $STATIC_DNS"
    NETWORK_CONFIG="static"
fi
echo ""
echo "================================================"
echo "  Recapitulatif"
echo "================================================"
echo "  Utilisateur : $USERNAME"
if [ "$NETWORK_CONFIG" = "static" ]; then
    echo "  Reseau : IP statique $STATIC_IP"
else
    echo "  Reseau : DHCP automatique"
fi
echo ""
read -p "Demarrer l installation ? (o/n) : " CONFIRM
if [ "$CONFIRM" != "o" ] && [ "$CONFIRM" != "O" ]; then
    echo "Installation annulee."
    exit 1
fi
echo ""
PRESEED="/cdrom/preseed.cfg"
sed -i "s/ROOTPASS/$ROOTPASS/g" $PRESEED
sed -i "s/USERNAME/$USERNAME/g" $PRESEED
sed -i "s/USERPASS/$USERPASS/g" $PRESEED
if [ "$NETWORK_CONFIG" = "static" ]; then
    sed -i "s|d-i netcfg/choose_interface select auto|d-i netcfg/choose_interface select auto\nd-i netcfg/disable_dhcp boolean true\nd-i netcfg/get_ipaddress string $STATIC_IP\nd-i netcfg/get_netmask string $STATIC_MASK\nd-i netcfg/get_gateway string $STATIC_GW\nd-i netcfg/get_nameservers string $STATIC_DNS\nd-i netcfg/confirm_static boolean true|" $PRESEED
fi
echo "Lancement de l installation..."
sleep 2
exec /usr/bin/debian-installer
