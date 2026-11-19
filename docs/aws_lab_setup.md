# Créer le laboratoire AWS Smart IDS

Guide du 19 novembre 2026 pour Adam et Mahmoud. Le logiciel reste sur votre PC et importe les journaux téléchargés. Aucune clé AWS n'est nécessaire dans le code. Les ressources ci-dessous sont créées manuellement ; aucune création AWS n'a été effectuée par le développement de cette branche.

## 1 Vérifier votre formule avant de commencer

L'inscription récente avec 100 USD et sans carte ressemble à la nouvelle expérience AWS avec Builder ID et projets. C'est une hypothèse à vérifier dans AWS Settings : projet actif, région sélectionnée, formule Free et solde des crédits. Les comptes/projets peuvent avoir des restrictions différentes.

La documentation actuelle inclut EC2, VPC et S3 dans les services disponibles de cette expérience [A1]. Utiliser la région du projet ; ne pas choisir une autre région au hasard. Conserver la formule gratuite pour ce laboratoire. Une conversion en Paid ou l'activation d'advanced features ne fait pas partie de ce guide. Les politiques gérées et les permissions du rôle utilisé restent applicables [A2].

Dans AWS Settings, consulter le solde et la date d'expiration, puis définir une limite de dépense de projet si ce contrôle est disponible. Un budget/une alerte de coût n'est pas un plafond automatique. La formule Free actuelle se termine à six mois ou à l'épuisement des crédits ; vérifier les conditions affichées dans votre compte [A3]. Ne pas engager les 100 USD pour une infrastructure permanente.

## 2 Ressources nécessaires

| Ressource | Configuration minimale | Rôle |
|---|---|---|
| Un VPC | Réutiliser le VPC par défaut ou préconfiguré du projet, si disponible | Réseau des deux VM |
| Un sous-réseau public | Même zone de disponibilité pour les deux VM ; route vers Internet Gateway pour SSH | Accès d'administration simple |
| Deux instances EC2 | Ubuntu Server 24.04 LTS officielle, x86, petit type disponible et indiqué comme éligible par la console, par exemple t3.micro | Source observée et cible contrôlée |
| Deux volumes racine EBS | 8 Gio gp3 par VM, suppression à la terminaison, sans volume supplémentaire | Système Linux |
| Deux groupes de sécurité | SSH depuis votre IPv4 publique /32 ; ports de test seulement depuis la VM observée | Accès limité au laboratoire |
| Un bucket S3 privé | Même région, nom unique, Block Public Access activé, chiffrement SSE-S3, sans versionnement pour cet essai | Destination des journaux |
| Un Flow Log | Sur l'ENI de la VM observée, destination S3, trafic ALL, texte format par défaut v2, agrégation maximale 1 minute | Métadonnées réseau |

L'application Streamlit et SQLite tournent sur votre PC. RDS, SageMaker, GuardDuty, load balancer et NAT Gateway ne sont pas nécessaires à la V1. Ne pas activer le wizard VPC avec une NAT Gateway par défaut. Si aucun réseau adapté n'existe, créer un VPC simple, un sous-réseau public, une Internet Gateway et la route 0.0.0.0/0 correspondante, sans NAT, après vérification des permissions de votre projet.

Les deux VM ont ici une IPv4 publique pour SSH depuis le PC. Cela évite un bastion/NAT, mais ces IPv4 consomment aussi du budget : le tarif public standard consulté est de 0,005 USD par adresse et par heure, avant franchises ou crédits applicables [A4]. Le calcul complet inclut aussi EC2, EBS, les logs et S3 ; relever les tarifs de la région avant lancement. Des sessions courtes et la suppression après essais limitent l'usage.

## 3 Créer les deux VM et leurs groupes de sécurité

Dans EC2, créer smart-ids-observed et smart-ids-target dans le même sous-réseau. Choisir une AMI Ubuntu officielle, conserver IMDSv2 requis, désactiver le monitoring détaillé pour cet essai. Choisir une paire de clés et la conserver localement hors du dépôt. Ne pas téléverser de .pem sur GitHub.

Pour les exemples suivants, on suppose que les IP privées sont 10.20.1.10 et 10.20.1.20. Remplacer ces adresses par celles réellement attribuées. Dans le groupe de smart-ids-observed, autoriser TCP 22 depuis votre IPv4 publique/32. Dans le groupe de smart-ids-target, autoriser TCP 22 depuis cette même IPv4/32 et TCP 8000 à 8019 depuis l'IP privée de smart-ids-observed/32. Ne pas ouvrir les ports de test à Internet. Les règles sortantes par défaut conviennent à ce laboratoire court.

Se connecter aux deux instances avec le client SSH de votre PC et l'utilisateur ubuntu. L'exemple de commande est ssh -i CHEMIN_CLE.pem ubuntu@IP_PUBLIQUE. Utiliser les IP privées pour les communications entre VM. En cas d'échec SSH, vérifier votre IP publique actuelle, le groupe de sécurité, l'IPv4 publique et la route du sous-réseau.

## 4 Créer S3 et le Flow Log

Créer un bucket dédié, par exemple smart-ids-adam-JETON_UNIQUE, dans la région du projet. Garder le blocage public actif, choisir SSE-S3 et créer une règle de cycle de vie expirant les objets après sept jours pour cet essai. La suppression des objets est asynchrone ; vider/supprimer le bucket à la fin si vous n'en avez plus besoin.

Dans EC2, ouvrir la VM observée, puis son interface réseau primaire. Relever l'ENI eni-... et l'IP privée primaire. Sur cette interface uniquement, créer le Flow Log avec : filtre ALL, destination S3, ARN du nouveau bucket, format de fichier Text, format des logs AWS default format et agrégation maximale 1 minute. Choisir le format standard ; pas Parquet ni un format custom sans en-tête. Attendre l'état de livraison actif.

