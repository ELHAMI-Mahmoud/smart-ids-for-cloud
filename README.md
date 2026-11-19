# Smart IDS pour AWS

Prototype étudiant d'Adam et Mahmoud, construit à partir du dépôt initial de Mahmoud. Le socle analyse des VPC Flow Logs téléchargés manuellement : contrôles de qualité, règles explicables, historique SQLite, preuves et qualification des alertes. Un mode distinct conserve l'expérience Isolation Forest sur données synthétiques.

**Aucun compte AWS n'est connecté au logiciel.** Les essais réels sont à réaliser dans votre laboratoire ; le logiciel n'annonce aucune précision/rappel sur des fichiers AWS non étiquetés. Le score d'anomalie synthétique n'est pas une probabilité d'attaque.

## Démarrage

Python 3.12 ou 3.13. Les versions de la branche ont été vérifiées sous Python 3.12 Windows ; le guide conserve aussi les commandes Linux utilisées par le binôme.

```bash
git clone --branch adam https://github.com/ELHAMI-Mahmoud/smart-ids-for-cloud.git
cd smart-ids-for-cloud
python -m venv .venv
```

Sous Windows PowerShell :

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Sous Linux :

```bash
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python -m streamlit run app.py
```

Ouvrir http://127.0.0.1:8501. La configuration lie le serveur à localhost. Les commandes ci-dessous utilisent python : le remplacer par le Python de votre venv ou activer celui-ci. Les dépendances souples sont dans requirements.txt ; la résolution testée est dans requirements.lock.txt.

## Trois parcours

- **Démonstration synthétique** : 945 flux factices, deux règles et seuils interactifs. Le bouton de conservation permet de retrouver et qualifier ces alertes dans l'historique Synthétique. L'expérience ML équilibrée v2 est affichée séparément.
- **Import AWS manuel** : déclarer le /32 surveillé et une seule ENI, choisir seuils et politique temporelle, puis importer les .log/.txt/.gz. Les diagnostics, flux retenus, indicateurs, alertes et preuves sont conservés localement.
- **Historique des analyses** : choisir la provenance, rouvrir une analyse, filtrer par période/hôte/détecteur/statut, consulter les preuves et enregistrer une qualification. Un lot strictement identique avec la même configuration n'est pas dupliqué.

Les limites d'import sont de 20 Mio par fichier compressé ou décompressé et 50 Mio décompressés par lot. Les flux internes, hors périmètre, REJECT, les protocoles non TCP/UDP et les données inexploitables sont au diagnostic. Les règles analysent les flux sortants ACCEPT. Un scan entrant ou entièrement bloqué n'est pas couvert par ce socle.

Les seuils initiaux sont 20 ports distincts par paire source/destination et 50 000 000 octets sortants par source sur cinq minutes UTC. Ce sont des valeurs de démonstration configurables, pas des normes de sécurité. Les sauvegardes légitimes peuvent déclencher la règle de volume.

## CLI et historique

```bash
python -m smart_ids demo
python -m smart_ids history
python -m smart_ids analyze data/aws/mon-export.log.gz --lab-cidr 10.20.1.10/32 --interface-id eni-REELLE --port-threshold 20 --byte-threshold 50000000 --window-policy exclude --output exports/mon-analyse
python -m smart_ids export IDENTIFIANT_ANALYSE --output exports/mon-analyse
python -m smart_ids qualify IDENTIFIANT_ALERTE --status "Clôturé" --qualification "Activité légitime" --comment "Sauvegarde autorisée"
```

Les identifiants sont affichés par la CLI et l'interface. La base est var/smart_ids.sqlite3. SMART_IDS_DB ou l'option globale --db permettent de choisir un autre chemin, par exemple python -m smart_ids --db var/essai.sqlite3 demo. Le fichier conserve des données réelles si vous les importez : il est exclu de Git, comme les exports, clés et secrets. Arrêter l'application avant de supprimer une base de démonstration dont vous n'avez plus besoin.

Les exports contiennent alerts.csv, diagnostics.csv, windows.csv, flows.csv et metadata.json. La configuration, les empreintes des sources, la provenance et la version du moteur permettent de reproduire l'analyse. Les champs CSV libres sont protégés contre l'interprétation en formule par un tableur. L'ancienne CLI smart_ids.aws_flow_logs reste disponible pour l'import exploratoire sans historique ; la CLI ci-dessus est celle du socle persistant.

## AWS avec votre compte à crédits

Suivre le [guide de création du laboratoire](docs/aws_lab_setup.md). Il décrit la nouvelle expérience AWS à projets, les vérifications de formule/région, deux petites VM, les groupes de sécurité, S3 et le Flow Log de l'ENI observée. Aucun NAT Gateway, RDS ou SageMaker n'est requis. Le récepteur et les trois essais bornés sont dans lab/ ; ils n'utilisent que Python standard et des données factices.

La livraison Flow Logs est différée. Si des intervalles traversent une frontière de fenêtre, exclude les écarte et end affecte tous les octets à la fin, avec avertissement. Examiner la couverture avant d'interpréter une absence d'alerte.

## Expérience intelligente

```bash
python -m smart_ids.anomaly
```

Le [protocole balanced v2](docs/evaluation_protocol_v2.md) couvre désormais les quatre familles normales dans chaque période. Entraînement sur normal uniquement, seuil choisi sur validation, test affiché exploratoire. Les CSV et métadonnées sont écrits dans reports/. La baseline et les anciens résultats restent historiques. Aucun résultat du jeu final réservé n'est calculé par la démonstration ou les tests.

Les règles, le modèle et leur combinaison OU sont comparés sans promesse d'amélioration : plus de rappel peut s'accompagner de plus de faux positifs. Le modèle synthétique n'est pas appliqué aux fichiers AWS. Le passage à un apprentissage AWS est une extension distincte.

## Vérifier et mesurer

```bash
python -m unittest discover -s tests -v
python -m smart_ids.benchmark
```

Les tests couvrent les règles, l'import, les contrats, les preuves, le réimport après redémarrage, la qualification, les exports et les parcours Streamlit. Le benchmark traite 10 000 lignes AWS entièrement construites et inclut la sauvegarde/relecture SQLite, hors interface et ML. Il ne mesure aucune performance sur une capture cloud réelle.

## Documents

- [Cahier des charges et répartition Adam et Mahmoud](docs/specification.md)
- [Architecture du socle implémenté](docs/architecture_v1.md)
- [Diagrammes de conception](docs/diagrammes_conception.md)
- [Contrôles et recette](docs/recette_v1.md)
- [Guide détaillé des conventions d'import](docs/aws_manual_import.md)
- [Analyse initiale et plan d'adaptation](docs/analyse_et_plan_adaptation.md)
- [README du prototype initial et métriques historiques](docs/prototype_initial.md)
- [Audit historique de validation](docs/validation_audit.md)
- [Préparation de l'expérience CIC facultative](docs/cic_ids2017_preflight.md)

Le prototype reste local, mono-utilisateur et d'analyse différée. Collecte automatique, SSH, Azure, scans entrants, réaction automatique et déploiement public attendent une extension du périmètre.
