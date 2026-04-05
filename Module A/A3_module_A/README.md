#  Assignment 3 – Module A  
## Transaction Management & Crash Recovery Engine

###  Course
CS 432 – Databases  
Indian Institute of Technology Gandhinagar  

---

##  Overview

This project implements **Module A of Assignment 3**, focusing on building a reliable database engine with proper transaction handling and crash recovery.

The system ensures correctness of operations by implementing core **ACID properties**:

- **Atomicity** → Operations fully complete or fully rollback  
- **Consistency** → Database and B+ Tree always remain synchronized  
- **Durability** → Committed data persists even after crashes  

---

##  Features Implemented

### 1. Transaction Management
- Each operation is executed as a **transaction**
- Supports:
  - BEGIN transaction
  - COMMIT
  - ROLLBACK
- Prevents partial updates in case of failures

---

###  2. Write-Ahead Logging (WAL)

- All operations are logged **before execution**
- Log entries include:
  - Transaction ID
  - Operation type (INSERT / DELETE / UPDATE)
  - Before state (for undo)
  - After state (for redo)

This ensures:
- Safe rollback of incomplete transactions  
- Recovery after crashes  

---

###  3. Crash Recovery Mechanism

On system restart, recovery is performed using logs:

#### 🔹 Undo Phase
- Reverts all **uncommitted transactions**

#### 🔹 Redo Phase
- Reapplies all **committed transactions**

---

###  4. B+ Tree Indexing

- All records are indexed using a **B+ Tree**
- Every operation updates:
  - Main database  
  - B+ Tree index  

---

###  5. Database Consistency

The system guarantees:
- Database and B+ Tree are always consistent  

---

##  How to Run

```bash
pip install -r requirements.txt
python app.py
# run_tests
```

---

## 🏁 Conclusion

This project successfully implements a **robust transaction engine** ensuring ACID properties and reliable crash recovery.
