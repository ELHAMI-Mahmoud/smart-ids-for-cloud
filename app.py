import streamlit as st

from smart_ids.pipeline import detect, generate_flows

st.set_page_config(page_title='Smart IDS · Laboratoire', page_icon='🔎', layout='wide')
st.title('Smart IDS — Laboratoire de flux')
mode = st.sidebar.radio('Source de données', ['Démonstration synthétique', 'Import AWS manuel'])
if mode == 'Import AWS manuel':
    from smart_ids.aws_dashboard import render_aws
    render_aws()
    st.stop()
st.warning('DÉMONSTRATION · Données entièrement synthétiques · Aucun cloud connecté')
st.caption('Observer une heure de trafic fictif et expliquer chaque alerte sur une fenêtre de 5 minutes UTC.')
with st.sidebar:
    st.header('Seuils de détection')
    ports = st.number_input('Ports distincts par source et destination', 1, 1000, 20)
    megabytes = st.number_input('Volume sortant par source (Mo décimaux)', 1, 1000, 50)
    st.caption('Seuils inclusifs. Fenêtres fixes de 5 minutes. Les scénarios ne servent pas à la détection.')
flows = generate_flows()
alerts = detect(flows, int(ports), int(megabytes) * 1_000_000)
left, middle, right = st.columns(3)
left.metric('Flux synthétiques', len(flows))
middle.metric('Sources observées', flows.src_ip.nunique())
right.metric('Alertes', len(alerts))
st.subheader('Chronologie du volume sortant')
timeline = flows.set_index('timestamp').groupby('src_ip')['bytes'].resample('5min').sum().unstack(0).fillna(0)
st.line_chart(timeline / 1_000_000, y_label='Mo / 5 minutes', x_label='Heure UTC')
st.subheader('Alertes expliquées')
if alerts.empty:
    st.info('Aucune règle ne dépasse les seuils actuels. Réduisez les seuils pour explorer les scénarios.')
else:
    st.dataframe(alerts, hide_index=True, width='stretch')
st.download_button('Télécharger les alertes synthétiques', alerts.to_csv(index=False),
                   'synthetic_alerts.csv', 'text/csv')
with st.expander('Examiner les flux et les scénarios injectés'):
    st.caption('scenario est la vérité terrain de génération, pas une entrée des règles.')
    st.dataframe(flows, hide_index=True, width='stretch')

st.divider()
st.header('Isolation Forest · Évaluation synthétique')
st.caption('Expérience indépendante de la démonstration ci-dessus. Les seuils manuels de la barre latérale ne modifient pas cette comparaison : règles fixes à 20 ports et 50 Mo.')

from smart_ids.anomaly import run_experiment


@st.cache_data
def ml_results():
    result = run_experiment()
    return {key: value for key, value in result.items() if key != 'model'}


result = ml_results()
st.write(f"Seuil choisi sur validation : {result['threshold']:.6f}")
st.info('Le score est −score_samples : plus il est élevé, plus la fenêtre est atypique pour le modèle. Ce score n’est pas une probabilité d’attaque.')
st.caption('Une ligne évaluée = un hôte interne sur cinq minutes UTC. Combinaison : règle OU modèle. Entraînement : 240 fenêtres normales ; validation et test : 160 fenêtres chacun.')
st.dataframe(result['metrics'], hide_index=True, width='stretch')
period = st.selectbox('Période à examiner', ['test', 'validation', 'train'])
observations = result['windows'].query('split == @period')
columns = ['window', 'host', *result['features'], 'anomaly_score',
           'rule_alert', 'model_alert', 'combined_alert']
rule_tab, model_tab, all_tab = st.tabs(['Alertes des règles', 'Alertes du modèle', 'Toutes les fenêtres'])
with rule_tab:
    st.dataframe(observations.loc[observations.rule_alert, columns], hide_index=True, width='stretch')
    st.caption('Détail des règles : valeur observée, seuil et unité.')
    events = result['rule_events']
    keys = set(zip(observations.window, observations.host))
    st.dataframe(events.loc[[(w, h) in keys for w, h in zip(events.window, events.src_ip)]],
                 hide_index=True, width='stretch')
with model_tab:
    st.dataframe(observations.loc[observations.model_alert, columns], hide_index=True, width='stretch')
with all_tab:
    st.dataframe(observations[columns], hide_index=True, width='stretch')
    st.download_button('Télécharger les fenêtres synthétiques évaluées',
                       observations.to_csv(index=False), 'synthetic_ml_windows.csv', 'text/csv')
