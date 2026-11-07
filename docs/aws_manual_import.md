# AWS VPC Flow Logs — import manuel

Cette intégration lit des fichiers locaux ; aucun SDK, appel AWS, secret ou
ressource cloud n’est requis pour l’import. La provenance est déclarée par
l’utilisateur, pas authentifiée. Les exemples des tests sont documentaires,
**pas des captures réelles**. Aucun résultat de performance réelle n’est annoncé.
La baseline dans `baseline/` et le jeu final réservé restent inchangés et ne
participent pas à l’import.

## Format pris en charge et correspondance

Entrées : texte UTF-8 à champs séparés par espaces, `.log`, `.txt`, `.log.gz`.
AWS publie notamment des fichiers texte compressés gzip sur S3. JSON CloudWatch,
CSV, Parquet et Transit Gateway Logs ne sont pas pris en charge par cet adaptateur.
Le nom d’un fichier et sa date S3 ne servent pas d’horodatage des flux.
[Organisation des fichiers S3](https://docs.aws.amazon.com/vpc/latest/userguide/flow-logs-s3-path.html).

Sans en-tête, seul l’ordre standard v2 suivant est admis :

```text
version account-id interface-id srcaddr dstaddr srcport dstport protocol packets bytes start end action log-status
```

Un format personnalisé doit avoir un en-tête nommé, contenir ces 14 champs, sans
nom dupliqué. L’ordre peut varier et des colonnes supplémentaires sont acceptées.
Un format custom sans en-tête n’est pas deviné.

| Champ AWS | Champ local / usage |
|---|---|
| version | Contrôle du format |
| account-id | account_id, provenance, conservé même si unknown |
| interface-id | interface_id, filtre obligatoire d’une ENI |
| srcaddr / dstaddr | src_ip / dst_ip, IP v4 ou v6 |
| srcport / dstport | src_port / dst_port, entiers 0–65535 |
| protocol | TCP pour 6, UDP pour 17 ; autres exclus de l’analyse |
| packets | packets, compteur entier de l’enregistrement |
| bytes | bytes, compteur entier en octets |
| start / end | start_time / end_time, secondes Unix converties en UTC |
| action | ACCEPT analysé ; REJECT visible au diagnostic |
| log-status | OK exploitable ; NODATA/SKIPDATA au diagnostic |

AWS emploie `-` lorsqu’un champ ne peut pas être renseigné. Un champ nécessaire
absent rend la ligne inexploitable ; aucune imputation n’est faite. Les champs
supplémentaires ne remplacent pas silencieusement les adresses standard.
[Définition officielle des champs](https://docs.aws.amazon.com/vpc/latest/userguide/flow-log-records.html).

Les IP source/destination du format standard peuvent refléter le point
intermédiaire plutôt que le paquet original, notamment avec NAT et adresses
secondaires. Ce premier adaptateur ne résout pas `pkt-srcaddr`/`pkt-dstaddr`,
les changements d’adresses ni les sauts réseau : utiliser une ENI de charge de
travail à IP primaire connue, sans NAT/transit comme point de collecte.
[Limites AWS](https://docs.aws.amazon.com/vpc/latest/userguide/flow-logs-limitations.html).

Informations absentes : vérité terrain, intention, identité applicative, charge
utile, chronologie des paquets et répartition des octets à l’intérieur d’un
intervalle. Aucun `label`, `scenario` ou statut « normal » n’est fabriqué.
`origin=aws_manual_import` désigne la voie d’import, pas une preuve d’authenticité.
Un enregistrement de flux est une agrégation, pas nécessairement une connexion ;
`flow_count` signifie ici nombre d’enregistrements retenus. Il n’est donc pas
strictement comparable au compteur du générateur synthétique.

## Périmètre explicite et direction

Avant la collecte, relever l’ENI et les IP attribuées à la machine du laboratoire.
Exemple fictif : `eni-0123456789abcdef0`, IP primaire `10.0.1.25/32`. Pour IPv6,
utiliser `/128` pour un hôte. Un CIDR de sous-réseau n’est acceptable que si tous
ses hôtes appartiennent réellement au laboratoire. Aucun réseau privé n’est
considéré comme interne automatiquement ; `/0` et CIDR non alignés sont refusés.

- Source dans le laboratoire et destination hors laboratoire : outbound, hôte source.
- Destination dans le laboratoire et source hors laboratoire : inbound, hôte destination.
- Les deux dedans : internal, exclu de la chaîne de frontière, signalé au diagnostic.
- Aucun dedans : outside, exclu et signalé.

« Sortant » signifie sortir du périmètre déclaré, pas nécessairement aller sur
Internet. Une autre machine privée peut être extérieure au laboratoire. Un seul
point ENI est autorisé par lot ; d’autres interfaces sont comptées à part.
`flow-direction`, s’il est présent, décrit l’ENI et ne remplace pas cette convention.
Le périmètre retenu doit correspondre à l’inventaire pendant la période observée.

## Contrôles, pertes et doublons

Le diagnostic donne fichier, ligne, motif, octets/paquets tels que rapportés.
La synthèse compte les lignes par état ; lignes blanches et en-têtes n’y figurent
pas. Les deux compteurs manquants des états de collecte restent `-`, jamais zéro.
Les répétitions sont classées duplicate en priorité après contrôle du nombre de
champs, avant les autres états : les catégories du résumé sont exclusives.

Contrôles sur les lignes OK : IP valides et même famille, ports/protocole bornés,
compteurs entiers non négatifs, end ≥ start, horodatages en secondes (les valeurs
en millisecondes sont hors plage), borne pandas ns, pas de futur à plus de cinq
minutes. Octets positifs avec zéro paquet sont refusés. Chaque compteur et le total
du lot sont bornés à int64 pour éviter un débordement silencieux. Ce sont des
contrôles de cohérence, pas une certification de l’exactitude des compteurs.

Les compteurs sont des totaux **par enregistrement**, pas des compteurs cumulatifs :
on somme les lignes retenues, sans calculer de différence entre lignes. Les ports
0 ne sont pas assimilés à des valeurs manquantes. L’analyse est limitée à TCP/UDP ;
ICMP n’est pas interprété comme un scan du port 0. Les lignes REJECT restent
visibles au diagnostic mais ne contribuent pas à un volume supposé transféré : les
scans entièrement bloqués ne sont donc pas détectés par cette première chaîne.
Les exemples officiels distinguent ACCEPT, REJECT, NODATA et SKIPDATA ; SKIPDATA
indique une perte de collecte, pas une activité nulle.
[Exemples AWS](https://docs.aws.amazon.com/vpc/latest/userguide/flow-logs-records-examples.html).

Les doublons exacts (tous les champs nommés, ENI comprise) sont supprimés entre
les fichiers du même lot, même si un fichier est gzip ou l’en-tête réordonné.
La première occurrence garde son fichier/numéro de ligne. Aucun dédoublonnage
persistant entre sessions ni rapprochement de captures partiellement recouvrantes.
Deux captures de points différents ou d’intervalles différents peuvent représenter
les mêmes paquets sans être identiques. Ne pas mélanger plusieurs configurations
de collecte ou vues réseau ; choisir une seule ENI ne résout pas tous ces cas.
Les lignes non identiques ne sont jamais fusionnées au jugé.

Une erreur d’encodage/gzip exclut le fichier et le signale. Un en-tête incohérent
arrête le lot pour éviter un mauvais mappage. Limites locales : 20 Mio par fichier
compressé et décompressé, 50 Mio décompressés par lot. Les sommes hors int64 arrêtent
le lot. Ces limites protègent ce prototype, pas une chaîne de gros volumes.

## Fenêtres de cinq minutes : approximation visible

Le champ local `timestamp` est **end**, jamais la date d’upload. L’agrégation est
UTC avec fenêtres fixes `[début, début+5min[`. Les heures start/end sont conservées.

Deux politiques explicites :

- `exclude` (défaut) : si floor(start, 5min) ≠ floor(end, 5min), exclure la ligne
  de l’analyse et la compter comme cross_window_excluded.
- `end` : placer intégralement l’enregistrement dans la fenêtre de fin et marquer
  crosses_windows. Le nombre d’octets est conservé, leur position temporelle est
  approximative ; aucun prorata ni duplication d’octets n’est inventé.

Un end exactement sur une frontière appartient à la fenêtre suivante. Même un
intervalle court peut franchir une frontière. Exclure réduit la couverture et peut
masquer des alertes ; affecter à la fin peut créer/déplacer des pics et alertes.
Même une ligne contenue dans une fenêtre reste une observation agrégée. Des
intervalles d’une minute réduisent le problème sans le supprimer. Le maximum AWS
peut être d’une ou dix minutes ; les temps de capture ne sont pas des horloges
exactes des paquets. [Intervalles AWS](https://docs.aws.amazon.com/vpc/latest/userguide/flow-log-records.html).

Les sommes indiquées concernent seulement les lignes retenues. Les exclusions,
SKIPDATA et fichiers manquants rendent les volumes incomplets. Si aucun entrant
n’est retenu, bytes_in est absent des indicateurs ; sinon les zéros signifient
« aucun entrant retenu dans cette fenêtre », pas « absence de trafic prouvée ».
L’interface montre les diagnostics avant les alertes pour rendre cela visible.

## Utiliser l’import

```bash
source .venv/bin/activate
streamlit run app.py
```

Choisir **Import AWS manuel**, saisir les CIDR réels et l’ENI, puis déposer les
fichiers téléchargés. Les fichiers importés ne sont pas écrits sur disque par
l’interface et ne sont pas mis dans un cache de données ; les exports sont proposés
au téléchargement. Les expériences synthétiques sont dans un mode distinct.
Les règles de référence restent 20 ports / 50 Mo ; Isolation Forest n’est ni
entraîné ni évalué sur les imports. Aucune précision/rappel/F1 n’est calculée sans
expériences réelles étiquetées et protocole distinct.

Équivalent CLI, après téléchargement, à adapter aux IP et chemins réels :

```bash
python -m smart_ids.aws_flow_logs data/aws/mon-export.log.gz \
  --lab-cidr 10.0.1.25/32 \
  --interface-id eni-0123456789abcdef0
```

Ajouter plusieurs chemins pour dédoublonner un lot ; répéter `--lab-cidr` pour
plusieurs réseaux. Ajouter `--window-policy end` uniquement en acceptant
l’approximation. Sorties locales dans `reports/aws_manual/` : flows.csv,
diagnostics.csv, rule_alerts.csv et import_metadata.json. Elles sont remplacées
à chaque invocation ; choisir `--output` pour conserver un autre lot. Ces chemins
et `data/aws/` sont ignorés par Git. Ne pas mettre de vrais exports dans les fixtures.

## Collecte minimale depuis la console AWS — à réaliser manuellement

Aucune des opérations suivantes n’est exécutée par le prototype.

1. Utiliser une machine/ENI de laboratoire déjà disponible. Noter région, ENI,
   IP primaire et période. Préparer un bucket S3 privé dédié dans cette région,
   avec blocage d’accès public, chiffrement SSE-S3 et rétention courte adaptée au TP.
2. Dans EC2 → Network Interfaces, sélectionner **cette ENI** → Create flow log.
   Choisir ALL, maximum aggregation interval **1 minute**, destination S3,
   format d’enregistrement **AWS default**, format de fichier **Text**.
3. Vérifier le statut et l’erreur de livraison éventuelle, puis générer une courte
   activité autorisée de laboratoire. Attendre la publication, dont le délai n’est
   pas une garantie. Dans S3, télécharger manuellement les `.log.gz` de la période.
4. Importer ces fichiers localement avec l’ENI et le périmètre correspondants.
   Garder les journaux originaux pour pouvoir réexaminer les exclusions.
5. Après le TP, supprimer la configuration Flow Log pour arrêter la collecte.
   Cela ne supprime pas les objets S3 déjà stockés ; gérer leur rétention séparément.

Le formulaire console propose ces choix de destination et de format.
[Création vers S3](https://docs.aws.amazon.com/vpc/latest/userguide/flow-logs-s3-create-flow-log.html).
Les objets sont rangés par compte, région et date sous AWSLogs ; le moment de
publication d’un fichier diffère du temps des flux.
[Structure S3](https://docs.aws.amazon.com/vpc/latest/userguide/flow-logs-s3-path.html).

### Permissions à préparer

Distinguer le rôle qui configure la collecte, le service de livraison et le rôle
qui télécharge. Ne pas donner AdministratorAccess pour ce TP.

- Configuration Flow Logs : `ec2:CreateFlowLogs`, `ec2:DescribeFlowLogs`,
  `ec2:DeleteFlowLogs` ; consultation des ENI : `ec2:DescribeNetworkInterfaces`.
  Le balisage éventuel exige aussi `ec2:CreateTags`. Adapter la portée/les conditions
  au laboratoire selon les ressources prises en charge ; les opérations Describe
  nécessitent généralement `Resource: "*"`.
  [Gestion IAM](https://docs.aws.amazon.com/vpc/latest/userguide/working-with-flow-logs.html),
  [Actions EC2](https://docs.aws.amazon.com/service-authorization/latest/reference/list_ec2.html).
- Pour la livraison S3, le rôle créateur doit aussi avoir `logs:CreateLogDelivery`
  et `logs:DeleteLogDelivery`, sur `*` selon l’exemple officiel.
  [Prérequis S3](https://docs.aws.amazon.com/vpc/latest/userguide/flow-logs-s3-create-flow-log.html).
- Politique du bucket : autoriser `delivery.logs.amazonaws.com` à `s3:PutObject`
  sur le préfixe de livraison et à `s3:GetBucketAcl` sur le bucket ; conditions
  `aws:SourceAccount`, `aws:SourceArn` et ACL bucket-owner-full-control selon le
  modèle officiel. Faire préparer cette politique par le propriétaire du bucket.
  Si le créateur la fait attacher automatiquement, il lui faut GetBucketPolicy et
  PutBucketPolicy ; AWS signale que cette opération peut remplacer une politique
  existante. Employer un bucket dédié et vérifier la politique.
  [Politique de livraison officielle](https://docs.aws.amazon.com/vpc/latest/userguide/flow-logs-s3-permissions.html).
- Téléchargement : `s3:ListBucket` limité au préfixe et `s3:GetObject` sur ses objets ;
  la navigation console peut demander `s3:ListAllMyBuckets` et `s3:GetBucketLocation`.
  Un administrateur peut préparer le bucket en amont ; sa création et sa gestion
  de rétention ne sont pas nécessaires au rôle lecteur.
  [Téléchargement S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/download-objects.html).

Cette procédure utilise S3 directement, pas un rôle de publication CloudWatch Logs.
Si SSE-KMS est imposé, prévoir en plus la politique de clé de livraison et le droit
Decrypt pour le lecteur ; cette variante ne fait pas partie de la procédure minimale.
[Variante SSE-KMS](https://docs.aws.amazon.com/vpc/latest/userguide/flow-logs-s3-cmk-policy.html).
Les SCP, politiques du bucket et frontières de permissions peuvent restreindre ces
rôles ; le prototype ne les configure pas.

### Ressources facturables

- Livraison/ingestion et archivage des VPC Flow Logs : tarification Vended Logs,
  même avec une destination S3 directe.
  [Publication S3](https://docs.aws.amazon.com/vpc/latest/userguide/flow-logs-s3.html),
  [Tarification CloudWatch](https://aws.amazon.com/cloudwatch/pricing/).
- Stockage S3, requêtes et transferts applicables lors du téléchargement.
  [Tarification S3](https://aws.amazon.com/s3/pricing/).
- Machine EC2, volumes EBS, IPv4 publique, trafic et NAT éventuel restent des coûts
  séparés du laboratoire. Cette intégration ne nécessite pas de créer un NAT,
  CloudWatch Log Group, Athena, Lambda ou autre pipeline.
  [Tarification VPC](https://aws.amazon.com/vpc/pricing/).

Le montant dépend de la région et des volumes ; aucun prix fixe ni gratuité n’est
supposé. Limiter le temps de collecte et les interfaces, vérifier l’estimation
AWS et les coûts réels. Une minute produit davantage d’enregistrements que dix.

## Vérifications et statut de validation

```bash
python -m unittest discover -s tests -v
python -m smart_ids.aws_flow_logs tests/fixtures/aws_v2_examples.log \
  --lab-cidr 10.0.1.25/32 --interface-id eni-lab1 --output /tmp/smart-ids-aws-example
```

La deuxième commande utilise des **exemples documentaires**, pas des données
réelles. La fixture contient un exemple ACCEPT officiel et des variantes adaptées
pour les autres états. Les tests couvrent le format v2 et custom à en-tête,
gzip, IPv6, bidirectionnalité, doublons entre fichiers, champs manquants,
compteurs invalides, frontières temporelles et interface Streamlit.
Le succès du parseur vérifie des transformations ; il ne valide pas une détection
sur des attaques AWS réelles. Le jeu final synthétique réservé n’est jamais chargé.
