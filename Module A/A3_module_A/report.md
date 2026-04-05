# Database ACID & Index Consistency Validation Report

## Overview

This report outlines the unit testing and validation strategies applied to ensure strict adherence to ACID properties within the custom database engine and its underlying B+ Tree indexing structure.

The test suite was modularized into four distinct domains and executed independently using Python's `unittest` framework. Across all domains, a total of 15 tests were executed successfully, validating the engine's operational completeness, failure recovery, and structural synchronization.

---

## 1. Atomicity Validation

**Technical Implementation:**

* **File:** `test_atomicity.py`
* **Class:** `TestAtomicity` (Inherits from `unittest.TestCase`)

**Objective:**
Ensure that every operation completes entirely or leaves no trace, meaning no partial updates remain if an interruption or failure occurs.

**Steps Used for Validation (The "All-or-Nothing" Rule):**

* **Normal Save (`test_successful_single_insert_commits`):** Tested that a standard insertion saves data correctly when finalized.
* **Undo an Insert (`test_rollback_insert_leaves_no_trace`):** Proved that if an insertion fails or is canceled (rolled back), the new row completely disappears without a trace.
* **Undo an Update (`test_rollback_update_restores_old_value`):** Proved that if an update is canceled halfway through, the database successfully remembers and restores the old data.
* **Undo a Delete (`test_rollback_delete_restores_row`):** Proved that if a deletion is canceled, the deleted row is brought back to life as if nothing happened.
* **Undo Multiple Steps (`test_multi_op_transaction_rolls_back_completely`):** Created a test where a transaction does two things (inserting and updating). Proved that if it gets canceled, the database neatly undoes both actions in reverse order.

**Execution Flow:**
Each test follows a strict three-phase narrative flow:

1. **Setup:** Initializes a fresh database with baseline committed data.
2. **Action:** Stages Write-Ahead Log (WAL) operations (Insert, Update, Delete) within a transaction, followed by a simulated failure forcing a `ROLLBACK`.
3. **Verification:** Queries the database to confirm the `Transaction.abort()` logic successfully reversed the operations using BEFORE-IMAGES stored in the WAL.

**Results Summary:**

* **Outcome:** All 5 tests passed successfully (Execution time: 0.086s).
* **Observation:** Multi-operation transactions accurately reversed in descending LSN order. Aborted inserts left zero traces, while aborted deletes and updates flawlessly restored their original states from the WAL.

---

## 2. Consistency Validation

**Technical Implementation:**

* **File:** `test_consistency.py`
* **Class:** `TestConsistency` (Inherits from `unittest.TestCase`)

**Objective:**
Validate that the database's primary state (the records dictionary) and the B+ Tree index remain perfectly aligned and synchronized across various operational states.

**Steps Used for Validation (Keeping Data Valid and Synced):**

* **Sync After Insert (`test_consistency_after_insert`):** Checked that immediately after adding a row, the main database and the B+ Tree index contain the exact same keys.
* **Sync After Commit (`test_consistency_after_commit`):** Confirmed that finalizing (committing) a transaction doesn't break the sync between the database and the index.
* **Sync After Rollback (`test_consistency_after_rollback`):** Verified that canceling an action doesn't accidentally leave ghost data in the index or the main database.
* **Sync After a Crash (`test_consistency_after_crash_simulation`):** Simulated a sudden system crash. Proved that when the system wakes back up and cleans itself, the main database and the B+ Tree index still match perfectly.

**Execution Flow:**
The flow focuses on executing state-altering commands (commits, rollbacks, and simulated crashes) and immediately following up with a **Consistency Check**. This check extracts all keys from the `records` dictionary and all mapped nodes from the `bplustree`, asserting that both sets are identical.

**Results Summary:**

* **Outcome:** All 4 tests passed successfully (Execution time: 0.035s).
* **Observation:** During the simulated crash scenario, the recovery engine successfully processed the WAL: it redone 1 committed transaction (`key=20`) and undone 1 incomplete transaction (`key=21`), leaving both data structures 100% in sync.

---

## 3. Durability Validation

**Technical Implementation:**

* **File:** `test_durability.py`
* **Class:** `TestDurability` (Inherits from `unittest.TestCase`)

**Objective:**
Verify that once a transaction receives a commit instruction, the data is permanently retained and survives application termination or abrupt hardware failure.

**Steps Used for Validation (Surviving System Shutdowns):**

* **Saved Data Stays Saved (`test_committed_data_survives_restart`):** Inserted data, completely shut down the database engine, and restarted it. Proved that the committed data was successfully recovered from the log file (WAL).
* **Half-Finished Data is Cleaned Up (`test_uncommitted_data_not_present_after_restart`):** Simulated a crash in the middle of a transaction. Proved that upon restart, the database smartly deletes the half-finished data but keeps all the older, fully saved data intact.

**Execution Flow:**
The durability tests utilize a two-session flow:

1. **Session 1:** Operations are executed and explicitly committed. The memory footprint (`DatabaseManager`) is then forcefully deleted without graceful shutdown, simulating a hard crash.
2. **Session 2:** A cold restart is initialized with `auto_recover=True`. The engine parses the existing WAL file and applies Redo/Undo logic before allowing verifications to run against the recovered state.

**Results Summary:**

* **Outcome:** All 2 tests passed successfully (Execution time: 0.027s).
* **Observation:** The recovery manager accurately detected completed versus partial transactions. Committed records (`key=100`, `key=101`, `key=1`) survived the simulated restart via REDO, while the uncommitted ghost row (`key=2`) was effectively erased via UNDO.

---

## 4. B+ Tree Index Consistency

**Technical Implementation:**

* **File:** `test_index_consistency.py`
* **Class:** `TestIndexConsistency` (Inherits from `unittest.TestCase`)

**Objective:**
Isolate and confirm that structural index modifications map 1-to-1 against raw storage modifications across all CRUD actions and transactional undo scenarios.

**Steps Used for Validation:**

* **Adding and Removing (`test_index_matches_records_after_insert`, `test_index_matches_records_after_delete`):** Proved that whenever a row is added or deleted in the main storage, the exact same change instantly happens in the B+ Tree.
* **Undoing Actions (`test_index_matches_records_after_failed_insert`, `test_index_matches_records_after_rollback_delete`):** Proved that if you change your mind and undo an insert or a delete, the B+ Tree correctly undoes its own changes so that the index never falls out of sync with the raw data.

**Execution Flow:**
Unlike the standard consistency tests, these tests track the state *before* and *after* specific node-level operations. The flow triggers an action (e.g., `_raw_delete` or `bplustree.delete()`) and runs comparative checks to ensure the B+ tree graph safely balances and mirrors the raw dictionary.

**Results Summary:**

* **Outcome:** All 4 tests passed successfully (Execution time: 0.090s).
* **Observation:** B+ tree node additions, removals, and rollbacks seamlessly synchronized with memory updates. Aborted operations completely restored both the index node pointers and the dictionary values without desynchronization.
