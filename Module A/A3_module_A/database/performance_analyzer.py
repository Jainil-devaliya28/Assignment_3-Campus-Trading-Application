"""
Performance Analysis module - Benchmarking B+ Tree vs BruteForce approach.
"""

import time
import sys
import random
from typing import List, Tuple, Dict, Any
from .bplustree import BPlusTree
from .bruteforce import BruteForceDB


class PerformanceAnalyzer:
    """Analyzes performance of B+ Tree vs BruteForceDB."""
    
    def __init__(self):
        """Initialize the performance analyzer."""
        self.results = {}
    
    def benchmark_insertion(self, data_sizes: List[int], num_runs: int = 3) -> Dict[str, Any]:
        """
        Benchmark insertion performance.
        
        Args:
            data_sizes: List of dataset sizes to test
            num_runs: Number of runs per size (for averaging)
            
        Returns:
            Dictionary with results
        """
        results = {
            'bplustree': [],
            'bruteforce': [],
            'sizes': data_sizes
        }
        
        for size in data_sizes:
            bptree_times = []
            brute_times = []
            
            for _ in range(num_runs):
                # Generate random data
                data = [(random.randint(1, 1000000), f"value_{i}") for i in range(size)]
                
                # B+ Tree insertion
                bptree = BPlusTree(order=5)
                start = time.time()
                for key, val in data:
                    bptree.insert(key, val)
                bptree_times.append(time.time() - start)
                
                # BruteForce insertion
                brute = BruteForceDB()
                start = time.time()
                for key, val in data:
                    brute.insert(key, val)
                brute_times.append(time.time() - start)
            
            # Average results
            results['bplustree'].append(sum(bptree_times) / len(bptree_times))
            results['bruteforce'].append(sum(brute_times) / len(brute_times))
        
        self.results['insertion'] = results
        return results
    
    def benchmark_search(self, data_sizes: List[int], num_runs: int = 3) -> Dict[str, Any]:
        """
        Benchmark search performance.
        
        Args:
            data_sizes: List of dataset sizes to test
            num_runs: Number of runs per size
            
        Returns:
            Dictionary with results
        """
        results = {
            'bplustree': [],
            'bruteforce': [],
            'sizes': data_sizes
        }
        
        for size in data_sizes:
            bptree_times = []
            brute_times = []
            
            for _ in range(num_runs):
                # Generate random data
                data = [(random.randint(1, 1000000), f"value_{i}") for i in range(size)]
                queries = [random.randint(1, 1000000) for _ in range(min(100, size // 10))]
                
                # B+ Tree
                bptree = BPlusTree(order=5)
                for key, val in data:
                    bptree.insert(key, val)
                
                start = time.time()
                for query_key in queries:
                    bptree.search(query_key)
                bptree_times.append(time.time() - start)
                
                # BruteForce
                brute = BruteForceDB()
                for key, val in data:
                    brute.insert(key, val)
                
                start = time.time()
                for query_key in queries:
                    brute.search(query_key)
                brute_times.append(time.time() - start)
            
            results['bplustree'].append(sum(bptree_times) / len(bptree_times))
            results['bruteforce'].append(sum(brute_times) / len(brute_times))
        
        self.results['search'] = results
        return results
    
    def benchmark_deletion(self, data_sizes: List[int], num_runs: int = 3) -> Dict[str, Any]:
        """
        Benchmark deletion performance.
        
        Args:
            data_sizes: List of dataset sizes to test
            num_runs: Number of runs per size
            
        Returns:
            Dictionary with results
        """
        results = {
            'bplustree': [],
            'bruteforce': [],
            'sizes': data_sizes
        }
        
        for size in data_sizes:
            bptree_times = []
            brute_times = []
            
            for _ in range(num_runs):
                # Generate random data
                data = [(random.randint(1, 1000000), f"value_{i}") for i in range(size)]
                delete_keys = [k for k, _ in data[:min(50, size // 10)]]
                
                # B+ Tree
                bptree = BPlusTree(order=5)
                for key, val in data:
                    bptree.insert(key, val)
                
                start = time.time()
                for key in delete_keys:
                    bptree.delete(key)
                bptree_times.append(time.time() - start)
                
                # BruteForce
                brute = BruteForceDB()
                for key, val in data:
                    brute.insert(key, val)
                
                start = time.time()
                for key in delete_keys:
                    brute.delete(key)
                brute_times.append(time.time() - start)
            
            results['bplustree'].append(sum(bptree_times) / len(bptree_times))
            results['bruteforce'].append(sum(brute_times) / len(brute_times))
        
        self.results['deletion'] = results
        return results
    
    def benchmark_range_query(self, data_sizes: List[int], num_runs: int = 3) -> Dict[str, Any]:
        """
        Benchmark range query performance.
        
        Args:
            data_sizes: List of dataset sizes to test
            num_runs: Number of runs per size
            
        Returns:
            Dictionary with results
        """
        results = {
            'bplustree': [],
            'bruteforce': [],
            'sizes': data_sizes
        }
        
        for size in data_sizes:
            bptree_times = []
            brute_times = []
            
            for _ in range(num_runs):
                # Generate random data
                data = [(random.randint(1, 100000), f"value_{i}") for i in range(size)]
                
                # Random range queries
                queries = []
                for _ in range(min(50, size // 10)):
                    start = random.randint(1, 50000)
                    end = random.randint(start, 100000)
                    queries.append((start, end))
                
                # B+ Tree
                bptree = BPlusTree(order=5)
                for key, val in data:
                    bptree.insert(key, val)
                
                start = time.time()
                for s, e in queries:
                    bptree.range_query(s, e)
                bptree_times.append(time.time() - start)
                
                # BruteForce
                brute = BruteForceDB()
                for key, val in data:
                    brute.insert(key, val)
                
                start = time.time()
                for s, e in queries:
                    brute.range_query(s, e)
                brute_times.append(time.time() - start)
            
            results['bplustree'].append(sum(bptree_times) / len(bptree_times))
            results['bruteforce'].append(sum(brute_times) / len(brute_times))
        
        self.results['range_query'] = results
        return results
    
    def benchmark_memory(self, data_sizes: List[int]) -> Dict[str, Any]:
        """
        Estimate memory usage.
        
        Args:
            data_sizes: List of dataset sizes to test
            
        Returns:
            Dictionary with memory estimates
        """
        results = {
            'bplustree': [],
            'bruteforce': [],
            'sizes': data_sizes
        }
        
        for size in data_sizes:
            data = [(random.randint(1, 1000000), f"value_{i}") for i in range(size)]
            
            # B+ Tree
            bptree = BPlusTree(order=5)
            for key, val in data:
                bptree.insert(key, val)
            bptree_size = sys.getsizeof(bptree)
            
            # BruteForce
            brute = BruteForceDB()
            for key, val in data:
                brute.insert(key, val)
            brute_size = sys.getsizeof(brute)
            
            results['bplustree'].append(bptree_size)
            results['bruteforce'].append(brute_size)
        
        self.results['memory'] = results
        return results
    
    def get_results_summary(self) -> str:
        """Get a text summary of all results."""
        summary = "Performance Analysis Summary\n"
        summary += "=" * 50 + "\n\n"
        
        for test_name, test_results in self.results.items():
            summary += f"{test_name.upper()}\n"
            summary += "-" * 50 + "\n"
            
            if 'sizes' in test_results:
                sizes = test_results['sizes']
                bptree = test_results.get('bplustree', [])
                brute = test_results.get('bruteforce', [])
                
                for i, size in enumerate(sizes):
                    if i < len(bptree) and i < len(brute):
                        bp_val = bptree[i]
                        br_val = brute[i]
                        ratio = (br_val / bp_val) if bp_val > 0 else 0
                        summary += f"Size {size:6d}: BPTree={bp_val:10.6f}s, Brute={br_val:10.6f}s, Speedup={ratio:.2f}x\n"
            
            summary += "\n"
        
        return summary
