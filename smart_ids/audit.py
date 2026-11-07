"""Audit reproductible de la validation ; ne score jamais le test ni le final."""
import hashlib
import json
import shutil

import numpy as np
import pandas as pd

from smart_ids.anomaly import (BASE_FEATURES, evaluation_windows, fit_detector,
                               generate_dataset, metrics)
from smart_ids.pipeline import ROOT, detect


def table(frame):
    frame = frame.copy().map(lambda x: f'{x:.6g}' if isinstance(x, float) else str(x))
    return '| ' + ' | '.join(frame.columns) + ' |\n| ' + ' | '.join(['---'] * len(frame.columns)) + ' |\n' + '\n'.join('| ' + ' | '.join(row) + ' |' for row in frame.values.tolist())


def preserve_baseline():
    destination = ROOT / 'baseline'
    manifest = destination / 'manifest.json'
    if manifest.exists():
        saved = json.loads(manifest.read_text())
        for name, digest in saved.items():
            if hashlib.sha256((destination / name).read_bytes()).hexdigest() != digest:
                raise ValueError(f'Baseline altérée : {name}')
        return
    sources = ['smart_ids/anomaly.py', 'smart_ids/pipeline.py', 'requirements.lock.txt',
               'reports/synthetic_ml_windows.csv', 'reports/synthetic_ml_metrics.csv',
               'reports/synthetic_ml_metadata.json']
    destination.mkdir(exist_ok=True)
    hashes = {}
    for source in sources:
        path = ROOT / source
        name = path.name
        if (destination / name).exists():
            raise ValueError('Snapshot partiel existant : vérifier avant de remplacer.')
        shutil.copyfile(path, destination / name)
        hashes[name] = hashlib.sha256((destination / name).read_bytes()).hexdigest()
    manifest.write_text(json.dumps(hashes, indent=2) + '\n')


def reserve_final():
    """Réservation uniquement : aucune agrégation, aucun score, aucune métrique."""
    manifest_path = ROOT / 'data/final_reserved_manifest.json'
    path = ROOT / 'data/synthetic_final_reserved.csv'
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if hashlib.sha256(path.read_bytes()).hexdigest() != manifest['sha256']:
            raise ValueError('Ensemble final altéré.')
        return
    if path.exists():
        raise ValueError('Final existant sans manifeste : ne pas écraser.')
    final = generate_dataset(seed=20261104)
    final = final.loc[final.split.eq('test')].copy()
    final['timestamp'] += pd.Timedelta(days=2)
    final['split'] = 'final_reserved'
    for column in ['instance_id', 'scenario']:
        final[column] = final[column].str.replace('test:', 'final_reserved:', regex=False)
    final.to_csv(path, index=False)
    manifest = dict(status='reserved_unscored', seed=20261104, rng_stream=20261106,
                    start='2026-01-07T00:00:00Z', end_exclusive='2026-01-07T13:20:00Z',
                    planned_windows=160, generator='baseline/anomaly.py:generate_dataset, test branch',
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    policy='Ne pas lire, scorer ou utiliser pour sélectionner les paramètres. Défiger une seule fois après gel du protocole.')
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')


