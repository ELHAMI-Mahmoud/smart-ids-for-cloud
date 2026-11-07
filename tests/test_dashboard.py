import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


class DashboardTests(unittest.TestCase):
    def test_dashboard_and_threshold_controls(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.metric[2].value, '2')
        app.number_input[0].set_value(100)
        app.number_input[1].set_value(100)
        app.run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.metric[2].value, '0')
        self.assertTrue(any('Aucune règle' in message.value for message in app.info))
        self.assertEqual(len(app.tabs), 3)
        self.assertTrue(any('probabilité' in message.value for message in app.info))
        app.selectbox[0].set_value('validation').run(timeout=30)
        self.assertEqual(len(app.exception), 0)
