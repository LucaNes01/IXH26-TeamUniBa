"""Conteggio atomico delle violazioni confermate per identità certificata."""

import sqlite3
from threading import Lock


class StatoRevoche:
    def __init__(self, percorso, soglia):
        if type(soglia) is not int or soglia < 1:
            raise ValueError("La soglia di revoca deve essere un intero positivo.")
        self._db = sqlite3.connect(percorso, check_same_thread=False)
        self._lock = Lock()
        self.soglia = soglia
        with self._db:
            self._db.execute("CREATE TABLE IF NOT EXISTS regola (id INTEGER PRIMARY KEY, soglia INTEGER)")
            self._db.execute("INSERT OR IGNORE INTO regola VALUES (1, ?)", (soglia,))
            if self._db.execute("SELECT soglia FROM regola WHERE id=1").fetchone()[0] != soglia:
                raise ValueError("La soglia configurata differisce da quella del registro.")
            self._db.execute("""CREATE TABLE IF NOT EXISTS violazioni (
                dispositivo TEXT, raw BLOB, foto BLOB, PRIMARY KEY(dispositivo, raw, foto))""")

    def _totale(self, dispositivo):
        return self._db.execute("SELECT COUNT(*) FROM violazioni WHERE dispositivo=?", (dispositivo,)).fetchone()[0]

    def totale(self, dispositivo):
        with self._lock:
            return self._totale(dispositivo)

    def registra(self, dispositivo, raw_sha256, foto_sha256):
        with self._lock, self._db:
            self._db.execute("BEGIN IMMEDIATE")
            if self._totale(dispositivo) < self.soglia:
                self._db.execute("INSERT OR IGNORE INTO violazioni VALUES (?, ?, ?)",
                                 (dispositivo, raw_sha256, foto_sha256))
            return self._totale(dispositivo)
