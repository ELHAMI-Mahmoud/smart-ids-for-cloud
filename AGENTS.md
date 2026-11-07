# Smart IDS

Prototype étudiant local sous Python 3.13, pandas, scikit-learn et Streamlit.
Répondre et documenter en français. Garder les changements simples et explicables.

- Toutes les données de démonstration doivent porter la mention synthétique.
- L’import manuel AWS est autorisé, sans appel cloud automatique. Ne pas ajouter
  de secrets, d’automatisation AWS/Azure ou de collecte réseau sans demande.
- Les règles sont une référence explicable ; ne pas présenter un seuil comme un modèle appris.
- Conserver une génération déterministe et des tests des détections et cas sans alerte.
- Vérifier avec `.venv/bin/python -m unittest discover -s tests -v`.
- Lancer la chaîne avec `.venv/bin/python -m smart_ids.pipeline`.
- Entraîner/évaluer Isolation Forest avec `.venv/bin/python -m smart_ids.anomaly`.
- Entraîner uniquement sur le normal d’entraînement, choisir le seuil sur validation.
  Ne jamais ajuster seuils ou hyperparamètres d’après le test. Les fenêtres,
  instances et variantes doivent rester disjointes entre périodes.
- Utiliser la liste explicite des variables numériques ; exclure labels,
  identifiants, IP et périodes. Le score d’anomalie n’est pas une probabilité.
- Lancer l’interface avec `.venv/bin/streamlit run app.py`.
- `baseline/` est un snapshot à conserver ; vérifier ses empreintes sans l’écraser.
- Audit validation : `.venv/bin/python -m smart_ids.audit`. L’ancien test est
  exploratoire. Ne pas charger, scorer ou évaluer `data/synthetic_final_reserved.csv`
  avant gel explicite du protocole. Ce nouvel ensemble est réservé, non consulté.
- Adaptateur AWS : `smart_ids/aws_flow_logs.py`, guide `docs/aws_manual_import.md`.
  Exiger les CIDR du laboratoire et une ENI, signaler les exclusions et ne jamais
  imputer les champs manquants. Pas de métriques réelles sans vérité terrain.
