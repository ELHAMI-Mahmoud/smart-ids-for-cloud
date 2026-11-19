"""Historique SQLite local avec écritures atomiques et suivi séparé des décisions."""
from contextlib import contextmanager
from datetime import datetime, timezone
from io import StringIO
import json
from pathlib import Path
import sqlite3

import pandas as pd

STATUSES = ['Nouveau', 'En cours', 'Clôturé']
QUALIFICATIONS = ['Non déterminé', 'Activité légitime', 'Suspect à examiner']


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def frame_json(frame):
    return frame.to_json(orient='split', date_format='iso', date_unit='ns', index=False)


def read_frame(value):
    result = pd.read_json(StringIO(value), orient='split', convert_dates=False, dtype=False)
    for name in ['timestamp', 'start_time', 'end_time', 'window']:
        if name in result and not result.empty:
            result[name] = pd.to_datetime(result[name], utc=True)
    return result


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            version = connection.execute('PRAGMA user_version').fetchone()[0]
            if version not in [0, 1]:
                raise ValueError('Version de base SQLite non prise en charge.')
            connection.executescript('''
                CREATE TABLE IF NOT EXISTS analyses (
                    id TEXT PRIMARY KEY, identity TEXT NOT NULL UNIQUE,
                    source TEXT NOT NULL CHECK(source IN ('aws_manual_import','synthetic')),
                    created_at TEXT NOT NULL, engine_version TEXT NOT NULL,
                    config_json TEXT NOT NULL, files_json TEXT NOT NULL,
                    flows_json TEXT NOT NULL, windows_json TEXT NOT NULL,
                    diagnostics_json TEXT NOT NULL, elapsed_seconds REAL NOT NULL,
                    flow_count INTEGER NOT NULL, alert_count INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS alerts (
                    id TEXT PRIMARY KEY, analysis_id TEXT NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
                    decision_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Nouveau',
                    qualification TEXT NOT NULL DEFAULT 'Non déterminé', comment TEXT NOT NULL DEFAULT '',
                    modified_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS alert_analysis ON alerts(analysis_id);
                CREATE TABLE IF NOT EXISTS followups (
                    id INTEGER PRIMARY KEY, alert_id TEXT NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
                    status TEXT NOT NULL, qualification TEXT NOT NULL,
                    comment TEXT NOT NULL, modified_at TEXT NOT NULL
                );
                PRAGMA user_version=1;
            ''')

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def find_identity(self, identity):
        with self.connect() as connection:
            row = connection.execute('SELECT id FROM analyses WHERE identity=?', (identity,)).fetchone()
        return row['id'] if row else None

    def save(self, analysis):
        """Insertion atomique ; une course sur le même lot réutilise le premier résultat."""
        a = analysis
        try:
            with self.connect() as connection:
                connection.execute('''INSERT INTO analyses VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
                    a['id'], a['identity'], a['source'], a['created_at'], a['engine_version'],
                    json.dumps(a['config'], ensure_ascii=False), json.dumps(a['files'], ensure_ascii=False),
                    frame_json(a['flows']), frame_json(a['windows']), frame_json(a['diagnostics']),
                    a['elapsed_seconds'], len(a['flows']), len(a['alerts'])))
                for decision in a['alerts'].to_dict('records'):
                    payload = json.dumps(decision, default=lambda v: v.isoformat(), ensure_ascii=False, allow_nan=False)
                    connection.execute('''INSERT INTO alerts
                        (id,analysis_id,decision_json,modified_at) VALUES (?,?,?,?)''',
                        (decision['alert_id'], a['id'], payload, a['created_at']))
        except sqlite3.IntegrityError:
            existing = self.find_identity(a['identity'])
            if existing:
                return existing, True
            raise
        return a['id'], False

    def list_analyses(self, source=None):
        sql = '''SELECT id, source, created_at, engine_version, flow_count, alert_count,
                        elapsed_seconds FROM analyses'''
        parameters = ()
        if source is not None:
            sql += ' WHERE source=?'
            parameters = (source,)
        with self.connect() as connection:
            return pd.read_sql_query(sql+' ORDER BY created_at DESC, id', connection, params=parameters)

    def load(self, analysis_id):
        with self.connect() as connection:
            row = connection.execute('SELECT * FROM analyses WHERE id=?', (analysis_id,)).fetchone()
            if row is None:
                raise LookupError('Analyse introuvable.')
            alerts = connection.execute('SELECT * FROM alerts WHERE analysis_id=? ORDER BY rowid', (analysis_id,)).fetchall()
        result = dict(row)
        result['config'] = json.loads(result.pop('config_json'))
        result['files'] = json.loads(result.pop('files_json'))
        for name in ['flows', 'windows', 'diagnostics']:
            result[name] = read_frame(result.pop(name+'_json'))
        records = []
        for alert in alerts:
            decision = json.loads(alert['decision_json'])
            decision.update({key: alert[key] for key in ['status', 'qualification', 'comment', 'modified_at']})
            records.append(decision)
        result['alerts'] = pd.DataFrame(records)
        if 'window' in result['alerts']:
            result['alerts']['window'] = pd.to_datetime(result['alerts']['window'], utc=True)
        return result

    def qualify(self, alert_id, status, qualification, comment=''):
        if status not in STATUSES or qualification not in QUALIFICATIONS:
            raise ValueError('Statut ou qualification inconnu.')
        if not isinstance(comment, str) or len(comment) > 4000:
            raise ValueError('Le commentaire est limité à 4 000 caractères.')
        when = utc_now()
        with self.connect() as connection:
            cursor = connection.execute('''UPDATE alerts SET status=?,qualification=?,comment=?,modified_at=? WHERE id=?''',
                                        (status, qualification, comment, when, alert_id))
            if cursor.rowcount != 1:
                raise LookupError('Alerte introuvable.')
            connection.execute('''INSERT INTO followups(alert_id,status,qualification,comment,modified_at)
                                  VALUES (?,?,?,?,?)''', (alert_id, status, qualification, comment, when))

    def followups(self, alert_id):
        with self.connect() as connection:
            return pd.read_sql_query('SELECT * FROM followups WHERE alert_id=? ORDER BY id', connection, params=(alert_id,))