Pour S3, la livraison utilise une politique du bucket autorisant le service delivery.logs.amazonaws.com, avec conditions SourceAccount et SourceArn [A5]. Ce parcours ne nécessite pas de créer le rôle de livraison CloudWatch souvent montré dans d'autres tutoriels. Quand le créateur possède les droits nécessaires sur ce bucket dédié, la console peut attacher la politique requise. Si AccessDenied apparaît, noter l'opération et le message ; ne pas rendre le bucket public ni activer des fonctions avancées pour contourner le problème.

Un exemple de politique pour un bucket neuf dédié est fourni dans lab/s3-flow-log-policy.example.json. Remplacer BUCKET_NAME, REGION et ACCOUNT_ID ; le numéro de compte est celui du projet exécutant EC2. Ne pas remplacer à l'aveugle la politique d'un bucket contenant d'autres applications.

## 5 Générer des essais sur les deux VM

Copier lab/tcp_sink.py sur la cible et lab/send_test_traffic.py sur la VM observée, par SCP depuis votre PC. Ces scripts utilisent uniquement Python 3 standard ; ils ne nécessitent ni scikit-learn ni Streamlit sur les VM.

Sur la cible, lancer dans un terminal :

```bash
python3 tcp_sink.py --port 8000
```

Sur la VM observée, remplacer la cible ci-dessous par son IP privée :

```bash
python3 send_test_traffic.py --target 10.20.1.20 --scenario normal
python3 send_test_traffic.py --target 10.20.1.20 --scenario scan
python3 send_test_traffic.py --target 10.20.1.20 --scenario volume
```

Exécuter ces trois scénarios dans des fenêtres UTC de cinq minutes distinctes. Noter les sorties JSON et les dates : elles constituent votre journal d'essais indépendant des prédictions. Éviter les frontières de fenêtres ; attendre quelques dizaines de secondes après une frontière pour commencer. Le scan tente exactement vingt ports 8000 à 8019 ; les vingt doivent être autorisés par le groupe de sécurité cible. Seul 8000 doit écouter : un port fermé peut quand même produire un flux ACCEPT au niveau du groupe de sécurité.

Le scénario normal envoie 1 Kio. Le scénario volume envoie 80 Mio de la VM observée vers la cible, sans écrire de données personnelles. Il est important d'envoyer depuis la VM observée : un téléchargement vers cette VM mesurerait principalement des octets entrants et ne validerait pas la règle de volume sortant. Les compteurs réseau AWS comprennent des éléments différents des octets applicatifs annoncés par le script ; ils ne doivent pas être forcés à l'égalité.

## 6 Télécharger puis analyser

Laisser aux journaux le temps d'arriver dans S3. La livraison est différée et best effort, pas instantanée [A6]. Dans le préfixe AWSLogs du bucket, télécharger tous les fichiers .log.gz couvrant les périodes des essais ; un seul fichier peut être incomplet. Conserver les captures réelles hors du dépôt public.

Dans Streamlit, choisir Import AWS manuel, saisir le /32 de la VM observée uniquement, par exemple 10.20.1.10/32, et l'ENI relevée. Ne pas saisir tout le sous-réseau : la cible deviendrait interne et serait exclue du détecteur de frontière. Choisir les seuils 20 ports et 50 000 000 octets, puis téléverser le lot téléchargé.

Commencer avec la politique exclude et examiner les diagnostics. Si des flux de l'essai traversent des frontières de fenêtres, ils peuvent être exclus. L'option end permet une seconde analyse en plaçant tout le compteur à la fin ; conserver cette approximation dans le rapport. Ne pas modifier les seuils pour faire artificiellement réussir une recette.

Résultats attendus : activité normale sans alerte sur les seuls flux de cet essai, scan sortant à vingt ports et alerte de volume sortant. D'autres activités de la VM, des pertes ou des délais peuvent modifier ce résultat. Consulter les preuves de chaque alerte et confronter les périodes au journal d'essais.

L'analyse est conservée dans SQLite. Un lot strictement identique et la même configuration rouvrent l'analyse existante. Qualifier les alertes, redémarrer l'application et vérifier que l'historique est présent. Exporter alertes, diagnostics, indicateurs et metadata.json.

## 7 Fin de session

Fermer le récepteur et arrêter les deux EC2 lorsque vous ne travaillez plus. Les volumes EBS persistent à l'arrêt ; pour finir le laboratoire, télécharger vos preuves, terminer les instances et vérifier la suppression des volumes associés. Supprimer le Flow Log et le bucket dédié après conservation des éléments utiles. Vérifier également les IPv4/Elastic IP éventuellement réservées ; cette procédure ne nécessite pas d'Elastic IP.

Ce guide prépare F11. La validation réelle est acquise seulement après votre exécution documentée. Aucun résultat de précision/rappel n'est déduit des seuls fichiers non étiquetés.

## Références officielles consultées

- A1 Services de la nouvelle expérience : https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html
- A2 Politiques des projets : https://docs.aws.amazon.com/accounts/latest/reference/scps-and-rcps-for-projects.html
- A3 Offre Free Tier et crédits : https://aws.amazon.com/free/
- A4 Tarification IPv4 et VPC : https://aws.amazon.com/vpc/pricing/
- A5 Livraison S3 : https://docs.aws.amazon.com/vpc/latest/userguide/flow-logs-s3-permissions.html
- A6 Formats, agrégation et délais : https://docs.aws.amazon.com/vpc/latest/userguide/flow-log-records.html
