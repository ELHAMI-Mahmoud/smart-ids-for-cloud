# Analyse du dépôt et plan adaptation

7 novembre 2026 - Référence examinée : b693b369451c3b747c4ff8794fab505b531e416c.

## Conclusion

Le travail du binôme est compatible avec un Smart IDS étudiant fondé sur des journaux de flux. Il faut le prolonger. La base contient déjà des détections explicables, une expérimentation ML, une interface et un adaptateur AWS. Elle ne constitue pas encore un IDS connecté en continu à AWS ni un modèle intelligent validé sur trafic cloud réel.

Pour terminer rapidement, le cahier des charges retient deux règles déjà développées et conserve l'expérience intelligente séparée. L'ajout SSH proposé initialement est reporté, puisqu'il demanderait des journaux d'authentification et un adaptateur supplémentaire. La collecte AWS manuelle reste acceptable pour cette V1 d'analyse différée.

## Ce qui existe dans le code

| Élément | Fichiers examinés | Constat |
|---|---|---|
| Générateur simple et règles | smart_ids/pipeline.py | Scan sortant par paire source/destination ; volume sortant par source ; fenêtres UTC de cinq minutes |
| Expérience ML | smart_ids/anomaly.py | Génération synthétique, agrégation, Isolation Forest, seuil de validation et métriques comparatives |
| Import AWS | smart_ids/aws_flow_logs.py | Texte/gzip, CIDR et ENI explicites, contrôles de qualité, exclusions, dédoublonnage par lot |
| Interface | app.py et smart_ids/aws_dashboard.py | Modes synthétique/AWS, diagnostics, indicateurs et exports CSV |
| Évaluation critique | docs/validation_audit.md | Erreurs par famille, faux positifs et étude des seuils |
| Conservation de référence | baseline/ et manifest.json | Versions et résultats historiques avec empreintes |
| Tests | tests/ | Cas de règles, agrégation, import et interface ; exécution partielle pendant cette revue |

La saisie des seuils est disponible dans la démonstration simple. La vue AWS utilise encore les seuils fixes 20 ports et 50 Mo. Le modèle ML n'est ni entraîné ni appliqué à l'import AWS. Les fichiers AWS téléversés et les alertes ne sont pas persistés par l'interface ; les exports CLI ne constituent pas un historique d'alertes avec statut.

Le code ne dispose pas encore d'une base SQLite, d'un cycle de qualification des alertes, d'un historique d'analyses ni d'une collecte automatique. Cette dernière n'est pas requise par le socle proposé.

## Limites à traiter dans le dossier et la démonstration

### Les alertes réseau ont un périmètre précis

Les règles actuelles filtrent le trafic sortant. Elles n'identifient donc pas un scan entrant. L'adaptateur écarte REJECT de l'analyse et conserve ces lignes au diagnostic ; un scan entièrement bloqué n'est pas détecté. Les échanges dont les deux hôtes sont dans les CIDR déclarés sont également exclus. Il faut montrer un scan depuis la VM observée vers une cible contrôlée extérieure à son /32 logique.

Le /32 déclare la ressource surveillée. Il ne faut pas déclarer tout le VPC par commodité si cela transforme l'essai en trafic interne exclu. Cette limite doit apparaître dans le guide du laboratoire et dans les résultats.

### Les faux positifs sont un sujet prioritaire

Le rapport docs/validation_audit.md indique sur validation 120 fenêtres normales et 40 suspectes. Les règles produisent 40 faux positifs sur 120 fenêtres normales, soit 33,33 %. Le modèle seul produit 29,17 % de faux positifs avec 70 % de rappel. La combinaison OU produit 47,5 % de faux positifs. Ces chiffres sont rapportés par le dépôt, pas recalculés pendant cette revue.

Les sauvegardes légitimes de 60 à 140 Mo dépassent la règle de volume à 50 Mo. Ajouter un OU entre règles et modèle ne peut pas supprimer les faux positifs des règles. Il faut conserver les décisions séparées, analyser leurs erreurs et régler les seuils sur développement/validation. Une comparaison OU peut rester dans l'expérience, sans être présentée comme une amélioration acquise.

