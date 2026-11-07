# CIC-IDS2017 — vérification préalable et protocole proposé

État au 4 novembre 2026 : **préparation documentaire uniquement**. Aucun adaptateur
CIC ni apprentissage sur CIC n’est encore implémenté ou exécuté. Cette étape
respecte la demande de vérifier les fichiers et leurs colonnes avant d’implémenter.
Ni l’importateur AWS, ni la baseline synthétique, ni son jeu final ne sont modifiés.

## Source et conditions vérifiées

La page UNB/CIC annonce PCAP, profils, flux étiquetés
`GeneratedLabelledFlows.zip` et `MachineLearningCSV.zip`, et demande de citer
l’article associé. Elle décrit une capture de laboratoire du 3 au 7 juillet 2017,
avec un lundi bénin et des attaques les jours suivants.
[Page officielle](https://www.unb.ca/cic/datasets/ids-2017.html).

La FAQ CIC autorise utilisation, redistribution, republication et miroirs avec
citation du dataset et de l’article. Ce constat n’attribue pas une licence SPDX
(CC-BY, MIT, etc.) absente des pages consultées. Lire aussi les notices effectivement
livrées avec l’archive lorsque celle-ci est disponible. Aucun formulaire n’a été
soumis avec des données personnelles ou inventées.
[FAQ officielle, questions de licence](https://www.unb.ca/cic/datasets/).

Citation à joindre aux rapports : Iman Sharafaldin, Arash Habibi Lashkari,
Ali A. Ghorbani, « Toward Generating a New Intrusion Detection Dataset and
Intrusion Traffic Characterization », ICISSP, 2018. Origine à afficher :
**CIC-IDS2017 — UNB/CIC, capture publique de laboratoire, version originale**.
Ce n’est ni une capture AWS ni une validation de déploiement en production.

## Disponibilité réellement constatée

| Élément | Statut constaté |
|---|---|
| Page descriptive UNB | Accessible |
| PCAP / GeneratedLabelledFlows.zip / MachineLearningCSV.zip | Annoncés sur la page, téléchargement non confirmé |
| Bouton Download officiel | Ouvre le formulaire CIC ; message « Server error. Please try again later. » |
| Ancien répertoire HTTP 205.174.165.80 | Redirection 301 vers cicresearch.ca ; aucun inventaire obtenu |
| Répertoire Dataset HTTPS | Redirection vers la liste générale UNB, pas un listing d’archives |
| CSV officiels présents dans ce projet | Aucun trouvé dans data/ |
| En-têtes/lignes d’une archive officielle effectivement inspectés | **Aucun : vérification bloquée** |

[Portail relié par UNB](https://cicresearch.ca/CICDataset/CIC-IDS-2017/).
Ne pas présenter les tailles/noms des membres d’archive ni leurs colonnes comme
vérifiés. Aucun miroir Kaggle/Hugging Face ne remplace silencieusement la source
choisie. Une version corrigée constituerait une expérience différente avec sa
propre provenance. Le formulaire requiert des coordonnées : l’utilisateur peut
le compléter lui-même, puis indiquer le chemin local de l’archive/des CSV.

## Schémas : ce qui est établi et ce qui reste à vérifier

Le dépôt CICFlowMeter relié depuis UNB montre des flux bidirectionnels et des
champs d’identité, ports, timestamp et compteurs directionnels. Mais son code
contient des variantes de noms (Source IP / Src IP, Destination IP / Dst IP,
Packet / Packets), et une ancienne liste d’en-têtes est commentée. Le code actuel
**n’est pas une preuve du schéma exact de l’archive 2017**.
[FlowGenerator](https://github.com/ahlashkari/CICFlowMeter/blob/master/src/main/java/cic/cs/unb/ca/jnetpcap/FlowGenerator.java),
[FlowFeature](https://github.com/ahlashkari/CICFlowMeter/blob/master/src/main/java/cic/cs/unb/ca/jnetpcap/FlowFeature.java).

La variante ML est à vérifier en priorité pour l’absence éventuelle d’IP et de
timestamp. Si ces informations sont absentes, elle sera refusée pour notre
expérience par hôte/fenêtre, même si elle permet une classification par ligne.
Les récupérer depuis Flow ID ou le nom du fichier serait une reconstruction non
validée et ne sera pas utilisée. Les flux étiquetés complets sont la variante
candidate ; aucun mappage n’est encore déclaré validé.

### Matrice de faisabilité conditionnelle

| Indicateur souhaité | Colonnes nécessaires à constater dans les fichiers |
|---|---|
| Hôte et fenêtre de cinq minutes | IP source/destination et Timestamp lisible ; périmètre d’hôtes défini |
| Nombre de flux | Une ligne = un biflux distinct, après dédoublonnage ; temps et IP |
| Ports distants distincts | Source Port, Destination Port, orientation et protocole |
| Destinations distinctes | Adresses des deux extrémités et orientation |
| Maximum de ports par destination | Même information, regroupée par hôte/pair |
| Volume sortant/entrant | Totaux de longueur forward/backward, sémantique/version à vérifier |
| Détection des intervalles traversant une fenêtre | Timestamp + Flow Duration avec unité confirmée |
| Évaluation des fenêtres | Label de chaque ligne, sans valeurs absentes ni conflit inexpliqué |

Sans IP : pas d’hôte ni de destinations distinctes. Sans timestamp : pas de
fenêtres. Sans compteur directionnel : pas de volume de ce sens. Sans durée/unité
confirmée : pas de contrôle fiable des traversées ; expérience temporelle suspendue.
Aucune ENI, IP, réseau CIDR, date, durée ou quantité d’octets ne sera ajoutée pour
combler une absence. Les débits Flow Bytes/s ne seront pas multipliés par une durée
pour fabriquer des totaux manquants.

Le code public BasicFlow additionne des longueurs de payload et exprime les durées
via une base microseconde. Cela avertit que les totaux de longueur ne sont pas
nécessairement les octets IP comptés par AWS ; la version productrice de l’archive
reste à identifier avant de fixer les unités. Ne pas sommer deux fois les champs
Subflow avec les totaux.
[Implémentation du producteur](https://github.com/ahlashkari/CICFlowMeter/blob/master/src/main/java/cic/cs/unb/ca/jnetpcap/BasicFlow.java).

## Vérification requise avant de commencer l’adaptateur

Sur les fichiers effectivement obtenus :

1. Relever URL d’acquisition, date, nom, taille, SHA-256 et notices de l’archive.
   Lister les membres sans extraction aveugle ; distinguer PCAP, flux complets et ML.
2. Pour chaque CSV, relever l’en-tête **brut**, espaces/BOM, encodage, délimiteur,
   doublons de colonnes et champs absents. Conserver cette preuve dans un manifeste.
3. Examiner des exemples de dates/durées/compteurs pour fixer explicitement format,
   unité et précision. Un nom de jour dans le fichier ne remplace pas une date.
   Ne pas convertir un horaire naïf en UTC sans source sur le fuseau : conserver
   le temps de capture naïf, identifié comme tel, si le fuseau n’est pas établi.
4. Auditer lignes malformées, NaN/Infinity, volumes/durées négatifs, plages des
   ports, incohérences de paquets, doublons et labels conflictuels. Ne pas compléter
   ou supprimer silencieusement. Vérifier les bornes calendaires de chaque fichier.
5. Valider les unités et l’orientation retenues, puis seulement coder les alias
   strictement constatés. Tout schéma inattendu doit produire un diagnostic.

## Adaptateur distinct à construire après cette vérification

Module envisagé : `smart_ids/cic_ids2017.py`, sans dépendance à l’importateur AWS.
Il conservera chaque biflux comme observation unique, avec provenance du fichier
et numéro de ligne, temps brut et temps interprété, durée et compteurs d’origine.
Ne pas découper un biflux en deux faux flux, ce qui doublerait flow_count.

Périmètre : liste explicite d’IP d’hôtes à étudier, provenant de l’inventaire
publié et des adresses réellement observées. Pas de CIDR AWS ni d’ENI fictive.
La topologie UNB sert à valider une configuration, pas à remplir les fichiers.
Si un périmètre de frontière est retenu, exclure et compter séparément les flux
avec deux extrémités dedans ou deux dehors. Les échanges internes nécessiteraient
une convention dédiée pour éviter de compter deux hôtes comme deux flux globaux.

Pour un biflux avec hôte étudié en source : forward = sortant, backward = entrant.
Avec hôte en destination : inverser les deux compteurs. Le sens forward n’est pas
une synonymie d’egress. Les destinations/ports distants de réponse peuvent être
éphémères : distinguer les ports distants observés des ports de services initiés.
La définition finale doit être figée et les différences avec le modèle synthétique
expliquées ; aucun transfert automatique de son seuil n’est prévu.

Fenêtres fixes de cinq minutes dans la base temporelle réellement disponible.
Politique principale prévue : exclure et compter les biflux dont l’intervalle
[start, start+duration] traverse une frontière. Ne pas distribuer les octets au
prorata sans temps des paquets. Cela peut biaiser l’évaluation vers les flux courts,
notamment pour certaines attaques : rapporter l’exclusion par label/jour.
La précision de Timestamp peut ajouter de l’incertitude aux frontières ; la
documenter avant de prétendre connaître exactement l’instant de fin.

### Étiquetage explicite des fenêtres mixtes

Unité = hôte × fenêtre, sur les biflux retenus :

- Normal si **toutes** les étiquettes présentes sont BENIGN.
- Suspect si **au moins une** ligne porte une étiquette d’attaque reconnue.
- Mixte si des BENIGN et attaques coexistent ; la cible binaire reste suspect.
- Non évaluable s’il existe un label absent/non reconnu ou un conflit de labels
  pour la même observation : exclure de l’apprentissage et des métriques, avec compte.

Conserver nombre de biflux, nombre et proportion de biflux d’attaque, liste des
familles et indicateur mixte pour l’évaluation, jamais comme variables du modèle.
Une fenêtre suspecte ne signifie pas que tous ses octets sont malveillants.
La liste des labels reconnus doit venir de l’inventaire effectif, sans réétiqueter
une ligne selon le seul calendrier des attaques. Ne pas propager une attaque aux
fenêtres où aucun flux étiqueté correspondant n’est observé.

## Expérience séparée proposée, à figer avant consultation du test

Répartition chronologique **par journées complètes de capture**, sous réserve de
validation des timestamps et des membres de l’archive :

| Ensemble | Périodes prévues | Usage |
|---|---|---|
| Entraînement | Lundi 3 juillet 2017 | Seulement fenêtres entièrement BENIGN |
| Validation | Mardi 4 et mercredi 5 juillet | Choix du seuil, analyse des erreurs |
| Test réservé CIC | Jeudi 6 et vendredi 7 juillet | Une évaluation après gel du protocole |

Tous les CSV matin/après-midi d’une journée appartiennent au même ensemble.
Aucun mélange entre variantes ML et flux complets ; aucune répartition aléatoire
par ligne/fenêtre. Les labels et scores du test ne doivent pas servir à ajuster
les variables ou le seuil. L’inspection structurelle préalable du schéma sera
distinguée de toute inspection des distributions/étiquettes du test.

Définir une session par biflux canonique (paire IP/port non orientée + protocole),
regroupé temporellement tant que les intervalles se chevauchent ou sont séparés
de moins de 120 secondes (convention expérimentale annoncée, pas un champ fourni).
Traiter les journées complètes ensemble avant cette vérification : supprimer des
ensembles concernés toute session franchissant une coupure d’ensemble. Le même
5-tuple réutilisé plusieurs jours plus tard n’est pas automatiquement une session.
Pour les observations exactement dupliquées, dédoublonner globalement avant
séparation ; si labels conflictuels, rendre la fenêtre non évaluable. Vérifier
également les copies d’un même fichier avec SHA-256. Contrôler que les intervalles
et fenêtres de chaque ensemble restent disjoints après ces opérations.

Variables : liste numérique explicite des indicateurs réellement disponibles.
Exclure IP, dates, Flow ID, nom de fichier, jour, label et familles. Entraîner un
nouvel Isolation Forest, graine 42 et hyperparamètres fixes ; ne pas réutiliser le
modèle synthétique. Seuil proposé : meilleur rappel sur validation sous FPR ≤ 5 %,
avec départage par FPR minimal puis seuil maximal. Rapporter aussi le seuil sans
alerte et le résultat non contraint, sans masquer une chute de rappel. Si validation
ne contient pas les deux classes, ne pas sélectionner le seuil.

Comparer règles de référence, modèle CIC seul et règle OU modèle, sans changer
cette combinaison pour améliorer les chiffres. Les seuils en octets des règles
seront identifiés comme exploratoires si les compteurs CIC ont une autre sémantique.
Rapporter précision, rappel, F1, matrices de confusion, FPR, nombres de fenêtres,
fenêtres mixtes, exclusions et résultats par jour/famille. Un score n’est pas une
probabilité d’attaque. Aucun chiffre CIC n’est actuellement disponible.

Origine obligatoire dans chaque rapport, manifeste et vue Streamlit : dataset,
variante, fichiers/empreintes, base temporelle, périmètre, politique de fenêtres,
règle de label mixte et répartition des sessions/périodes. Le futur mode CIC sera
séparé d’AWS et du synthétique et n’affichera pas d’évaluation avant fichiers valides.
Sorties prévues dans `reports/cic_ids2017/`, sources dans `data/cic_ids2017/`.

## Limites de portée

Capture de laboratoire ancienne, attaques programmées, familles liées au jour,
plusieurs machines/protocoles partagés entre journées : une séparation temporelle
limite les fuites directes mais ne crée pas une indépendance totale des contextes.
Un test de familles différentes mesure un décalage de distribution, pas seulement
un changement de période. Les labels publiés et l’extracteur peuvent avoir des
imperfections ; ils ne sont pas une vérité terrain vérifiée par nous. L’agrégation
et l’exclusion de flux longs peuvent amplifier ces biais. Ces résultats publics
ne seront ni une performance cloud AWS ni une preuve de performance en production.

**Prochaine entrée indispensable : archive/CSV officiel accessible et son chemin
local.** Aucun adaptateur fondé sur un schéma supposé n’est livré à ce stade.