def audit():
    preserve_baseline()
    reserve_final()
    flows = generate_dataset()
    flows = flows.loc[flows.split.isin(['train', 'validation'])].copy()
    windows = evaluation_windows(flows)
    features = BASE_FEATURES + ['bytes_in']
    train = windows[windows.split.eq('train')]
    val = windows[windows.split.eq('validation')].copy()
    model, threshold = fit_detector(train, val, features)
    val['score'] = -model.score_samples(val[features])
    val['family'] = val.scenario.str.split(':').str[-1]
    val['rule'] = (val.max_ports_per_destination >= 20) | (val.bytes_out >= 50_000_000)
    val['model'] = val.score >= threshold
    val['combined'] = val.rule | val.model
    # Recalcul indépendant à partir des flux, comparé aux indicateurs agrégés.
    raw = flows[flows.split.eq('validation')]
    events = detect(raw)
    rule_keys = set(zip(events.window, events.src_ip))
    assert val.rule.tolist() == [(w, h) in rule_keys for w, h in zip(val.window, val.host)]
    assert windows.flow_count.sum() == len(flows)
    assert windows.bytes_out.sum() == flows.loc[flows.direction.eq('outbound'), 'bytes'].sum()
    assert windows.bytes_in.sum() == flows.loc[flows.direction.eq('inbound'), 'bytes'].sum()
    assert (flows.groupby('instance_id').timestamp.max() - flows.groupby('instance_id').timestamp.min()).max() < pd.Timedelta(minutes=5)

    normal = windows[windows.label.eq(0)].copy()
    normal['family'] = normal.scenario.str.split(':').str[-1]
    composition = normal.groupby(['split', 'family']).size().rename('windows').reset_index()
    composition['share'] = composition.windows / composition.groupby('split').windows.transform('sum')
    distributions = []
    for (split, family), group in normal.groupby(['split', 'family']):
        for feature in features:
            distributions.append(dict(split=split, family=family, feature=feature,
                                      mean=group[feature].mean(), min=group[feature].min(),
                                      median=group[feature].median(), max=group[feature].max()))
    distribution = pd.DataFrame(distributions)
    errors = []
    for family, group in val.groupby('family'):
        for detector in ['rule', 'model', 'combined']:
            errors.append(dict(family=family, detector=detector,
                               **metrics(group.label, group[detector])))
    errors = pd.DataFrame(errors)
    scores = val.groupby('family').score.agg(['count', 'min', 'median', 'max'])
    quantiles = val.groupby('family').score.quantile([.05, .25, .75, .95]).unstack()
    quantiles.columns = ['p05', 'p25', 'p75', 'p95']
    scores = scores.join(quantiles).reset_index()
    error_features = val.assign(outcome=np.where(val.label.eq(0),
                                np.where(val.model, 'FP', 'TN'),
                                np.where(val.model, 'TP', 'FN'))).groupby(
                                    ['family', 'outcome'])[features].median().reset_index()

    # Exhaustif : toutes les décisions réalisables avec score >= seuil.
    candidates = np.append(np.unique(val.score), np.nextafter(val.score.max(), np.inf))
    sweep = pd.DataFrame([dict(threshold=float(t), **metrics(val.label, val.score >= t)) for t in candidates])
    feasible = sweep[sweep.false_positive_rate <= .05]
    best = feasible.sort_values(['recall', 'false_positive_rate', 'threshold'], ascending=[False, True, False]).iloc[0]
    selected = [threshold, .55, .60, .65, float(best.threshold), float(candidates[-1])]
    comparisons = pd.DataFrame([dict(threshold=t, **metrics(val.label, val.score >= t)) for t in dict.fromkeys(selected)])
    normal_scores = val.loc[val.label.eq(0), 'score'].sort_values(ascending=False).reset_index(drop=True)
    rules = []
    for ports in [3, 4, 10, 15, 20, 25]:
        for volume in [50_000_000, 100_000_000, 140_000_000, 160_000_000, 200_000_000, 300_000_000]:
            predictions = (val.max_ports_per_destination >= ports) | (val.bytes_out >= volume)
            rules.append(dict(ports=ports, volume_Mo=volume / 1_000_000,
                              **metrics(val.label, predictions)))
    rules = pd.DataFrame(rules)
    best_rules = rules[rules.false_positive_rate <= .05].sort_values(['recall', 'false_positive_rate', 'ports', 'volume_Mo'], ascending=[False, True, False, False]).head(8)
    summary = pd.DataFrame([dict(detector=n, **metrics(val.label, val[n])) for n in ['rule', 'model', 'combined']])
    out = ROOT / 'reports'
    outputs = dict(validation_errors=errors, validation_score_distribution=scores,
                   validation_model_thresholds=sweep, validation_rules_thresholds=rules,
                   normal_distributions=distribution, validation_windows=val,
                   normal_composition=composition, validation_error_features=error_features)
    for name, frame in outputs.items():
        frame.to_csv(out / f'audit_{name}.csv', index=False)
    report = f'''# Audit de la baseline — données synthétiques uniquement

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

{table(composition)}

Le remplacement de chaque i divisible par quatre par un suspect supprime **tous
les web normaux de validation**. Ce n'est pas seulement un changement de graine :
le normal passe de quatre familles à trois. Les sauvegardes passent de 25 % à
33,33 % du normal (60 entraînement, 40 validation). Toutes dépassent le seuil
volume de 50 Mo, même si elles sont légitimes. Leur plage théorique reste
60–140 Mo, pas une nouvelle famille de volume absente de l'apprentissage.
Les moyennes/min/médianes/max des six indicateurs par famille sont dans
`reports/audit_normal_distributions.csv`. Extrait des sauvegardes :

{table(distribution[(distribution.family == 'backup') & distribution.feature.isin(['bytes_out', 'bytes_in', 'flow_count'])])}

## Baseline sur validation : 160 fenêtres, 120 normales et 40 suspectes

{table(summary)}

## Erreurs par famille sur validation

FP = normal signalé ; FN = suspect non signalé. FPR indéfini si aucun normal.

{table(errors[['family', 'detector', 'windows', 'normal', 'suspicious', 'tn', 'fp', 'fn', 'tp']])}

## Distribution des scores de validation

Score = -score_samples, non probabiliste. Quantiles empiriques interpolés :

{table(scores)}

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
Seuil actuel exact : **{threshold:.17g}**. Il privilégie le compromis F1 de ce jeu,
pas une contrainte opérationnelle sur les fausses alertes.

## Recherche expérimentale FPR ≤ 5 % sur validation seulement

Avec 120 normales, le budget est **6 faux positifs maximum**. Le septième score
normal le plus élevé est {normal_scores.iloc[6]:.17g} ; le seuil doit être strictement
supérieur à cette valeur (attention aux égalités). Recherche exhaustive des
{len(sweep)} décisions réalisables, sans réentraînement :

{table(comparisons)}

Meilleur rappel réalisable sous cette contrainte : **{best.recall:.1%}**,
FP={int(best.fp)}, TP={int(best.tp)}, FN={int(best.fn)}, seuil={best.threshold:.17g}.
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

{table(best_rules)}

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
'''
    (ROOT / 'docs/validation_audit.md').write_text(report, encoding='utf-8')
    print(table(comparisons))
    print(table(best_rules))
    print('Audit écrit dans docs/validation_audit.md ; final réservé, non évalué.')


if __name__ == '__main__':
    audit()
