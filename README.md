# Smart IDS — laboratoire local

## Expérience publique CIC-IDS2017 — vérification préalable

Le [dossier de vérification CIC](docs/cic_ids2017_preflight.md) documente la source
officielle, les conditions de citation, les champs requis, le mappage conditionnel
des biflux et le protocole entraînement/validation/test proposé.

Le portail officiel affiche actuellement une erreur et aucun CSV officiel n’est
présent localement : **les colonnes de l’archive n’ont pas encore été vérifiées**.
L’adaptateur et le mode Streamlit CIC restent à implémenter après cette vérification,
conformément à l’ordre demandé. Aucun résultat CIC n’est annoncé. La baseline et
le jeu final synthétiques sont conservés.

## Import manuel AWS

Le mode **Import AWS manuel** de Streamlit lit les VPC Flow Logs exportés en
texte ou gzip. Définir explicitement les CIDR du laboratoire et une seule ENI.
Les diagnostics distinguent doublons, lignes invalides et exclusions ; aucune
étiquette ou valeur manquante n’est inventée. L’import reste séparé des
expériences synthétiques et ne charge pas le jeu final réservé.

Le [guide AWS](docs/aws_manual_import.md) décrit le schéma, les conventions de
direction, les limites temporelles, les permissions, les coûts et la collecte
manuelle vers S3. Aucune ressource AWS n’est créée par le prototype.

```bash
python -m smart_ids.aws_flow_logs data/aws/mon-export.log.gz \
  --lab-cidr 10.0.1.25/32 --interface-id eni-0123456789abcdef0
```

Adapter le chemin et le périmètre aux ressources réelles. Par défaut, les
enregistrements traversant plusieurs fenêtres sont exclus plutôt que répartis
artificiellement. Les règles restent exploratoires ; aucune performance réelle
n’a encore été mesurée. Isolation Forest reste limité à l’expérience synthétique.

## Audit de la baseline et statut des ensembles

L’analyse des erreurs est dans [docs/validation_audit.md](docs/validation_audit.md).
La reproduire avec `python -m smart_ids.audit` : elle utilise uniquement
l’entraînement et la validation, exporte les diagnostics et ne modifie aucun seuil.
Les résultats/code de référence sont conservés dans `baseline/` avec empreintes.
Le test déjà consulté est désormais exploratoire, pas un ensemble final intact.
Un nouveau tirage est réservé dans `data/synthetic_final_reserved.csv`, période
du 7 janvier, avec manifeste et empreinte ; il n’a été ni scoré ni évalué.
Ne pas le consulter avant le gel du protocole. Aucun chargement automatique par
le tableau de bord ou les commandes d’apprentissage ne l’utilise.

Sur validation, la contrainte expérimentale FPR ≤ 5 % limite le modèle à 27,5 %
de rappel, contre 70 % à son seuil initial (FPR 29,17 %). Les règles actuelles
ont 33,33 % de FPR, donc la combinaison OU ne peut pas atteindre 5 % en changeant
seulement le seuil du modèle. Les seuils exploratoires du rapport ne sont pas appliqués.

Prototype étudiant Python, pandas, scikit-learn et Streamlit. **Les expériences
d’apprentissage et leurs performances sont exclusivement synthétiques.** L’import
manuel AWS affiche séparément les journaux fournis par l’utilisateur, sans mesure
de performance réelle. Aucun compte AWS/Azure n’est connecté au prototype.

## Installation et commandes

Environnement vérifié : Kali Linux, Python 3.13. Les dépendances restent dans le venv.

```bash
cd /home/mahmoud/projets/smart-ids
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock.txt
python -m smart_ids.anomaly
python -m unittest discover -s tests -v
streamlit run app.py
```

`python -m smart_ids.anomaly` génère les données, entraîne Isolation Forest,
choisit son seuil sur validation puis évalue le test. Graine fixe : 42, exécution
mono-processus, 200 arbres, max_samples='auto', contamination='auto'. Aucune recherche
sur les hyperparamètres. Les versions exactes sont dans `requirements.lock.txt`.
Le modèle reste en mémoire ; relancer cette commande reproduit l’apprentissage.

