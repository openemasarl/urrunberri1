# Journal des modifications

Toutes les modifications notables de UrrunBerri OS sont consignees dans ce fichier.

## [1.1.1] — 2026-09-10

### Corrige

- Ajout explicite du paquet wpasupplicant a la liste d'installation. Ce paquet
  n'etait qu'une recommandation du gestionnaire de reseau, et non une
  dependance stricte. Lors d'une installation depuis l'image ISO, les
  recommandations n'etant pas retenues, il etait absent : les interfaces sans
  fil restaient alors indisponibles et aucune recherche de reseau n'aboutissait.
  L'installation par script n'etait pas concernee, ce qui rendait le defaut
  difficile a identifier.

## [1.1.0] — 2026-09-10

Premiere version integrant le module de configuration reseau.
Validee sur installation neuve, machine ZOTAC (Debian 13 Trixie).

### Ajoute

- Page de configuration reseau accessible depuis l'interface de connexion
  (bouton Reseau), disponible en francais, anglais, espagnol et basque.
- Configuration Ethernet depuis l'interface : bascule entre DHCP et adressage
  statique, avec saisie de l'adresse, du masque, de la passerelle et du DNS.
- Module Wi-Fi complet : recherche des reseaux disponibles, connexion avec
  saisie du mot de passe, et deconnexion.
- Detection automatique des interfaces reseau a l'execution. Les cles USB sans
  fil sont retenues en priorite lorsqu'elles sont presentes, la carte interne
  servant de solution de repli.
- Installation du gestionnaire de reseau et du service de resolution de noms,
  absents des versions precedentes.
- Configuration des serveurs de noms lors de l'installation. Une installation
  neuve demarrait auparavant sans aucune resolution DNS.
- Fichier VERSION permettant d'identifier la version installee.

### Corrige

- La recherche de reseaux Wi-Fi ne renvoyait jamais aucun resultat. La fonction
  reposait sur un utilitaire absent de Debian 13, et l'erreur etait interceptee
  sans etre signalee, ce qui produisait une liste vide indiscernable d'une
  recherche legitimement infructueuse.
- Les noms d'interfaces reseau etaient inscrits en dur dans le code, ce qui
  limitait le fonctionnement a un materiel precis. Toutes les occurrences ont
  ete supprimees, cote filaire comme sans fil.
- Une configuration Ethernet statique s'affichait a tort comme DHCP dans
  l'interface. Le libelle n'etait mis a jour qu'au changement de langue.
- Le domaine de recherche DNS etait inscrit en dur dans la configuration
  generee.
- Absence d'instruction de retour apres la lecture de l'etat reseau.

### Connu

- L'export des informations Ceph n'est pas concerne par cette version.
- La persistance du pilote sans fil apres redemarrage prolonge reste a
  observer sur la duree.

## [1.0] — 2026

Version initiale.

- Connexions RDP, RDP Gateway, VNC, SSH et Web depuis une interface unique.
- Demarrage automatique sur l'interface de connexion.
- Interface disponible en quatre langues.
- Sauvegarde des connexions favorites.
- Detection automatique de la resolution d'ecran.
- Arret et redemarrage depuis l'interface.
