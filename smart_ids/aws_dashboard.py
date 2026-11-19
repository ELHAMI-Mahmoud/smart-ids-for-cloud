"""Import AWS manuel avec résultats persistants ; aucun accès à un compte cloud."""
import sqlite3

import streamlit as st

from smart_ids.config import AnalysisConfig
from smart_ids.service import analyze_aws
from smart_ids.ui import get_store, render_analysis


def render_aws():
    st.header('AWS · Import manuel de journaux')
    st.warning('Données importées, non étiquetées — provenance déclarée par l’utilisateur. Aucune performance réelle mesurée.')
    st.caption('VPC Flow Logs texte standard ou custom avec en-tête, éventuellement gzip. Aucun appel AWS.')
    cidrs = st.text_area('CIDR des hôtes du laboratoire (un par ligne)',
                         help='Adresse réellement surveillée, par exemple 10.0.1.25/32. Une seule ENI, sans NAT/transit.')
    eni = st.text_input('Interface ENI unique du point de collecte', placeholder='eni-0123456789abcdef0')
    policy = st.selectbox('Enregistrements couvrant plusieurs fenêtres', ['exclude', 'end'],
                         format_func=lambda p: 'Exclure et signaler' if p == 'exclude' else 'Tout affecter à la fin (approximation)')
    left, right = st.columns(2)
    with left:
        ports = st.number_input('Seuil de ports distincts par destination', min_value=1, max_value=65536, value=20)
    with right:
        volume = st.number_input('Seuil de volume sortant en octets', min_value=1, max_value=10**12, value=50_000_000)
    st.caption('Seuils inclusifs sur cinq minutes UTC. 50 Mo décimaux = 50 000 000 octets.')
    uploads = st.file_uploader('Fichiers VPC Flow Logs exportés depuis S3', type=['log', 'txt', 'gz'], accept_multiple_files=True)
    st.caption('Les résultats et preuves importés seront conservés localement dans SQLite. Seuls les flux sortants ACCEPT TCP/UDP déclenchent les règles.')
    if not uploads:
        st.info('Définir le laboratoire et importer des fichiers pour commencer.')
        return
    try:
        config = AnalysisConfig(tuple(line.strip() for line in cidrs.splitlines() if line.strip()),
                                eni.strip(), int(ports), int(volume), policy)
        store = get_store()
        analysis, reused = analyze_aws([(f.name, f.getvalue()) for f in uploads], config, store)
        if reused:
            st.info('Lot et configuration déjà analysés : réouverture de l’historique existant.')
        render_analysis(analysis, store)
    except (ValueError, OSError, sqlite3.Error) as exc:
        st.error(str(exc))
        return
    st.info('Isolation Forest reste une expérience synthétique. Aucun modèle n’est appliqué à cet import AWS ; aucune métrique réelle sans vérité terrain.')
