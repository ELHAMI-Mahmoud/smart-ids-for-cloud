"""Consultation de l'historique, preuves et qualification des alertes."""
import os
from pathlib import Path
import sqlite3

import streamlit as st

from smart_ids.exports import csv_bytes, export_bundle
from smart_ids.pipeline import ROOT
from smart_ids.service import evidence
from smart_ids.storage import QUALIFICATIONS, STATUSES, Store


def get_store():
    return Store(Path(os.environ.get('SMART_IDS_DB', str(ROOT / 'var/smart_ids.sqlite3'))))


def render_analysis(analysis, store):
    aid = analysis['id']
    st.caption(f"Analyse {aid} · {analysis['created_at']} · moteur {analysis['engine_version']} · {analysis['source']}")
    if analysis['source'] == 'synthetic':
        st.warning('DONNÉES SYNTHÉTIQUES — les résultats ne mesurent aucune performance AWS réelle.')
    with st.expander('Configuration et sources conservées'):
        st.json(dict(configuration=analysis['config'], fichiers=analysis['files']))
    st.subheader('Qualité et périmètre des données')
    diagnostics = analysis['diagnostics']
    if not diagnostics.empty:
        summary = diagnostics.groupby('status').size().rename('lines').reset_index()
        st.dataframe(summary, hide_index=True, width='stretch')
    with st.expander('Diagnostic détaillé par fichier et ligne'):
        st.dataframe(diagnostics, hide_index=True, width='stretch')
    if analysis['flows'].empty:
        st.info('Aucun enregistrement utilisable après contrôles. Les diagnostics restent conservés.')
    st.caption(f"{len(analysis['flows'])} enregistrements retenus ; traitement moteur : {analysis['elapsed_seconds']:.3f} s, sauvegarde et interface exclues.")
    if 'crosses_windows' in analysis['flows'] and analysis['flows'].crosses_windows.any():
        st.warning('Approximation temporelle : les octets traversant une frontière sont affectés à la fenêtre de fin.')
    st.subheader('Indicateurs par hôte et fenêtre UTC')
    st.dataframe(analysis['windows'], hide_index=True, width='stretch')
    st.caption('Les volumes portent sur les lignes retenues. Absence de ligne ne prouve pas absence de trafic.')
    st.subheader('Alertes et preuves')
    alerts = analysis['alerts']
    filtered = alerts
    if alerts.empty:
        st.info('Aucune alerte parmi les données retenues. Consulter les pertes et exclusions.')
        st.dataframe(alerts, hide_index=True, width='stretch')
    else:
        a, b, c = st.columns(3)
        with a:
            host = st.selectbox('Hôte', ['Tous', *sorted(alerts.src_ip.unique())], key=f'host-{aid}')
        with b:
            detector = st.selectbox('Détecteur', ['Tous', *sorted(alerts.detector_id.unique())], key=f'detector-{aid}')
        with c:
            status = st.selectbox('Statut', ['Tous', *STATUSES], key=f'status-filter-{aid}')
        dates = st.date_input('Période des alertes en UTC',
                             value=(alerts.window.min().date(), alerts.window.max().date()), key=f'dates-{aid}')
        filtered = alerts.copy()
        if host != 'Tous':
            filtered = filtered.loc[filtered.src_ip.eq(host)]
        if detector != 'Tous':
            filtered = filtered.loc[filtered.detector_id.eq(detector)]
        if status != 'Tous':
            filtered = filtered.loc[filtered.status.eq(status)]
        if isinstance(dates, (list, tuple)) and dates:
            filtered = filtered.loc[(filtered.window.dt.date >= dates[0]) & (filtered.window.dt.date <= dates[-1])]
        columns = ['alert_id', 'window', 'src_ip', 'dst_ip', 'rule', 'value', 'threshold', 'unit', 'status', 'qualification']
        st.dataframe(filtered[columns], hide_index=True, width='stretch')
        st.download_button('Exporter les alertes filtrées', csv_bytes(filtered), 'filtered_alerts.csv',
                           'text/csv', key=f'filtered-export-{aid}')
        if filtered.empty:
            st.info('Aucune alerte ne correspond aux filtres.')
        else:
            selected = st.selectbox('Alerte à examiner', filtered.alert_id.tolist(),
                                    format_func=lambda key: f"{filtered.set_index('alert_id').loc[key, 'rule']} · {key[:8]}",
                                    key=f'alert-{aid}')
            decision = alerts.set_index('alert_id').loc[selected]
            st.write(f"{decision['rule']} : {decision['value']} {decision['unit']} ; seuil {decision['threshold']}.")
            st.dataframe(evidence(analysis, selected), hide_index=True, width='stretch')
            st.caption('La qualification manuelle conserve la décision initiale et les preuves.')
            with st.form(f'qualify-{selected}'):
                new_status = st.selectbox('Nouveau statut', STATUSES, index=STATUSES.index(decision.status))
                qualification = st.selectbox('Qualification', QUALIFICATIONS, index=QUALIFICATIONS.index(decision.qualification))
                comment = st.text_area('Commentaire', value=decision.comment, max_chars=4000)
                submitted = st.form_submit_button('Enregistrer la qualification')
            if submitted:
                try:
                    store.qualify(selected, new_status, qualification, comment)
                    st.success('Qualification enregistrée.')
                    st.rerun()
                except (ValueError, LookupError, sqlite3.Error) as exc:
                    st.error(str(exc))
            with st.expander('Historique des qualifications'):
                st.dataframe(store.followups(selected), hide_index=True, width='stretch')
    st.subheader('Exporter cette analyse complète')
    for filename, payload in export_bundle(analysis).items():
        st.download_button(f'Télécharger {filename}', payload, filename,
                           'application/json' if filename.endswith('.json') else 'text/csv', key=f'export-{aid}-{filename}')


def render_history():
    st.header('Historique des analyses')
    origin = st.selectbox('Provenance', ['AWS importé', 'Synthétique'])
    source = 'aws_manual_import' if origin == 'AWS importé' else 'synthetic'
    try:
        store = get_store()
        entries = store.list_analyses(source)
        if entries.empty:
            st.info('Aucune analyse enregistrée pour cette provenance.')
            return
        st.dataframe(entries, hide_index=True, width='stretch')
        selected = st.selectbox('Analyse à ouvrir', entries.id.tolist())
        render_analysis(store.load(selected), store)
    except (ValueError, OSError, sqlite3.Error) as exc:
        st.error(f'Historique indisponible : {exc}')