Le générateur remplace par un suspect chaque observation dont l'indice est divisible par quatre. Cette logique élimine les exemples web normaux de validation et du test exploratoire. Corriger la sélection pour couvrir les familles normales dans chaque période est utile avant un nouveau protocole, tout en conservant la baseline historique.

### Le passage du synthétique à AWS doit être évalué séparément

Un enregistrement AWS agrège des paquets sur un intervalle ; il n'est pas nécessairement équivalent à une ligne générée. La distribution des variables et leur couverture changent. Réutiliser directement le modèle synthétique sur AWS ne constituerait pas une validation de son efficacité.

La V1 garde le mode ML synthétique explicite. L'extension E01 devra produire une base normale propre au laboratoire, figer les mêmes variables, réserver une période indépendante et mesurer les résultats de cette nouvelle expérience.

### Les fenêtres et la qualité de collecte peuvent masquer un essai

Par défaut, les intervalles AWS qui traversent deux fenêtres sont exclus. L'option end conserve les octets en les plaçant entièrement dans la fenêtre de fin, avec une approximation temporelle. Les deux comportements sont documentés et doivent rester visibles. Un essai sans alerte n'est interprétable qu'après examen des exclusions, des périodes et des données réellement reçues.

### La reproductibilité doit fonctionner sur les systèmes du binôme

Les six empreintes de baseline/manifest.json correspondent aux objets Git du commit examiné. Dans la copie Windows utilisée pour la revue, les fins de ligne ont été converties en CRLF par Git ; les empreintes des fichiers de travail diffèrent alors. Il ne s'agit pas d'une corruption constatée des objets Git.

Ajouter une politique .gitattributes imposant LF pour les fichiers hachés, puis vérifier une copie fraîche, permettrait de stabiliser les contrôles. Ne pas modifier les empreintes simplement pour masquer cet effet. Les dépendances exactes et les commandes d'installation doivent aussi être vérifiées sur le système réellement utilisé.

Le jeu final réservé mentionné dans la documentation n'est pas présent dans la copie publique examinée ; les chemins data/*.csv sont ignorés par Git. Il faut l'archiver séparément avec son manifeste et définir son accès, sans le consulter pendant les réglages.

## Plan adaptation par fonction

| Fonction | État observé | Action minimale |
|---|---|---|
| F01 Configuration | Partiel | Partager une configuration versionnée entre CLI, interface et résultats ; rendre les seuils AWS configurables |
| F02 Import et diagnostics | Présent, vérifié partiellement | Conserver ; ajouter à la recette les fichiers vides et limites de taille |
| F03 Normalisation et indicateurs | Présent | Conserver les conventions ; isoler l'agrégation pour ne pas importer scikit-learn dans le seul mode AWS |
| F04 Scan sortant | Présent | Conserver ; relier les événements justificatifs à l'alerte persistée |
| F05 Volume sortant | Présent | Conserver ; documenter et tester les sauvegardes légitimes |
| F06 Interface | Partiel | Ajouter filtres, détail, choix d'analyse et limites visibles |
| F07 Module intelligent | Présent sur synthétique | Conserver l'historique ; rééquilibrer les familles normales et figer un nouveau protocole avant le final |
| F08 Historique | Absent de l'interface | Ajouter SQLite et réouverture d'une analyse identique |
| F09 Qualification | Absent | Ajouter statut, qualification, commentaire et dates |
| F10 Exports | Partiel | Ajouter métadonnées/version/configuration à l'interface et sécuriser les champs CSV libres |
| F11 Preuve AWS réelle | Non démontrée par les fichiers examinés | Exécuter un petit laboratoire et archiver les preuves anonymisées |

## Organisation cible du code

Conserver smart_ids/pipeline.py pour les règles, smart_ids/aws_flow_logs.py pour l'import et les composants d'interface actuels. Extraire aggregate vers un module indépendant tel que features.py, utilisé à la fois par la vue AWS et anomaly.py. Cette séparation évite que la simple consultation AWS charge la dépendance ML.

