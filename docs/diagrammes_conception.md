# Diagrammes de conception Smart IDS pour AWS

Version cible V1 du 7 novembre 2026. Ces vues accompagnent le cahier des charges. Les blocs SQLite, service d'analyse et qualification représentent des ajouts à réaliser ; les détecteurs et l'import AWS existent déjà. Le ML reste synthétique dans le socle.

## 1 Cas utilisation

```mermaid
flowchart LR
    admin[Administrateur du laboratoire] --> lab[Configurer VM ENI et Flow Logs]
    admin --> export[Télécharger les journaux AWS]
    analyst[Analyste] --> config[Configurer le périmètre et les seuils]
    analyst --> imp[Importer et contrôler un lot]
    analyst --> view[Consulter alertes et preuves]
    analyst --> history[Retrouver une analyse]
    analyst --> qualify[Qualifier une alerte]
    analyst --> reports[Exporter les résultats]
    analyst --> ml[Rejouer une expérience ML synthétique]
```

## 2 Composants

```mermaid
flowchart TD
    files[Fichiers AWS téléchargés] --> adapt[Adaptateur AWS et diagnostics]
    adapt --> norm[Flux normalisés]
    norm --> features[Indicateurs par hôte et fenêtre]
    norm --> rules[Règles de scan et volume sortants]
    rules --> service[Service analyse et justification]
    features --> service
    adapt --> service
    service --> store[(SQLite analyses et alertes)]
    store <--> ui[Interface Streamlit et qualification]
    ui --> out[Exports CSV et JSON]
    synthetic[Générateur synthétique] --> experiment[Expérience ML séparée]
    experiment --> metrics[Métriques synthétiques et fenêtres scorées]
    metrics --> ui
```

## 3 Déploiement

```mermaid
flowchart TD
    subgraph aws[AWS compte du laboratoire]
        subgraph vpc[VPC du laboratoire]
            observed[VM observée IP primaire en /32 et ENI unique]
            target[VM cible contrôlée hors du /32 observé]
            observed -->|Trafic de test accepté| target
            observed -->|Métadonnées ENI| flowlogs[VPC Flow Logs]
        end
        flowlogs --> bucket[(Bucket S3 privé)]
    end
    bucket -->|Téléchargement manuel| exports[Fichiers locaux]
    subgraph pc[PC du binôme]
        exports --> app[Application Python et Streamlit localhost]
        app <--> sqlite[(SQLite locale)]
        app --> results[Exports et rapport]
    end
```

La cible peut être dans le même VPC tout en étant hors du périmètre logique observé. Cette V1 ne nécessite ni NAT comme point de capture, ni service d'analyse exposé sur Internet.

## 4 Séquence import et alerte

```mermaid
sequenceDiagram
    actor U as Analyste
    participant I as Interface
    participant S as Service analyse
    participant D as Stockage SQLite
    participant A as Adaptateur AWS
    participant R as Règles
    U->>I: Fichiers et configuration
    I->>S: Analyser le lot
    S->>S: Valider et calculer l'identité lot configuration
    S->>D: Chercher une analyse identique
    alt Analyse déjà présente
        D-->>S: Identifiant existant
        S-->>I: Ouvrir cette analyse
    else Nouvelle analyse
        S->>A: Importer et diagnostiquer
        A-->>S: Flux retenus et diagnostics
        S->>R: Appliquer la configuration figée
        R-->>S: Alertes et valeurs observées
        S->>D: Sauvegarder analyse événements preuves et alertes
        D-->>S: Identifiant analyse
        S-->>I: Résultats et diagnostics
    end
    I-->>U: Alertes expliquées
    U->>I: Qualifier et commenter
    I->>D: Enregistrer le suivi sans modifier la décision
```

## 5 Modèle de données

```mermaid
erDiagram
    ANALYSE ||--o{ FICHIER_SOURCE : utilise
    ANALYSE ||--o{ EVENEMENT : conserve
    ANALYSE ||--o{ DIAGNOSTIC : rapporte
    ANALYSE ||--o{ FENETRE : calcule
    ANALYSE ||--o{ ALERTE : produit
    ALERTE ||--o{ PREUVE : justifie
    ALERTE ||--o{ QUALIFICATION : suit
    EVENEMENT ||--o{ PREUVE : contribue
    FENETRE o|--o{ PREUVE : explique
    FICHIER_SOURCE ||--o{ DIAGNOSTIC : localise
    FICHIER_SOURCE ||--o{ EVENEMENT : contient
    EXPERIENCE_ML ||--o{ RESULTAT_ML : produit
    ANALYSE {
        string id PK
        string source
        string configuration_json
        string version_code
        string identite_lot_configuration UK
        datetime date_creation_utc
    }
    EVENEMENT {
        string id PK
        string analyse_id FK
        string fichier_id FK
        int ligne
        datetime debut_utc
        datetime fin_utc
        string source_ip
        string destination_ip
        int destination_port
        int octets
        string sens
    }
    ALERTE {
        string id PK
        string analyse_id FK
        string detecteur
        datetime fenetre_utc
        string hote
        string destination
        float valeur
        float seuil
    }
    QUALIFICATION {
        string id PK
        string alerte_id FK
        string statut
        string qualification
        string commentaire
        datetime modification_utc
    }
    EXPERIENCE_ML {
        string id PK
        string protocole_version
        string manifeste_jeux
        int graine
        string variables
        float seuil_validation
    }
```

Le modèle est conceptuel : les champs complets, index, types SQLite et contraintes seront définis dans le ticket L01. Une preuve référence un événement ou une fenêtre. Une contrainte de cohérence devra garantir qu'au moins une de ces références est renseignée. Les expériences ML sont conservées à part des analyses AWS.
