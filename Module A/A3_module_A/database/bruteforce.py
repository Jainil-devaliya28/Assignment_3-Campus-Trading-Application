"""
BruteForceDB - Baseline comparison for B+ Tree performance.
Uses a simple list-based approach with linear search.
"""

from typing import List, Tuple, Any, Optional


class BruteForceDB:
    """Simple list-based database for comparison with B+ Tree."""
    
    def __init__(self):
        """Initialize with empty data list."""
        self.data = []
    
    def insert(self, key: int, value: Any) -> None:
        """
        Insert a key-value pair.
        
        Args:
            key: Key to insert
            value: Associated value
        """
        # Check if key already exists
        for i, (k, v) in enumerate(self.data):
            if k == key:
                self.data[i] = (key, value)
                return
        
        self.data.append((key, value))
    
    def search(self, key: int) -> Optional[Any]:
        """
        Search for a key.
        
        Args:
            key: Key to search for
            
        Returns:
            Associated value if found, else None
        """
        for k, v in self.data:
            if k == key:
                return v
        return None
    
    def delete(self, key: int) -> bool:
        """
        Delete a key from the database.
        
        Args:
            key: Key to delete
            
        Returns:
            True if deletion succeeded, False otherwise
        """
        for i, (k, v) in enumerate(self.data):
            if k == key:
                self.data.pop(i)
                return True
        return False
    
    def range_query(self, start: int, end: int) -> List[Tuple[int, Any]]:
        """
        Retrieve all key-value pairs within range.
        
        Args:
            start: Start of range (inclusive)
            end: End of range (inclusive)
            
        Returns:
            List of (key, value) tuples in range
        """
        return [(k, v) for k, v in self.data if start <= k <= end]
    
    def update(self, key: int, new_value: Any) -> bool:
        """
        Update value associated with a key.
        
        Args:
            key: Key to update
            new_value: New value
            
        Returns:
            True if successful, False if key not found
        """
        for i, (k, v) in enumerate(self.data):
            if k == key:
                self.data[i] = (key, new_value)
                return True
        return False
    
    def get_all(self) -> List[Tuple[int, Any]]:
        """
        Get all key-value pairs in sorted order.
        
        Returns:
            Sorted list of all (key, value) tuples
        """
        return sorted(self.data, key=lambda x: x[0])
