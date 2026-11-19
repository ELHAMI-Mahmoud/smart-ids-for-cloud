# Protocole expérimental balanced v2

L'expérience exécutée par smart_ids.anomaly et l'interface utilise désormais quatre familles normales dans chaque période : web, sauvegarde, interaction et téléchargement entrant. La sélection des cas normaux se fait indépendamment du placement des suspects. L'entraînement conserve 60 fenêtres de chaque famille ; validation et test exploratoire en contiennent 30 chacune. Les suspects restent les quatre familles précédentes, avec 40 fenêtres par période d'évaluation.

L'unité d'observation reste un hôte interne et une fenêtre UTC fixe de cinq minutes. L'entraînement comporte 240 fenêtres normales, la validation 160 fenêtres dont 120 normales et 40 suspectes, et le test exploratoire 160 fenêtres de même composition. Les dates restent disjointes et les instances/variantes ne traversent pas les périodes.

Le modèle utilise uniquement les six indicateurs numériques : flow_count, ports_out, destinations_out, max_ports_per_destination, bytes_out et bytes_in. Les étiquettes, IP, dates et identifiants ne sont pas des variables explicatives. Entraînement normal uniquement ; 200 arbres, graine 42, n_jobs=1, max_samples et contamination auto. Le score est -score_samples, pas une probabilité d'attaque.

Le seuil maximise F1 sur validation ; égalité départagée par FPR minimal, puis seuil maximal. Le test exploratoire n'entre ni dans l'apprentissage ni dans ce choix. Comparaisons : règles fixes 20 ports/50 Mo, modèle seul et règle OU modèle. Le OU ne peut supprimer les faux positifs de ses composants. Aucun objectif de supériorité ML n'est annoncé.

Le générateur reste petit et artificiel. Même avec des fenêtres et des tirages disjoints, les familles sont apparentées : les scores ne mesurent pas une généralisation à des familles inconnues ou au trafic AWS. Le passage à de vraies fenêtres AWS requerra un apprentissage, une sélection et un test propres à ce domaine.

La baseline originale demeure inchangée dans baseline/. Le document validation_audit.md décrit l'ancien générateur ; smart_ids.audit utilise explicitement balanced=False pour reproduire cet audit. Les métriques v2 doivent porter leur nom de protocole et leurs versions de dépendances. Elles ne remplacent pas rétroactivement les métriques historiques.

Le fichier data/synthetic_final_reserved.csv et son manifeste, s'ils existent dans la copie de travail privée du binôme, ne sont ni chargés ni évalués par les commandes de démonstration ou les tests. La branche ne crée pas une nouvelle évaluation finale. Avant de défiger un final, Adam et Mahmoud doivent archiver le protocole, la version du code, les paramètres, le générateur et le manifeste d'un jeu correspondant à ce protocole. Un final préparé avec l'ancien générateur ne devient pas automatiquement un final v2.

La commande python -m smart_ids.anomaly écrit les fenêtres, métriques et métadonnées synthétiques sous reports/. Les résultats v2 seront produits par cette commande ou par l'interface, sans reprise de chiffres historiques dans le tableau courant.
