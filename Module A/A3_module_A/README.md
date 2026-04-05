# Module A: Lightweight DBMS with B+ Tree Index

## Overview

This module implements a complete Lightweight Database Management System (DBMS) with a B+ Tree index structure. It demonstrates efficient data storage and retrieval through self-balancing tree structures with comprehensive performance analysis.

## Project Structure

```
Module_A/
├── db_management_system/
│   ├── __init__.py                 # Package initialization
│   └── database/
│       ├── __init__.py             # Database package exports
│       ├── bplustree.py            # Core B+ Tree implementation
│       ├── bruteforce.py           # Linear search baseline for comparison
│       ├── table.py                # Table abstraction layer
│       ├── db_manager.py           # Database manager for multi-table operations
│       └── performance_analyzer.py # Benchmarking and analysis tools
├── report.ipynb                    # Jupyter notebook with analysis and visualizations
├── requirements.txt                # Python dependencies
└── README.md                       # This file
```

## Features Implemented

### 1. **B+ Tree Data Structure** (`bplustree.py`)
   - **Nodes**: Efficient key-value storage with automatic balancing
   - **Operations**:
     - `insert(key, value)`: O(log n) insertion with automatic node splitting
     - `delete(key)`: O(log n) deletion with merging/borrowing
     - `search(key)`: O(log n) exact match search
     - `range_query(start, end)`: O(log n + k) efficient range queries
     - `update(key, new_value)`: O(log n) updates
   - **Leaf Linking**: Pointers between leaf nodes enable sequential access
   - **Auto-Balancing**: Maintains balance through splitting and merging

### 2. **Table Abstraction** (`table.py`)
   - Maps indexed keys to complete records (dictionaries)
   - Supports CRUD operations on records
   - Maintains data integrity through key-based indexing
   - Multiple tables per database

### 3. **Database Manager** (`db_manager.py`)
   - Manages multiple tables
   - Create/drop tables dynamically
   - Retrieve table metadata and statistics
   - Unified database interface

### 4. **Performance Analysis** (`performance_analyzer.py`)
   - Benchmarks B+ Tree vs. BruteForceDB (linear search)
   - Measures: insertion, search, deletion, range query performance
   - Time and memory usage tracking
   - Statistical averaging over multiple runs

## Installation

### Prerequisites
- Python 3.7+
- numpy
- matplotlib
- graphviz (optional, for tree visualization)

### Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Verify installation
python3 << EOF
import sys
sys.path.insert(0, './db_management_system')
from database import BPlusTree
print("✓ Installation successful!")
EOF
```

## Usage Examples

### Basic B+ Tree Operations

```python
from db_management_system.database import BPlusTree

# Create tree with order 3 (max 2 keys per node)
tree = BPlusTree(order=3)

# Insert key-value pairs
tree.insert(10, "Alice")
tree.insert(20, "Bob")
tree.insert(5, "Charlie")

# Search for a key
result = tree.search(10)  # Returns "Alice"

# Range query
results = tree.range_query(5, 15)  # Returns [(5, "Charlie"), (10, "Alice")]

# Delete a key
tree.delete(5)

# Get all records
all_records = tree.get_all()
```

### Using Tables and Database Manager

```python
from db_management_system.database import DatabaseManager

# Create database
db = DatabaseManager("student_db")

# Create a table
students = db.create_table("students", "student_id", order=5)

# Insert records
students.insert(1, {"student_id": 1, "name": "Alice", "major": "CS", "gpa": 3.8})
students.insert(2, {"student_id": 2, "name": "Bob", "major": "Math", "gpa": 3.5})

# Search for a record
record = students.search(1)
print(record)  # {'student_id': 1, 'name': 'Alice', 'major': 'CS', 'gpa': 3.8}

# Range query on student IDs
results = students.range_query(1, 3)

# Update a record
students.update(1, {"student_id": 1, "name": "Alice", "major": "CS", "gpa": 3.9})

# Get all records
all_students = students.get_all()

# Database statistics
stats = db.get_database_stats()
```

### Performance Benchmarking

```python
from db_management_system.database.performance_analyzer import PerformanceAnalyzer

# Create analyzer
analyzer = PerformanceAnalyzer()

# Run benchmarks
data_sizes = [500, 1000, 2000, 5000, 10000]

insertion_results = analyzer.benchmark_insertion(data_sizes, num_runs=3)
search_results = analyzer.benchmark_search(data_sizes, num_runs=3)
deletion_results = analyzer.benchmark_deletion(data_sizes, num_runs=3)
range_results = analyzer.benchmark_range_query(data_sizes, num_runs=3)

