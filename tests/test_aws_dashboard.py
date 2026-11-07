from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


class AwsDashboardTests(unittest.TestCase):
    def test_source_switch_keeps_experiments_separate(self):
        app = AppTest.from_file(str(ROOT / 'app.py')).run(timeout=30)
        app.radio[0].set_value('Import AWS manuel').run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.metric), 0)
        self.assertTrue(any('non étiquetées' in w.value for w in app.warning))
        self.assertEqual(len(app.tabs), 0)

    def test_uploaded_example_and_scope(self):
        upload = SimpleNamespace(name='adapted-documentation-example.log',
                                 getvalue=lambda: (ROOT / 'tests/fixtures/aws_v2_examples.log').read_bytes())
        app = AppTest.from_file(str(ROOT / 'app.py')).run(timeout=30)
        app.radio[0].set_value('Import AWS manuel').run(timeout=30)
        app.text_area[0].set_value('10.0.1.25/32')
        app.text_input[0].set_value('eni-lab1')
        with patch('streamlit.file_uploader', return_value=[upload]):
            app.run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 0)
        self.assertGreaterEqual(len(app.dataframe), 4)
        self.assertTrue(any('Aucun modèle' in info.value for info in app.info))
