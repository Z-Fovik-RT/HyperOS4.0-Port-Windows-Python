"""Transaction and rollback system for modifier plugins.

This module provides transaction-like semantics for plugin execution:
- Pre-modification backups
- Rollback on failure
- Transaction context managers
- Modification tracking
"""
import logging
import shutil
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ModificationRecord:
    """Record of a single file modification."""
    original_path: Path
    backup_path: Optional[Path]
    action: str  # 'modify', 'delete', 'create'
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Transaction:
    """Represents a transactional operation."""
    name: str
    start_time: datetime = field(default_factory=datetime.now)
    modifications: List[ModificationRecord] = field(default_factory=list)
    completed: bool = False
    rolled_back: bool = False
    
    def add_modification(self, mod: ModificationRecord):
        """Add a modification record."""
        self.modifications.append(mod)
    
    def rollback(self, logger: logging.Logger) -> int:
        """Rollback all modifications in this transaction.
        
        Returns:
            int: Number of files rolled back
        """
        if self.rolled_back:
            logger.warning(f"Transaction '{self.name}' already rolled back")
            return 0
        
        rolled_back = 0
        for mod in reversed(self.modifications):
            try:
                if mod.action == 'modify' and mod.backup_path and mod.backup_path.exists():
                    # Restore from backup
                    if mod.original_path.exists():
                        if mod.original_path.is_dir():
                            shutil.rmtree(mod.original_path)
                        else:
                            mod.original_path.unlink()
                    shutil.copy2(mod.backup_path, mod.original_path)
                    rolled_back += 1
                    logger.debug(f"Rolled back: {mod.original_path}")
                    
                elif mod.action == 'delete':
                    # Restore deleted file from backup
                    if mod.backup_path and mod.backup_path.exists():
                        shutil.copy2(mod.backup_path, mod.original_path)
                        rolled_back += 1
                        logger.debug(f"Restored deleted: {mod.original_path}")
                        
                elif mod.action == 'create':
                    # Remove created file/directory
                    if mod.original_path.exists():
                        if mod.original_path.is_dir():
                            shutil.rmtree(mod.original_path)
                        else:
                            mod.original_path.unlink()
                        rolled_back += 1
                        logger.debug(f"Removed created: {mod.original_path}")
                        
            except Exception as e:
                logger.error(f"Failed to rollback {mod.original_path}: {e}")
        
        self.rolled_back = True
        return rolled_back


class TransactionManager:
    """Manages transactions and rollbacks for modifier operations."""
    
    def __init__(self, backup_dir: Optional[Path] = None):
        # Default backup directory
        self.backup_dir = backup_dir or Path("temp/backups")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        self._transactions: List[Transaction] = []
        self._current_transaction: Optional[Transaction] = None
        self.logger = logging.getLogger("TransactionManager")
    
    @contextmanager
    def transaction(self, name: str):
        """Context manager for transactional operations.
        
        Usage:
            with manager.transaction("my_operation"):
                # Do modifications
                pass
            # If exception, auto-rollback
        """
        txn = Transaction(name=name)
        self._transactions.append(txn)
        self._current_transaction = txn
        
        try:
            yield txn
            txn.completed = True
            self.logger.info(f"Transaction '{name}' completed successfully")
        except Exception as e:
            self.logger.error(f"Transaction '{name}' failed: {e}")
            self.rollback(name)
            raise
        finally:
            self._current_transaction = None
    
    def record_modification(self, path: Path, action: str, create_backup: bool = True) -> Optional[Path]:
        """Record a file modification for potential rollback.
        
        Args:
            path: Path to the file being modified
            action: 'modify', 'delete', or 'create'
            create_backup: Whether to create a backup
            
        Returns:
            Path to backup file if created, None otherwise
        """
        if not self._current_transaction:
            self.logger.debug(f"No active transaction, skipping backup for {path}")
            return None
        
        backup_path = None
        
        # Create backup for modify/delete actions
        if create_backup and action in ('modify', 'delete') and path.exists():
            # Generate unique backup name
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = f"{path.name}_{timestamp}"
            backup_path = self.backup_dir / safe_name
            
            try:
                if path.is_dir():
                    shutil.copytree(path, backup_path, symlinks=True)
                else:
                    shutil.copy2(path, backup_path)
                self.logger.debug(f"Created backup: {backup_path}")
            except Exception as e:
                self.logger.warning(f"Failed to create backup for {path}: {e}")
                backup_path = None
        
        # Record the modification
        mod = ModificationRecord(
            original_path=path,
            backup_path=backup_path,
            action=action
        )
        self._current_transaction.add_modification(mod)
        
        return backup_path
    
    def rollback(self, transaction_name: str) -> int:
        """Rollback a specific transaction by name.
        
        Args:
            transaction_name: Name of the transaction to rollback
            
        Returns:
            int: Number of files rolled back
        """
        for txn in reversed(self._transactions):
            if txn.name == transaction_name:
                return txn.rollback(self.logger)
        
        self.logger.warning(f"Transaction '{transaction_name}' not found")
        return 0
    
    def rollback_all(self) -> int:
        """Rollback all transactions.
        
        Returns:
            int: Total files rolled back
        """
        total = 0
        for txn in reversed(self._transactions):
            if not txn.rolled_back and txn.completed is False:
                total += txn.rollback(self.logger)
        return total
    
    def commit(self, transaction_name: str):
        """Commit a transaction, clearing its rollback info.
        
        Args:
            transaction_name: Name of the transaction to commit
        """
        for txn in self._transactions:
            if txn.name == transaction_name:
                # Clean up backups
                for mod in txn.modifications:
                    if mod.backup_path and mod.backup_path.exists():
                        try:
                            mod.backup_path.unlink()
                        except:
                            pass
                txn.completed = True
                self.logger.info(f"Transaction '{transaction_name}' committed")
                break
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of all transactions.
        
        Returns:
            Dict with transaction information
        """
        return {
            'total_transactions': len(self._transactions),
            'active': self._current_transaction.name if self._current_transaction else None,
            'transactions': [
                {
                    'name': t.name,
                    'completed': t.completed,
                    'rolled_back': t.rolled_back,
                    'modifications': len(t.modifications)
                }
                for t in self._transactions
            ]
        }
    
    def cleanup(self):
        """Clean up backup directory."""
        if self.backup_dir.exists():
            try:
                shutil.rmtree(self.backup_dir)
                self.backup_dir.mkdir(parents=True, exist_ok=True)
                self.logger.info("Cleaned up backup directory")
            except Exception as e:
                self.logger.warning(f"Failed to cleanup backup directory: {e}")


# Helper functions for easy integration

def track_modification(manager: TransactionManager, path: Path, action: str):
    """Decorator/helper to track file modifications.
    
    Usage:
        @track_modification(manager, path, 'modify')
        def modify_file(path):
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            manager.record_modification(path, action)
            return func(*args, **kwargs)
        return wrapper
    return decorator


class RollbackContext:
    """Context manager for rollback on exception.
    
    Usage:
        with RollbackContext(manager, "operation_name"):
            # Do modifications that might fail
            pass
        # If exception, automatically rolls back
    """
    
    def __init__(self, manager: TransactionManager, name: str):
        self.manager = manager
        self.name = name
    
    def __enter__(self):
        self.manager.transaction(self.name)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            # Exception occurred, rollback
            self.manager.rollback(self.name)
        return False