Ajouter config.py pour valider les paramètres, storage.py pour SQLite et service.py pour coordonner l'import, la détection et l'enregistrement. Le nom exact de ces fichiers est une proposition ; leur responsabilité et leurs contrats de données comptent davantage.

Ne pas réécrire les modules qui fonctionnent pour imposer une nouvelle architecture. Ajouter d'abord les tests d'intégration sur les comportements ciblés, puis déplacer les fonctions en conservant leur résultat.

## Ordre des tickets

| Ordre | Ticket | Preuve de fin |
|---|---|---|
| 1 | Écrire les modèles Analyse, Configuration, Alerte et Qualification | Schéma partagé et un exemple JSON convenu |
| 2 | Ajouter configuration AWS et tests de frontières | Même configuration visible dans CLI, interface et export |
| 3 | Ajouter SQLite et historique | Une analyse et ses alertes restent visibles après redémarrage |
| 4 | Ajouter qualification et dédoublonnage de réimport | Statut conservé et aucun double historique pour le même lot/configuration |
| 5 | Raccorder filtres, preuves et métadonnées | Une alerte peut être expliquée et exportée |
| 6 | Réaliser le laboratoire AWS | Les règles sont rejouées sur une capture du laboratoire, avec limites explicites |
| 7 | Stabiliser le protocole ML et la portabilité | Baseline intacte, familles normales couvertes, final réservé identifié |
| 8 | Exécuter la recette et finaliser le dossier | Tableau T01 à T14 rempli, installation reproductible |

Les tickets 2 et 3 peuvent être réalisés en parallèle après le ticket 1. Le laboratoire peut être préparé pendant ce temps. L'ajout d'une nouvelle source SSH ou d'un jeu CIC public attend la fin du socle.

## Vérifications effectuées pendant la revue

- Lecture des sources du moteur, de l'import AWS, des deux vues, de l'expérience ML et des documents d'audit.
- Analyse syntaxique Python de tous les modules smart_ids, des tests et de app.py, sans erreur de syntaxe.
- Exécution des cinq tests existants de tests/test_pipeline.py : tous passent dans le runtime de revue.
- Contrôles supplémentaires par assertions sur données construites : validation AWS, doublons, compteurs absents, REJECT, scan à 20 ports et politiques temporelles exclude/end : conformes sur ces cas.
- Vérification des six empreintes de la baseline sur les objets Git : conformes. Écart CRLF de la copie Windows identifié.
- Aucune ressource cloud créée, aucune capture AWS réelle analysée, aucun jeu final réservé chargé ou évalué.
- Suite complète ML/Streamlit non exécutée : scikit-learn et Streamlit ne sont pas installés dans le runtime de revue. Les métriques historiques n'ont pas été reproduites. La revue n'est donc pas une certification de l'ensemble des tests.
- Aucun fichier du projet examiné n'a été modifié.

## Sources du dépôt

- Version complète : https://github.com/ELHAMI-Mahmoud/smart-ids-for-cloud/tree/b693b369451c3b747c4ff8794fab505b531e416c
- Règles : https://github.com/ELHAMI-Mahmoud/smart-ids-for-cloud/blob/b693b369451c3b747c4ff8794fab505b531e416c/smart_ids/pipeline.py
- Import : https://github.com/ELHAMI-Mahmoud/smart-ids-for-cloud/blob/b693b369451c3b747c4ff8794fab505b531e416c/smart_ids/aws_flow_logs.py
- Expérience ML : https://github.com/ELHAMI-Mahmoud/smart-ids-for-cloud/blob/b693b369451c3b747c4ff8794fab505b531e416c/smart_ids/anomaly.py
- Audit : https://github.com/ELHAMI-Mahmoud/smart-ids-for-cloud/blob/b693b369451c3b747c4ff8794fab505b531e416c/docs/validation_audit.md