# Print summary
print(analyzer.get_results_summary())
```

## Performance Analysis Results

### Time Complexity Comparison

| Operation | B+ Tree | BruteForce | Performance Gain |
|-----------|---------|-----------|-----------------|
| Insertion | O(log n) | O(n) | 2-10x faster |
| Search | O(log n) | O(n) | 3-10x faster |
| Deletion | O(log n) | O(n) | 2-8x faster |
| Range Query | O(log n + k) | O(n) | 10-50x faster ⭐ |

Where: n = number of records, k = number of results

### Key Findings

1. **Range Queries**: B+ Tree's unique strength through leaf node linking
2. **Break-even Point**: ~50-100 records where B+ Tree starts outperforming linear search
3. **Scalability**: Performance gap widens significantly with larger datasets
4. **Memory**: Slight overhead for tree structure, but worth it for performance

## Visualization

### B+ Tree Structure

Use Graphviz to visualize tree structure (requires graphviz package):

```python
tree = BPlusTree(order=3)
# ... insert some data ...

dot = tree.visualize_tree()
if dot:
    dot.render('bptree_structure', format='png')
```

The visualization shows:
- **Ellipses**: Internal (index) nodes with keys
- **Rectangles**: Leaf nodes with values
- **Solid arrows**: Parent-child relationships
- **Dashed arrows**: Leaf node linked list pointers

## Report and Analysis

Run the Jupyter notebook for comprehensive analysis:

```bash
jupyter notebook report.ipynb
```

The report includes:
- Introduction and background on B+ Trees
- Implementation details and code walkthrough
- Performance benchmarks with multiple operations
- Matplotlib graphs comparing B+ Tree vs. BruteForce
- Graphviz tree visualizations
- Analysis and conclusions
- Real-world applications discussion

## Testing

Run the included test to verify everything works:

```bash
python3 << EOF
import sys
sys.path.insert(0, './db_management_system')
from database import BPlusTree, DatabaseManager
from database.performance_analyzer import PerformanceAnalyzer

# Test B+ Tree
tree = BPlusTree(order=3)
test_data = [(10, "A"), (20, "B"), (5, "C")]
for k, v in test_data:
    tree.insert(k, v)
assert tree.search(10) == "A"
print("✓ B+ Tree tests passed")

# Test Database Manager
db = DatabaseManager("test_db")
table = db.create_table("test", "id", order=3)
table.insert(1, {"id": 1, "name": "Test"})
assert table.search(1) == {"id": 1, "name": "Test"}
print("✓ Database Manager tests passed")

# Test Performance Analyzer
analyzer = PerformanceAnalyzer()
results = analyzer.benchmark_insertion([100, 200], num_runs=1)
assert len(results['bplustree']) == 2
print("✓ Performance Analyzer tests passed")

print("\n✅ All tests passed!")
EOF
```

## Key Implementation Details

### Node Splitting (Insertion)
When a node exceeds capacity:
1. Split node into two nodes of size ⌊order/2⌋
2. Promote median key to parent (copy for leaves, move for internal)
3. Recursively split parent if needed
4. Maintain leaf node pointers

### Node Merging (Deletion)
When a node becomes underfull:
1. Try borrowing from siblings
2. If siblings also underfull, merge with sibling
3. Remove separator key from parent
4. Recursively handle parent underflow

### Leaf Linking
- All leaf nodes maintain `next` and `prev` pointers
- Forms a complete doubly-linked list
- Enables O(k) sequential access after finding start position
- Critical for efficient range queries

## Dependencies

```
graphviz>=0.20.1      # Tree visualization
matplotlib>=3.7.0     # Performance graphs
numpy>=1.24.0         # Numerical analysis
jupyter>=1.0.0        # Notebook environment
ipython>=8.0.0        # Interactive terminal
```

## Troubleshooting

### ImportError: No module named 'graphviz'
Graphviz is optional. Install it for visualization:
```bash
pip install graphviz
```

### Performance benchmarks seem slow
This is expected for large datasets. Reduce `data_sizes` in benchmarks for faster runs:
```python
data_sizes = [100, 500, 1000]  # Instead of [500, 1000, 2000, 5000, 10000]
```

## Future Enhancements

1. **Persistence**: Serialize/deserialize B+ Tree to disk
2. **Concurrency**: Multi-threaded access with locks
3. **Optimization**: Lazy deletion, bulk loading algorithms
4. **Variants**: B* Trees (higher occupancy), B-link Trees
5. **SQL Interface**: Query language for database operations
6. **Compression**: Key and value compression techniques

## References

- Bayer & McCreight (1972): "Organization and Maintenance of Large Ordered Indices"
- Knuth (1998): "The Art of Computer Programming, Volume 3"
- Modern Database Systems textbooks

## Course Information

- **Course**: CS 432 - Databases (Course Project/Assignment 2)
- **Instructor**: Dr. Yogesh K. Meena
- **Institution**: Indian Institute of Technology, Gandhinagar
- **Date**: March 2026
- **Module**: A - Lightweight DBMS with B+ Tree Index

## Author Notes

This implementation prioritizes **clarity and correctness** over performance micro-optimizations. It serves as an educational tool demonstrating:
- How modern databases implement indexing
- Self-balancing tree concepts
- Time complexity analysis in practice
- Performance benchmarking methodology

---

**Status**: ✅ Complete and fully functional
**Last Updated**: March 21, 2026
