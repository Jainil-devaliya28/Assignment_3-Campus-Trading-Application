"""
B+ Tree Implementation
A self-balancing tree structure optimized for database indexing.
Supports insertion, deletion, search, and range queries with automatic node splitting/merging.
"""

from collections import defaultdict
from typing import List, Tuple, Optional, Any, Dict


class BPlusTreeNode:
    """Represents a node in the B+ Tree."""
    
    def __init__(self, leaf=False, order=3):
        """
        Initialize a B+ Tree node.
        
        Args:
            leaf: True if this is a leaf node
            order: Maximum number of children (and max keys = order - 1)
        """
        self.keys = []
        self.values = []  # For leaf nodes: actual data; for internal nodes: child pointers
        self.children = []  # Child pointers for internal nodes
        self.next = None  # For leaf nodes: pointer to next leaf (for range queries)
        self.prev = None  # For leaf nodes: pointer to previous leaf
        self.leaf = leaf
        self.order = order
        self.parent = None
    
    def is_full(self):
        """Check if node has maximum number of keys."""
        return len(self.keys) >= self.order - 1
    
    def is_underfull(self):
        """Check if node has fewer than minimum keys."""
        min_keys = (self.order - 1) // 2
        return len(self.keys) < min_keys


class BPlusTree:
    """B+ Tree data structure for efficient indexing."""
    
    def __init__(self, order=3):
        """
        Initialize B+ Tree.
        
        Args:
            order: Maximum number of children per node (default 3)
        """
        self.root = BPlusTreeNode(leaf=True, order=order)
        self.order = order
        self.first_leaf = self.root  # Track first leaf for range queries
    
    def search(self, key):
        """
        Search for a key in the B+ tree.
        
        Args:
            key: Key to search for
            
        Returns:
            Associated value if found, else None
        """
        node = self._find_leaf(key)
        if node is None:
            return None
        
        try:
            index = node.keys.index(key)
            return node.values[index]
        except ValueError:
            return None
    
    def _find_leaf(self, key):
        """Find the leaf node that should contain the key."""
        node = self.root
        while not node.leaf:
            for i, k in enumerate(node.keys):
                if key < k:
                    node = node.children[i]
                    break
            else:
                node = node.children[-1]
        return node
    
    def insert(self, key, value):
        """
        Insert a key-value pair into the B+ tree.
        
        Args:
            key: Key to insert
            value: Associated value/data
        """
        if self.root.is_full():
            old_root = self.root
            self.root = BPlusTreeNode(leaf=False, order=self.order)
            self.root.children.append(old_root)
            old_root.parent = self.root
            self._split_child(self.root, 0)
        
        self._insert_non_full(self.root, key, value)
    
    def _insert_non_full(self, node, key, value):
        """Recursively insert into a non-full node."""
        if node.leaf:
            # Insert into leaf node
            insert_idx = 0
            for i, k in enumerate(node.keys):
                if key < k:
                    insert_idx = i
                    break
                elif key == k:
                    # Update existing key
                    node.values[i] = value
                    return
                insert_idx = i + 1
            
            node.keys.insert(insert_idx, key)
            node.values.insert(insert_idx, value)
        else:
            # Find child to insert into
            child_idx = 0
            for i, k in enumerate(node.keys):
                if key < k:
                    child_idx = i
                    break
                child_idx = i + 1
            
            child = node.children[child_idx]
            
            if child.is_full():
                self._split_child(node, child_idx)
                if key > node.keys[child_idx]:
                    child_idx += 1
            
            self._insert_non_full(node.children[child_idx], key, value)
    
    def _split_child(self, parent, child_idx):
        """Split a full child node."""
        full_child = parent.children[child_idx]
        mid_point = (self.order - 1) // 2
        
        # Create new node
        new_node = BPlusTreeNode(leaf=full_child.leaf, order=self.order)
        new_node.parent = parent
        
        if full_child.leaf:
            # Split leaf: copy median key to parent
            new_node.keys = full_child.keys[mid_point:]
            new_node.values = full_child.values[mid_point:]
            
            full_child.keys = full_child.keys[:mid_point]
            full_child.values = full_child.values[:mid_point]
            
            # Update leaf linkage
            new_node.next = full_child.next
            new_node.prev = full_child
            if full_child.next:
                full_child.next.prev = new_node
            full_child.next = new_node
            
            # Promote first key of new node
            parent.keys.insert(child_idx, new_node.keys[0])
            parent.children.insert(child_idx + 1, new_node)
        else:
            # Split internal node: promote median key
            new_node.keys = full_child.keys[mid_point + 1:]
            new_node.children = full_child.children[mid_point + 1:]
            
            for child in new_node.children:
                child.parent = new_node
            
            median_key = full_child.keys[mid_point]
            full_child.keys = full_child.keys[:mid_point]
            full_child.children = full_child.children[:mid_point + 1]
            
            parent.keys.insert(child_idx, median_key)
            parent.children.insert(child_idx + 1, new_node)
    
    def delete(self, key):
        """
        Delete a key from the B+ tree.
        
        Args:
            key: Key to delete
            
        Returns:
            True if deletion succeeded, False otherwise
        """
        self._delete(self.root, key)
        
        # Update root if it's empty
        if not self.root.leaf and len(self.root.keys) == 0:
            if self.root.children:
                self.root = self.root.children[0]
                self.root.parent = None
        
        return True
    
    def _delete(self, node, key):
        """Recursive helper for deletion."""
        if node.leaf:
            # Delete from leaf
            try:
                idx = node.keys.index(key)
                node.keys.pop(idx)
                node.values.pop(idx)
            except ValueError:
                return False
        else:
            # Find child that should contain key
            child_idx = 0
            for i, k in enumerate(node.keys):
                if key < k:
                    child_idx = i
                    break
                child_idx = i + 1
            
            # Ensure child has enough keys before deletion
            if child_idx < len(node.children):
                child = node.children[child_idx]
                if len(child.keys) <= (self.order - 1) // 2:
                    self._fill_child(node, child_idx)
                    # Recompute child index after fill operation
                    child_idx = 0
                    for i, k in enumerate(node.keys):
                        if key < k:
                            child_idx = i
                            break
                        child_idx = i + 1
            
            # Ensure child_idx is within valid range
            if child_idx < len(node.children):
                self._delete(node.children[child_idx], key)
    
    def _fill_child(self, node, idx):
        """Ensure child at index has enough keys."""
        min_keys = (self.order - 1) // 2
        
        # If prev sibling has extra keys, borrow
        if idx > 0 and len(node.children[idx - 1].keys) > min_keys:
            self._borrow_from_prev(node, idx)
        # If next sibling has extra keys, borrow
        elif idx < len(node.children) - 1 and len(node.children[idx + 1].keys) > min_keys:
            self._borrow_from_next(node, idx)
        # Merge with sibling
        else:
            if idx < len(node.children) - 1:
                self._merge(node, idx)
            else:
                self._merge(node, idx - 1)
    
    def _borrow_from_prev(self, parent, child_idx):
        """Borrow a key from left sibling."""
        child = parent.children[child_idx]
        sibling = parent.children[child_idx - 1]
        
        if child.leaf:
            # Move key from sibling through parent to child
            child.keys.insert(0, sibling.keys.pop())
            child.values.insert(0, sibling.values.pop())
            parent.keys[child_idx - 1] = child.keys[0]
        else:
            # For internal nodes
            child.keys.insert(0, parent.keys[child_idx - 1])
            parent.keys[child_idx - 1] = sibling.keys.pop()
            child.children.insert(0, sibling.children.pop())
            child.children[0].parent = child
    
    def _borrow_from_next(self, parent, child_idx):
        """Borrow a key from right sibling."""
        child = parent.children[child_idx]
        sibling = parent.children[child_idx + 1]
        
        if child.leaf:
            child.keys.append(sibling.keys.pop(0))
            child.values.append(sibling.values.pop(0))
            parent.keys[child_idx] = sibling.keys[0]
        else:
            child.keys.append(parent.keys[child_idx])
            parent.keys[child_idx] = sibling.keys.pop(0)
            child.children.append(sibling.children.pop(0))
            child.children[-1].parent = child
    
    def _merge(self, parent, idx):
        """Merge child with its right sibling."""
        child = parent.children[idx]
        sibling = parent.children[idx + 1]
        
        if child.leaf:
            child.keys.extend(sibling.keys)
            child.values.extend(sibling.values)
            child.next = sibling.next
            if sibling.next:
                sibling.next.prev = child
        else:
            child.keys.append(parent.keys.pop(idx))
            child.keys.extend(sibling.keys)
            child.children.extend(sibling.children)
            for grandchild in sibling.children:
                grandchild.parent = child
        
        parent.children.pop(idx + 1)
    
    def update(self, key, new_value):
        """
        Update value associated with an existing key.
        
        Args:
            key: Key to update
            new_value: New value
            
        Returns:
            True if successful, False if key not found
        """
        node = self._find_leaf(key)
        if node is None:
            return False
        
        try:
            idx = node.keys.index(key)
            node.values[idx] = new_value
            return True
        except ValueError:
            return False
    
    def range_query(self, start_key, end_key):
        """
        Return all key-value pairs where start_key <= key <= end_key.
        Efficiently traverses leaf nodes using linked list pointers.
        
        Args:
            start_key: Start of range (inclusive)
            end_key: End of range (inclusive)
            
        Returns:
            List of (key, value) tuples in range
        """
        result = []
        
        # Find leaf containing start_key
        node = self._find_leaf(start_key)
        
        # Traverse leaf nodes using next pointers
        while node:
            for i, key in enumerate(node.keys):
                if key >= start_key and key <= end_key:
                    result.append((key, node.values[i]))
                elif key > end_key:
                    return result
            
            node = node.next
        
        return result
    
    def get_all(self):
        """
        Return all key-value pairs in the tree using in-order traversal.
        
        Returns:
            List of (key, value) tuples
        """
        result = []
        node = self.first_leaf
        
        while node:
            for i, key in enumerate(node.keys):
                result.append((key, node.values[i]))
            node = node.next
        
        return sorted(result, key=lambda x: x[0])
    
    def visualize_tree(self):
        """
        Generate Graphviz representation of the B+ tree structure.
        
        Returns:
            Graphviz Digraph object
        """
        try:
            import graphviz
        except ImportError:
            return None
        
        dot = graphviz.Digraph(comment='B+ Tree', format='png')
        dot.attr(rankdir='TB')
        dot.attr('node', shape='box', style='rounded')
        
        self._add_nodes(dot, self.root)
        self._add_edges(dot, self.root)
        
        return dot
    
    def _add_nodes(self, dot, node, node_id=None):
        """Recursively add nodes to Graphviz object."""
        if node_id is None:
            node_id = id(node)
        
        if node.leaf:
            label = '|'.join(str(k) for k in node.keys)
            dot.node(str(node_id), label=label, shape='box')
        else:
            label = '|'.join(str(k) for k in node.keys)
            dot.node(str(node_id), label=label, shape='ellipse')
            
            for child in node.children:
                self._add_nodes(dot, child)
    
    def _add_edges(self, dot, node):
        """Add edges between nodes and dashed lines for leaf connections."""
        node_id = id(node)
        
        if not node.leaf:
            for i, child in enumerate(node.children):
                child_id = id(child)
                dot.edge(str(node_id), str(child_id))
                self._add_edges(dot, child)
        else:
            # Add dashed edges for leaf linkage
            if node.next:
                dot.edge(str(node_id), str(id(node.next)), style='dashed', label='next')
    
    def __str__(self):
        """String representation of tree structure."""
        return self._node_repr(self.root, "")
    
    def _node_repr(self, node, prefix=""):
        """Recursive string representation."""
        result = prefix + f"Keys: {node.keys}\n"
        
        if not node.leaf:
            for i, child in enumerate(node.children):
                result += self._node_repr(child, prefix + "  ")
        else:
            result += prefix + f"Values: {node.values}\n"
        
        return result