Sorties remplacées à chaque exécution :

- `data/synthetic_ml_flows.csv` : flux et vérité terrain synthétiques.
- `reports/synthetic_ml_windows.csv` : indicateurs, scores, décisions, métadonnées.
- `reports/synthetic_ml_metrics.csv` : résultats validation/test des trois détecteurs.
- `reports/synthetic_ml_metadata.json` : graine, variables, seuil et convention du score.

Ouvrir <http://127.0.0.1:8501>. `Ctrl+C` arrête le serveur, `deactivate` quitte le
venv. Sans activation, utiliser `.venv/bin/python` ou `.venv/bin/streamlit`.
Le tableau de bord reproduit l’expérience en mémoire et la met en cache. Il ne lit
pas les rapports CSV. Il sépare règles, modèle et toutes les fenêtres, avec leurs
indicateurs et scores. Le sélecteur permet d’examiner chaque période.

La démonstration initiale reste disponible : `python -m smart_ids.pipeline`
produit 945 flux et 2 alertes. La première partie de l’interface utilise toujours
ce jeu et ses seuils interactifs ; ces contrôles ne changent pas l’expérience ML.

## Unité d’observation et variables

Une observation = un **hôte interne × fenêtre fixe UTC de cinq minutes**,
intervalle [début, début + 5 min[. Seules les fenêtres contenant des flux existent.
Aucune fenêtre glissante, duplication de fenêtre ou attribution par IP au modèle.

| Variable | Calcul |
|---|---|
| flow_count | Nombre de flux entrants et sortants observés |
| ports_out | Nombre de ports destination distincts des flux sortants |
| destinations_out | Nombre d’IP destination distinctes des flux sortants |
| max_ports_per_destination | Maximum des ports distincts par destination sortante |
| bytes_out | Somme des octets sortants |
| bytes_in | Somme des octets entrants, si ce sens est disponible |

Pour un flux sortant l’hôte est `src_ip`, pour un entrant c’est `dst_ip`.
Cette convention suppose une direction relative au périmètre interne déjà connue.
Les ports entrants sont des ports destination locaux et ne sont pas mélangés aux
ports distants sortants. Aucune durée ni métrique de paquets n’est inventée.

Si le jeu ne comporte aucun flux entrant, `bytes_in` est omis, plutôt que de
prétendre mesurer ce volume. Dans le jeu synthétique bidirectionnel, une fenêtre
sans flux d’un sens a un volume nul pour ce sens. Sur de vrais journaux il faudra
valider la couverture de collecte ; absence de ligne ne garantit pas absence de
trafic. Les volumes manquants/négatifs et directions inconnues sont refusés.

Le modèle utilise exclusivement la liste explicite des variables numériques
ci-dessus, sans mise à l’échelle apprise. `label`, `scenario`, `instance_id`,
`split`, `synthetic`, les dates et les IP sont exclus. Les étiquettes servent à
vérifier le normal d’entraînement, sélectionner le seuil sur validation et évaluer.

## Données et protocole sans consultation du test

| Ensemble | Période UTC | Fenêtres | Normal / suspect |
|---|---|---:|---:|
| Entraînement | 1 janvier 2026, 00:00–20:00 | 240 | 240 / 0 |
| Validation | 3 janvier 2026, 00:00–13:20 | 160 | 120 / 40 |
| Test | 5 janvier 2026, 00:00–13:20 | 160 | 120 / 40 |

Les fins sont exclusives. Les périodes sont séparées de plus d’une journée.
Chaque instance de scénario occupe une seule fenêtre, avec un identifiant unique.
Chaque période possède ses variantes de scénarios, ses tirages indépendants et
ses instances générées une seule fois. Aucun suréchantillonnage ni copie d’une
instance entre ensembles. Les familles de comportements restent apparentées :
ce protocole mesure des variantes synthétiques, pas la généralisation à des
familles d’attaques entièrement inconnues. Les contrôles refusent les périodes
chevauchantes, les identifiants/variantes partagés et le suspect en entraînement.

Activités normales : web, interaction, téléchargement entrant et sauvegardes
sortantes légitimes de 60–140 Mo. Suspects : scan de ports, dispersion vers de
nombreuses destinations, gros transfert sortant et variante plus discrète de
10–40 Mo avec davantage de ports. Tous utilisent des adresses de documentation.
Les occurrences normales et suspectes ont des tirages de paramètres indépendants.
La proportion synthétique de suspects est fixée à 25 % en validation/test ; elle
ne représente pas une fréquence d’attaque réelle.

Isolation Forest est ajusté **uniquement sur les 240 fenêtres normales
d’entraînement**. Le score est `-model.score_samples(X)` : une valeur plus élevée
indique une fenêtre plus atypique. **Ce n’est pas une probabilité d’attaque.**
Le seuil est choisi parmi les scores uniques de validation et un seuil sans
alerte : F1 maximal, puis taux de faux positifs minimal, puis seuil le plus haut.
Une alerte correspond à `score >= seuil`. Les hyperparamètres et cette procédure
sont fixes ; le test n’entre ni dans l’ajustement ni dans le choix du seuil.
Les métriques de validation sont des résultats de sélection, pas une estimation
indépendante. Aucune modification des paramètres d’après les résultats du test.

## Comparaison mesurée sur données synthétiques

Les règles existantes sont conservées : au moins 20 ports distincts par paire
source/destination OU au moins 50 000 000 octets sortants par source, dans cinq
minutes. Une fenêtre hôte est positive si au moins une règle la signale.
Le modèle seul utilise son seuil de validation. La combinaison est **règle OU
modèle**, sans nouveau seuil et sans modification des règles pour améliorer le test.

Résultats test, graine 42, seuil de validation **0,51584454** ; chaque ligne porte
sur **160 fenêtres**, dont 120 normales et 40 suspectes :

| Détecteur | Précision | Rappel | F1 | Taux de faux positifs | TN | FP | FN | TP |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Règles | 0,2000 | 0,2500 | 0,2222 | 0,3333 | 80 | 40 | 30 | 10 |
| Isolation Forest | 0,3714 | 0,6500 | 0,4727 | 0,3667 | 76 | 44 | 14 | 26 |
| Règles OU modèle | 0,2826 | 0,6500 | 0,3939 | 0,5500 | 54 | 66 | 14 | 26 |

Matrice de confusion : lignes = vérité [normal, suspect], colonnes = prédiction
[normal, suspect], donc `[[TN, FP], [FN, TP]]`. Taux de faux positifs = FP/(TN+FP),
précision = TP/(TP+FP), rappel = TP/(TP+FN). Un dénominateur nul de précision/rappel
vaut zéro ; un FPR sans négatifs est indéfini. Les rapports incluent aussi validation.

Le modèle améliore ici le rappel mais produit de nombreux faux positifs. La
combinaison OU augmente les faux positifs sans gagner en rappel sur ce test.
Les sauvegardes légitimes dépassent volontairement le seuil de la règle de volume.
Ces résultats révèlent les limites du prototype ; ils ne mesurent **aucune
performance réelle**. Le petit générateur, ses distributions simples, une seule
graine et les familles partagées limitent fortement toute généralisation.

## Structure et vérifications

`smart_ids/pipeline.py` conserve le prototype et les règles. `smart_ids/anomaly.py`
contient le générateur enrichi, l’agrégation, les contrôles de séparation,
l’apprentissage et l’évaluation. `app.py` expose les deux expériences.

Les tests vérifient les anciens comportements, l’agrégation par sens, les calculs
de métriques, la combinaison OU, la reproductibilité, les fuites temporelles et
de scénarios, l’exclusion des étiquettes et l’absence d’influence du test sur le
seuil. Les tests Streamlit vérifient l’exécution et les contrôles de l’interface.

L’import manuel AWS est disponible ; l’automatisation AWS et l’intégration Azure
restent à faire. Ne pas versionner de secrets ni de journaux réels sensibles.
