# Recette du socle V1

Vérifications du 19 novembre 2026, à partir du commit initial b693b369451c3b747c4ff8794fab505b531e416c et des changements de la branche adam. Les données utilisées dans les tests et le benchmark sont construites ou synthétiques. Aucune ressource AWS n'a été créée et aucune capture AWS réelle n'a été évaluée pendant l'implémentation.

## Vérifications exécutées

La suite python -m unittest discover -s tests -v comporte 38 tests et passe. L'environnement vérifié utilise Python 3.12.14, pandas 3.0.1, scikit-learn 1.9.1 et Streamlit 1.67.0 sous Windows 11. Les versions de la résolution sont épinglées dans requirements.lock.txt et pip check ne signale pas de dépendance cassée.

Le parcours Streamlit automatisé ouvre une analyse, filtre le détecteur, affiche la preuve, clôture une alerte avec qualification/commentaire, puis ouvre une nouvelle session et retrouve l'historique. Le mode AWS est testé avec une fixture documentaire ; cette fixture n'est pas une capture réelle.

Le benchmark local python -m smart_ids.benchmark retient les 10 000 lignes construites et produit deux alertes. La mesure de référence obtenue est d'environ 3,36 secondes sur Windows 11, Python 3.12.14, processeur AMD64 Family 25 Model 80. Elle inclut import, indicateurs, règles, sauvegarde et relecture SQLite, mais pas interface ni ML. Ce résultat dépend de la machine et n'est pas une garantie de performance AWS.

Les six empreintes de la baseline correspondent au manifeste. Les fichiers de baseline sont conservés octet pour octet. La politique .gitattributes évite leur conversion automatique de fins de ligne. Le test final réservé n'a pas été chargé ni évalué.

## Traçabilité de la recette

| Critère | Vérification disponible | Statut |
|---|---|---|
| T01 Import texte et gzip | test_aws_flow_logs, test_service | Automatisé sur fixtures |
| T02 Invalides et diagnostics | test_aws_flow_logs, test_service ; bornes de fichiers conservées dans l'adaptateur | Automatisé sur les cas couverts |
| T03 Doublons | Déduplication du lot dans test_aws_flow_logs | Automatisé |
| T04 UTC et sens | test_pipeline, test_anomaly, test_audit | Automatisé |
| T05 Scan à la frontière du seuil | test_service, test_pipeline | Automatisé |
| T06 Volume à la frontière du seuil | test_service, test_pipeline | Automatisé |
| T07 Frontières de fenêtres | test_aws_flow_logs, test_service | Automatisé |
| T08 Historique et réimport | Réouverture avec une nouvelle instance Store, puis nouvelle session Streamlit | Automatisé |
| T09 Qualification sans modifier les preuves | test_service, test_history_dashboard | Automatisé |
| T10 Filtres et exports | test_history_dashboard, test_service | Automatisé sur les parcours couverts |
| T11 Expérience intelligente | Reproductibilité, indépendance des étiquettes de test, séparation, couverture des familles normales | Automatisé sur synthétique |
| T12 Laboratoire AWS | Guide aws_lab_setup.md et scripts lab/ prêts | À exécuter par Adam et Mahmoud |
| T13 Activité légitime volumineuse | Qualification et conservation de la décision sur données construites | Partie locale automatisée ; essai AWS à documenter |
| T14 Performance locale | Benchmark de 10 000 lignes, référence environ 3,36 secondes | Objectif local de 30 secondes atteint sur cette machine |

## Réserve de validation réelle

Le logiciel de F01 à F10 est implémenté dans le périmètre local prévu. F11 et l'interprétation des résultats sur votre laboratoire AWS restent à acquérir après création des ressources et exécution des essais. Le compte à crédits ne peut être validé à distance à partir de sa seule description ; la région, les autorisations et la disponibilité des fonctions doivent être vérifiées dans votre console.

Les tests ne certifient pas toutes les configurations cloud ou tous les fichiers possibles. Les pertes de collecte, REJECT, les intervalles exclus et le changement de distribution entre synthétique et AWS restent des limites explicites. Aucune précision, aucun rappel et aucun F1 réels ne sont annoncés sans vérité terrain indépendante.
