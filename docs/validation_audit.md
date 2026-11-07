# Audit de la baseline — données synthétiques uniquement

Les détecteurs, les règles, le générateur et la logique OU restent inchangés.
Le test du 5 janvier est désormais exploratoire car déjà consulté. Cet audit utilise
uniquement entraînement et validation. Aucun résultat final n'est calculé.

## Cohérence des calculs

Vérifications exécutées : conservation du nombre de flux et des sommes d'octets
par sens ; équivalence exacte entre les règles sur flux et sur indicateurs ;
chaque instance reste dans cinq minutes. Hôte = src_ip en sortie, dst_ip en entrée.
Ports/destinations/max par destination concernent seulement la sortie. Les octets
sont des entiers et les seuils en Mo décimaux (1 Mo = 1 000 000 octets).
Fenêtres UTC fixes [début, début + 5 min[ ; pas de fenêtres glissantes.
Le générateur répartit total_out par division entière : la somme peut être
inférieure à la cible de moins d'un octet par flux sortant. Aucun mélange entrant/sortant observé.
Cette cohérence interne ne valide pas encore les conventions d'un fournisseur cloud.

## Distribution du normal

| split | family | windows | share |
| --- | --- | --- | --- |
| train | backup | 60 | 0.25 |
| train | download | 60 | 0.25 |
| train | interactive | 60 | 0.25 |
| train | web | 60 | 0.25 |
| validation | backup | 40 | 0.333333 |
| validation | download | 40 | 0.333333 |
| validation | interactive | 40 | 0.333333 |

Le remplacement de chaque i divisible par quatre par un suspect supprime **tous
les web normaux de validation**. Ce n'est pas seulement un changement de graine :
le normal passe de quatre familles à trois. Les sauvegardes passent de 25 % à
33,33 % du normal (60 entraînement, 40 validation). Toutes dépassent le seuil
volume de 50 Mo, même si elles sont légitimes. Leur plage théorique reste
60–140 Mo, pas une nouvelle famille de volume absente de l'apprentissage.
Les moyennes/min/médianes/max des six indicateurs par famille sont dans
`reports/audit_normal_distributions.csv`. Extrait des sauvegardes :

| split | family | feature | mean | min | median | max |
| --- | --- | --- | --- | --- | --- | --- |
| train | backup | flow_count | 22.6 | 12 | 21 | 34 |
| train | backup | bytes_out | 1.00612e+08 | 62807256 | 1.03013e+08 | 136684737 |
| train | backup | bytes_in | 243825 | 76468 | 236864 | 494788 |
| validation | backup | flow_count | 22.925 | 13 | 21 | 34 |
| validation | backup | bytes_out | 9.73074e+07 | 61398912 | 9.52568e+07 | 133853472 |
| validation | backup | bytes_in | 256465 | 65433 | 244537 | 482417 |

## Baseline sur validation : 160 fenêtres, 120 normales et 40 suspectes

| detector | windows | normal | suspicious | precision | recall | f1 | false_positive_rate | tn | fp | fn | tp |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rule | 160 | 120 | 40 | 0.2 | 0.25 | 0.222222 | 0.333333 | 80 | 40 | 30 | 10 |
| model | 160 | 120 | 40 | 0.444444 | 0.7 | 0.543689 | 0.291667 | 85 | 35 | 12 | 28 |
| combined | 160 | 120 | 40 | 0.329412 | 0.7 | 0.448 | 0.475 | 63 | 57 | 12 | 28 |

## Erreurs par famille sur validation

FP = normal signalé ; FN = suspect non signalé. FPR indéfini si aucun normal.

| family | detector | windows | normal | suspicious | tn | fp | fn | tp |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| backup | rule | 40 | 40 | 0 | 0 | 40 | 0 | 0 |
| backup | model | 40 | 40 | 0 | 22 | 18 | 0 | 0 |
| backup | combined | 40 | 40 | 0 | 0 | 40 | 0 | 0 |
| download | rule | 40 | 40 | 0 | 40 | 0 | 0 | 0 |
| download | model | 40 | 40 | 0 | 28 | 12 | 0 | 0 |
| download | combined | 40 | 40 | 0 | 28 | 12 | 0 | 0 |
| exfiltration | rule | 10 | 0 | 10 | 0 | 0 | 0 | 10 |
| exfiltration | model | 10 | 0 | 10 | 0 | 0 | 0 | 10 |
| exfiltration | combined | 10 | 0 | 10 | 0 | 0 | 0 | 10 |
| fanout | rule | 10 | 0 | 10 | 0 | 0 | 10 | 0 |
| fanout | model | 10 | 0 | 10 | 0 | 0 | 0 | 10 |
| fanout | combined | 10 | 0 | 10 | 0 | 0 | 0 | 10 |
| interactive | rule | 40 | 40 | 0 | 40 | 0 | 0 | 0 |
| interactive | model | 40 | 40 | 0 | 35 | 5 | 0 | 0 |
| interactive | combined | 40 | 40 | 0 | 35 | 5 | 0 | 0 |
| scan | rule | 10 | 0 | 10 | 0 | 0 | 10 | 0 |
| scan | model | 10 | 0 | 10 | 0 | 0 | 2 | 8 |
| scan | combined | 10 | 0 | 10 | 0 | 0 | 2 | 8 |
| subtle | rule | 10 | 0 | 10 | 0 | 0 | 10 | 0 |
| subtle | model | 10 | 0 | 10 | 0 | 0 | 10 | 0 |
| subtle | combined | 10 | 0 | 10 | 0 | 0 | 10 | 0 |

## Distribution des scores de validation

Score = -score_samples, non probabiliste. Quantiles empiriques interpolés :

| family | count | min | median | max | p05 | p25 | p75 | p95 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| backup | 40 | 0.459652 | 0.506306 | 0.644435 | 0.47172 | 0.487525 | 0.531764 | 0.634327 |
| download | 40 | 0.452511 | 0.490252 | 0.667456 | 0.46522 | 0.479917 | 0.52936 | 0.610429 |
| exfiltration | 10 | 0.547916 | 0.575662 | 0.621971 | 0.549998 | 0.558437 | 0.599105 | 0.614723 |
| fanout | 10 | 0.613074 | 0.628153 | 0.64144 | 0.618212 | 0.626053 | 0.639456 | 0.64077 |
| interactive | 40 | 0.379255 | 0.411226 | 0.619694 | 0.387276 | 0.394845 | 0.431881 | 0.587011 |
| scan | 10 | 0.423993 | 0.519352 | 0.531174 | 0.453606 | 0.516043 | 0.528667 | 0.530539 |
| subtle | 10 | 0.436683 | 0.453001 | 0.475537 | 0.436838 | 0.439682 | 0.461274 | 0.474578 |

Les distributions se recouvrent : une valeur atypique ne révèle pas l'intention.
Les lignes et scores individuels sont dans `reports/audit_validation_windows.csv`.
Au seuil actuel, le modèle signale 18/40 sauvegardes (45 %), 12/40 téléchargements
(30 %) et 5/40 interactions (12,5 %). Il manque 2/10 scans et les 10/10 subtle.
Les subtle ont tous un score inférieur au seuil, malgré leurs étiquettes suspectes.
L'exfiltration à volume élevé n'a pas systématiquement un score supérieur aux
normales : l'amplitude du score n'est ni le volume ni une mesure de gravité.
Isolation Forest isole des configurations rares, pas une intention malveillante.
Les médianes des variables par famille et issue FP/TN/FN/TP sont exportées dans
`reports/audit_validation_error_features.csv`. Les associations ne prouvent pas
qu'une variable cause une erreur ; aucune attribution causale n'a été calculée.

## Choix exact du seuil actuel

Isolation Forest : 200 arbres, max_samples=auto (240 observations disponibles),
contamination=auto, random_state=42, n_jobs=1. Entraînement normal uniquement,
aucune normalisation ni variable d'identité. On utilise score_samples et non
predict : l'offset automatique de contamination n'est pas le seuil d'alerte.
Les candidats sont tous les scores uniques de validation et nextafter(max, +inf)
(pas d'alerte). Pour chacun, prédire score >= seuil. Maximiser dans l'ordre :
F1, puis -FPR, puis seuil. Aucun objectif FPR à 5 % n'était imposé.
Seuil actuel exact : **0.51584453878430836**. Il privilégie le compromis F1 de ce jeu,
pas une contrainte opérationnelle sur les fausses alertes.

## Recherche expérimentale FPR ≤ 5 % sur validation seulement

Avec 120 normales, le budget est **6 faux positifs maximum**. Le septième score
normal le plus élevé est 0.61023558317467763 ; le seuil doit être strictement
supérieur à cette valeur (attention aux égalités). Recherche exhaustive des
160 décisions réalisables, sans réentraînement :

| threshold | windows | normal | suspicious | precision | recall | f1 | false_positive_rate | tn | fp | fn | tp |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.515845 | 160 | 120 | 40 | 0.444444 | 0.7 | 0.543689 | 0.291667 | 85 | 35 | 12 | 28 |
| 0.55 | 160 | 120 | 40 | 0.527778 | 0.475 | 0.5 | 0.141667 | 103 | 17 | 21 | 19 |
| 0.6 | 160 | 120 | 40 | 0.619048 | 0.325 | 0.42623 | 0.0666667 | 112 | 8 | 27 | 13 |
| 0.65 | 160 | 120 | 40 | 0 | 0 | 0 | 0.00833333 | 119 | 1 | 40 | 0 |
| 0.613074 | 160 | 120 | 40 | 0.647059 | 0.275 | 0.385965 | 0.05 | 114 | 6 | 29 | 11 |
| 0.667456 | 160 | 120 | 40 | 0 | 0 | 0 | 0 | 120 | 0 | 40 | 0 |

Meilleur rappel réalisable sous cette contrainte : **27.5%**,
FP=6, TP=11, FN=29, seuil=0.61307448228931638.
La contrainte est réalisable, au minimum en ne signalant rien ; le rappel obtenu
ci-dessus en donne le coût : 72,5 % des suspects restent manqués, contre 30 %
avec le seuil initial. Ce rappel est faible pour un détecteur général ; aucun
minimum de rappel acceptable n'a encore été fixé pour le projet. Aucun de ces
seuils exploratoires n'est appliqué. Avec les règles actuelles conservées, la
combinaison OU ne peut jamais respecter 5 % en faisant varier uniquement le seuil
du modèle : son FPR est au moins celui des règles, soit 40/120 = 33,33 %.
Un FPR empirique ≤ 5 % sur seulement 120 normales n'est pas une garantie statistique
ni une borne en production. Choisir sur validation rend aussi ces résultats optimistes.

## Seuils des règles, logique OU conservée

Grille déclarée : ports [3, 4, 10, 15, 20, 25] ; volume en Mo
[50, 100, 140, 160, 200, 300]. Les 36 résultats sont dans le CSV dédié.
Meilleurs candidats de cette grille sous FPR ≤ 5 % :

| ports | volume_Mo | windows | normal | suspicious | precision | recall | f1 | false_positive_rate | tn | fp | fn | tp |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 4 | 160 | 160 | 120 | 40 | 1 | 0.75 | 0.857143 | 0 | 120 | 0 | 10 | 30 |
| 4 | 140 | 160 | 120 | 40 | 1 | 0.75 | 0.857143 | 0 | 120 | 0 | 10 | 30 |
| 4 | 200 | 160 | 120 | 40 | 1 | 0.65 | 0.787879 | 0 | 120 | 0 | 14 | 26 |
| 4 | 300 | 160 | 120 | 40 | 1 | 0.5 | 0.666667 | 0 | 120 | 0 | 20 | 20 |
| 10 | 160 | 160 | 120 | 40 | 1 | 0.475 | 0.644068 | 0 | 120 | 0 | 21 | 19 |
| 10 | 140 | 160 | 120 | 40 | 1 | 0.475 | 0.644068 | 0 | 120 | 0 | 21 | 19 |
| 15 | 160 | 160 | 120 | 40 | 1 | 0.4 | 0.571429 | 0 | 120 | 0 | 24 | 16 |
| 15 | 140 | 160 | 120 | 40 | 1 | 0.4 | 0.571429 | 0 | 120 | 0 | 24 | 16 |

Les 40 sauvegardes expliquent les FP du volume à 50 Mo. Le scan synthétique
répartit ses ports sur trois pairs : le maximum par destination peut rester sous
20, même avec beaucoup de ports au total. fanout garde trois ports et un petit
volume : les deux règles ne ciblent pas ce comportement. subtle peut rester sous
les deux seuils. Baisser le seuil ports à trois toucherait du normal utilisant
80/443/53. Les seuils ci-dessus sont exploratoires ; ni règle ni combinaison OU
n'est changée. Un meilleur chiffre sur ce générateur ne prouve pas une meilleure détection réelle.
Le couple 4 ports / 140 Mo sépare artificiellement bien les plages connues du
générateur : 30 suspects détectés sur 40, les dix fanout restant manqués. Le
seuil 140 Mo est juste au-dessus de la borne supérieure programmée des sauvegardes.
Cette facilité illustre un biais du générateur et non un seuil cloud recommandé.

## Réservation finale et limites communes

La baseline est archivée dans `baseline/`, avec code, dépendances, résultats et
SHA-256 dans le manifeste. L'ancien test reste une référence descriptive connue.
Nouvelle période réservée : 7 janvier, 160 fenêtres, graine de base 20261104,
flux RNG indépendant 20261106, identifiants préfixés final_reserved. Le fichier
`data/synthetic_final_reserved.csv` n'est ni agrégé, ni scoré, ni évalué. Son
manifeste contient son empreinte. Ne l'ouvrir qu'après gel explicite des variables,
hyperparamètres, seuils et protocole ; aucun outil existant ne le charge automatiquement.
Un tirage neuf du même générateur n'est pas indépendant de ses hypothèses : il
reste un contrôle synthétique interne, pas une validation externe.

Limites partagées : familles codées par règles simples, proportion de suspects
fixe, normales simplifiées, absence de bruit/pertes/doublons, un scénario et un
hôte par fenêtre, pas de concurrence ni de scans lents entre fenêtres. Les cinq IP
sont réutilisées ; pas de profil par hôte. Le temps n'influence pas les comportements.
Les identifiants de variantes distincts ne garantissent pas des distributions
vraiment nouvelles : plusieurs familles partagent exactement les mêmes plages.
Les directions sont imposées, pas inférées, et l'observation est complète par
construction. Réutiliser ce générateur pour choisir puis juger favorise ses
particularités. Aucun résultat ici ne mesure la performance réelle.
