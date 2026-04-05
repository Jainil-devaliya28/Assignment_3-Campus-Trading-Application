import os
import sys
import tempfile
import textwrap

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database.db_manager import DatabaseManager

WAL_PATH = os.path.join(tempfile.gettempdir(), "test_acid.wal")
W = 68

def _banner(title):
    pad = max(0, W - len(title) - 2)
    print(f"\n{'═'*(pad//2)} {title} {'═'*(pad - pad//2)}")

def _section(title):
    print(f"\n  ┌── {title}")

def _step(msg, indent=4):
    prefix = " " * indent + "│  "
    for line in textwrap.wrap(msg, W - indent - 4):
        print(prefix + line)

def _result(label, value, good=True):
    icon = "✔" if good else "✘"
    print(f"  │  {icon}  {label}: {value}")

def _ok(msg):
    print(f"  └─ ✔  {msg}")

def _wal_snapshot(db):
    records = db._wal.get_records()
    if not records:
        _step("WAL is empty.")
        return
    _step(f"WAL now contains {len(records)} record(s):")
    for r in records:
        tbl = f" table={r.table_name}" if r.table_name else ""
        key = f" key={r.key}"          if r.key is not None else ""
        old = f" old={r.old_value}"    if r.old_value is not None else ""
        new = f" new={r.new_value}"    if r.new_value is not None else ""
        print(f"     LSN {r.lsn:>3} │ txn={r.txn_id} │ {r.record_type.value:<10}{tbl}{key}{old}{new}")

def _table_snapshot(db, table_name):
    table    = db.get_table(table_name)
    rec_keys = sorted(table.records.keys())
    idx_keys = sorted(k for k, _ in table.bplustree.get_all())
    _step(f"Table '{table_name}' records dict  : {rec_keys}")
    _step(f"Table '{table_name}' B+ Tree index : {idx_keys}")
    _step(f"Index ↔ Records in sync           : {'YES ✔' if rec_keys == idx_keys else 'NO ✘'}")

def fresh_db(name="testdb"):
    if os.path.exists(WAL_PATH):
        os.remove(WAL_PATH)
    db = DatabaseManager(name, log_path=WAL_PATH, auto_recover=False)
    db.create_table("users", "id", order=4)
    return db