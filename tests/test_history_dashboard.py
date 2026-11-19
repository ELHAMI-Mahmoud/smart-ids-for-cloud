"""Parcours intégré interface, filtres, preuve et qualification après redémarrage."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from smart_ids.service import analyze_synthetic
from smart_ids.storage import Store

ROOT = Path(__file__).resolve().parents[1]


def widget(elements, label):
    return next(element for element in elements if element.label == label)


class HistoryDashboardTests(unittest.TestCase):
    def test_filter_qualify_and_reopen_after_new_session(self):
        (ROOT / 'var').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / 'var') as temporary:
            db = Path(temporary) / 'history.sqlite3'
            analysis, _ = analyze_synthetic(Store(db))
            with patch.dict(os.environ, {'SMART_IDS_DB': str(db)}):
                app = AppTest.from_file(str(ROOT / 'app.py')).run(timeout=30)
                app.radio[0].set_value('Historique des analyses').run(timeout=30)
                widget(app.selectbox, 'Provenance').set_value('Synthétique').run(timeout=30)
                self.assertFalse(app.exception)
                widget(app.selectbox, 'Détecteur').set_value('R01').run(timeout=30)
                self.assertFalse(app.exception)
                widget(app.selectbox, 'Nouveau statut').set_value('Clôturé')
                widget(app.selectbox, 'Qualification').set_value('Activité légitime')
                widget(app.text_area, 'Commentaire').set_value('Essai administratif autorisé')
                widget(app.button, 'Enregistrer la qualification').click().run(timeout=30)
                self.assertFalse(app.exception)
                saved = Store(db).load(analysis['id'])['alerts']
                scan = saved.loc[saved.detector_id.eq('R01')].iloc[0]
                self.assertEqual(scan.status, 'Clôturé')
                self.assertEqual(scan.comment, 'Essai administratif autorisé')
                reopened = AppTest.from_file(str(ROOT / 'app.py')).run(timeout=30)
                reopened.radio[0].set_value('Historique des analyses').run(timeout=30)
                widget(reopened.selectbox, 'Provenance').set_value('Synthétique').run(timeout=30)
                self.assertFalse(reopened.exception)
                self.assertTrue(any('Synthétiques' in str(w.value) or 'SYNTHÉTIQUES' in str(w.value) for w in reopened.warning))
