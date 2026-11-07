"""Vue Streamlit pour fichiers AWS déclarés par l'utilisateur, sans accès cloud."""
import streamlit as st

from smart_ids.anomaly import aggregate
from smart_ids.aws_flow_logs import import_files
from smart_ids.pipeline import detect


def render_aws():
    st.header('AWS · Import manuel de journaux')
    st.warning('Données importées, non étiquetées — provenance déclarée par l’utilisateur. Aucune performance réelle mesurée.')
    st.caption('Fichiers VPC Flow Logs texte standard ou custom avec en-tête, éventuellement gzip. Aucun appel AWS. Les exemples de documentation ne sont pas des captures réelles.')
    cidrs = st.text_area('CIDR des hôtes du laboratoire (un par ligne)',
                         help='Exemple : 10.0.1.25/32. Utiliser uniquement les IP réellement attribuées aux hôtes du laboratoire ; ne pas déclarer tout le VPC par défaut.')
    eni = st.text_input('Interface ENI unique du point de collecte', placeholder='eni-0123456789abcdef0')
    policy = st.selectbox('Enregistrements couvrant plusieurs fenêtres',
                          ['exclude', 'end'], format_func=lambda value: {
                              'exclude': 'Exclure de l’analyse (répartition temporelle inconnue)',
                              'end': 'Affecter tous les octets à la fenêtre de fin (approximation)'}[value])
    uploads = st.file_uploader('Fichiers exportés depuis S3 (.log, .txt, .gz)',
                               type=['log', 'txt', 'gz'], accept_multiple_files=True)
    st.caption('Une seule ENI de charge de travail, sans NAT ni point de transit. Les échanges internes, hors périmètre et REJECT restent au diagnostic. Les doublons exacts sont éliminés dans ce lot uniquement.')
    if not uploads:
        st.info('Définir le laboratoire et importer des fichiers pour commencer.')
        return
    try:
        result = import_files([(f.name, f.getvalue()) for f in uploads],
                              [line.strip() for line in cidrs.splitlines() if line.strip()],
                              eni.strip(), policy)
    except ValueError as exc:
        st.error(str(exc))
        return
    st.subheader('Qualité et périmètre des données')
    st.write(f'Laboratoire : {", ".join(result.scope)} · ENI : {result.interface_id}')
    st.dataframe(result.summary, hide_index=True, width='stretch')
    st.download_button('Télécharger le diagnostic d’import', result.diagnostics.to_csv(index=False),
                       'aws_import_diagnostics.csv', 'text/csv')
    with st.expander('Détail par ligne, y compris exclusions et compteurs rapportés'):
        st.dataframe(result.diagnostics, hide_index=True, width='stretch')
    if result.flows.empty:
        st.info('Aucun enregistrement utilisable après contrôles. Consulter les diagnostics et vérifier le périmètre.')
        return
    st.caption(f'{len(result.flows)} enregistrements retenus ; {sum(result.flows["bytes"]):,} octets entrants + sortants observés. Un enregistrement agrège des paquets : ce n’est pas une connexion unique.')
    if result.flows.crosses_windows.any():
        st.warning('Approximation temporelle active : les octets des intervalles traversant plusieurs fenêtres sont intégralement placés à la fin. Les pics par fenêtre peuvent être artificiels.')
    windows = aggregate(result.flows)
    st.subheader('Indicateurs observés par hôte et fenêtre de fin UTC')
    st.dataframe(windows, hide_index=True, width='stretch')
    st.caption('bytes_in est omis si aucun entrant n’est observé dans le lot. Même lorsqu’un sens est présent, zéro signifie aucun octet retenu dans ce lot, pas une preuve d’absence de trafic.')
    st.subheader('Alertes des règles · seuils de référence')
    st.caption('20 ports distincts par destination OU 50 000 000 octets sortants en cinq minutes. Alertes exploratoires, sans mesure de précision/rappel sur ces fichiers.')
    alerts = detect(result.flows)
    if alerts.empty:
        st.info('Aucune alerte parmi les enregistrements retenus ; les exclusions et pertes de collecte peuvent masquer du trafic.')
    st.dataframe(alerts, hide_index=True, width='stretch')
    st.download_button('Télécharger les alertes AWS', alerts.to_csv(index=False),
                       'aws_rule_alerts.csv', 'text/csv')
    st.download_button('Télécharger les indicateurs AWS', windows.to_csv(index=False),
                       'aws_windows.csv', 'text/csv')
    st.info('Isolation Forest reste une expérience synthétique. Aucun modèle n’est entraîné ou évalué sur cet import AWS ; les compteurs réels ne sont pas comparables sans protocole dédié.')
