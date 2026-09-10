"""
Port ROM Cache Manager - Hierarchical caching for ROM porting

This module provides a hierarchical caching system for Port ROM processing,
enabling reuse of extracted partitions and APK modifications across multiple
device porting operations.

Features:
    - Partition-level caching (Level 1) - DISABLED BY DEFAULT
    - APK modification caching (Level 2) - ALWAYS ENABLED
    - File lock support for concurrent access
    - Cache metadata management with versioning
    - Automatic cache validation and invalidation

Usage:
    # APK caching only (default)
    cache = PortRomCacheManager(".cache/portroms")

    # Enable partition caching for multi-device reuse
    cache = PortRomCacheManager(".cache/portroms", cache_partitions=True)

    # Store partition
    cache.store_partition(rom_path, "system", extracted_dir)

    # Restore partition
    cache.restore_partition(rom_path, "system", target_dir)

    # Check cache validity
    if cache.is_partition_cached(rom_path, "system"):
        print("Cache hit!")
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Cache format version
CACHE_VERSION = "1.0"
DEFAULT_CACHE_ROOT = ".cache/portroms"


@dataclass
class CacheMetadata:
    """Cache metadata structure for tracking cached partitions."""

    version: str = CACHE_VERSION
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    rom_hash: str = ""
    partition_name: str = ""
    file_count: int = 0
    total_size: int = 0
    modifier_version: str = "1.0"
    source_size: int = 0
    rom_type: str = ""  # ROM type (PAYLOAD, FASTBOOT, etc.)
    extracted_at: str = ""  # Extraction timestamp

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CacheMetadata":
        return cls(**data)


class FileLock:
    """
    Cross-platform file lock implementation.

    Supports Unix (fcntl) with fallback for Windows.
    """

    def __init__(self, lock_file: Union[str, Path], timeout: float = 30.0):
        self.lock_file = Path(lock_file)
        self.timeout = timeout
        self._lock_fd: Optional[Any] = None
        self._logger = logging.getLogger("FileLock")

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False

    def acquire(self) -> bool:
        """Acquire file lock."""
        import fcntl

        self.lock_file.parent.mkdir(parents=True, exist_ok=True)

        start_time = time.time()
        while True:
            try:
                self._lock_fd = open(self.lock_file, "w")
                fcntl.flock(self._lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self._logger.debug(f"Lock acquired: {self.lock_file}")
                return True
            except (IOError, OSError) as err:
                if self._lock_fd:
                    self._lock_fd.close()
                    self._lock_fd = None

                if time.time() - start_time > self.timeout:
                    self._logger.warning(f"Lock timeout after {self.timeout}s")
                    raise TimeoutError(
                        f"Could not acquire lock: {self.lock_file}"
                    ) from err

                time.sleep(0.1)

    def release(self):
        """Release file lock."""
        import fcntl

        if self._lock_fd:
            try:
                fcntl.flock(self._lock_fd.fileno(), fcntl.LOCK_UN)
                self._lock_fd.close()
                self._logger.debug(f"Lock released: {self.lock_file}")
            except Exception as e:
                self._logger.error(f"Error releasing lock: {e}")
            finally:
                self._lock_fd = None


class PortRomCacheManager:
    """
    Port ROM Cache Manager

    Manages partition and APK modification caches for Port ROM processing.
    Supports reuse across multiple device porting operations.

    Cache Levels:
        - Level 1 (Partition): Disabled by default - high disk usage
        - Level 2 (APK): Always enabled - minimal disk usage

    Attributes:
        cache_root: Cache root directory path
        cache_partitions: Whether partition-level caching is enabled
        logger: Logger instance

    Example:
        >>> # APK caching only (default)
        >>> cache = PortRomCacheManager(".cache/portroms")
        >>>
        >>> # Enable partition caching for multi-device reuse
        >>> cache = PortRomCacheManager(".cache/portroms", cache_partitions=True)
        >>> cache.store_partition(rom_path, "system", extracted_dir)
        >>> cache.restore_partition(rom_path, "system", target_dir)
    """

    def __init__(
        self,
        cache_root: Union[str, Path] = DEFAULT_CACHE_ROOT,
        cache_partitions: bool = False,
    ):
        """
        Initialize cache manager.

        Args:
            cache_root: Cache root directory path, default ".cache/portroms"
            cache_partitions: Enable partition-level caching, default False

        Note:
            Partition-level caching consumes significant disk space.
            Enable only when reusing same Port ROM across multiple devices.
            APK modification caching is always enabled regardless of this setting.
        """
        self.cache_root = Path(cache_root).resolve()
        self.cache_root.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger("PortRomCacheManager")

        # Partition-level caching switch (disabled by default)
        self.cache_partitions = cache_partitions
        if cache_partitions:
            self.logger.info("Partition-level caching enabled")
        else:
            self.logger.info("Partition-level caching disabled (APK caching still active)")

        # Ensure metadata directory exists
        self._metadata_file = self.cache_root / "metadata.json"
        self._load_global_metadata()

    def _load_global_metadata(self):
        """Load global cache metadata."""
        if self._metadata_file.exists():
            try:
                with open(self._metadata_file, "r", encoding="utf-8") as f:
                    self._global_metadata = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                self.logger.warning(f"Failed to load global metadata: {e}")
                self._global_metadata = {"version": CACHE_VERSION, "roms": {}}
        else:
            self._global_metadata = {"version": CACHE_VERSION, "roms": {}}

    def _save_global_metadata(self):
        """Save global cache metadata."""
        try:
            with open(self._metadata_file, "w", encoding="utf-8") as f:
                json.dump(self._global_metadata, f, indent=2)
        except IOError as e:
            self.logger.error(f"Failed to save global metadata: {e}")

    def _compute_rom_hash(self, rom_path: Union[str, Path]) -> str:
        """
        Compute ROM file hash.

        For large files, uses segmented hashing for performance:
        - First 10MB
        - Middle 10MB
        - Last 10MB

        Args:
            rom_path: ROM file path

        Returns:
            32-character MD5 hash string
        """
        path = Path(rom_path)
        if not path.exists():
            raise FileNotFoundError(f"ROM file not found: {path}")

        hash_md5 = hashlib.md5()
        file_size = path.stat().st_size

        with open(path, "rb") as f:
            if file_size < 100 * 1024 * 1024:  # < 100MB
                # Small file: read all
                hash_md5.update(f.read())
            else:
                # Large file: segmented read
                chunk_size = 10 * 1024 * 1024  # 10MB

                # Read beginning
                hash_md5.update(f.read(chunk_size))

                # Read middle
                f.seek(file_size // 2)
                hash_md5.update(f.read(chunk_size))

                # Read end
                f.seek(-chunk_size, 2)
                hash_md5.update(f.read(chunk_size))

        return hash_md5.hexdigest()

    def _get_rom_cache_dir(self, rom_hash: str) -> Path:
        """Get ROM cache directory."""
        return self.cache_root / rom_hash[:16]

    def _get_partition_cache_dir(self, rom_hash: str, partition: str) -> Path:
        """Get partition cache directory."""
        return self._get_rom_cache_dir(rom_hash) / "partitions" / partition

    def _get_apk_cache_dir(self, rom_hash: str) -> Path:
        """Get APK cache directory."""
        return self._get_rom_cache_dir(rom_hash) / "apks"

    def _get_lock_file(self, rom_hash: str) -> Path:
        """Get lock file path."""
        return self._get_rom_cache_dir(rom_hash) / ".lock"

    def is_partition_cached(
        self, rom_path: Union[str, Path], partition: str, validate: bool = True
    ) -> bool:
        """
        Check if partition is cached.

        Args:
            rom_path: ROM file path
            partition: Partition name (e.g., "system", "product")
            validate: Whether to validate cache integrity

        Returns:
            True if cache exists and is valid
        """
        if not self.cache_partitions:
            return False

        try:
            rom_hash = self._compute_rom_hash(rom_path)
        except FileNotFoundError:
            return False

        cache_dir = self._get_partition_cache_dir(rom_hash, partition)
        metadata_file = cache_dir / "cache_metadata.json"

        if not cache_dir.exists() or not metadata_file.exists():
            return False

        if not validate:
            return True

        # Validate cache metadata
        try:
            with open(metadata_file, "r", encoding="utf-8") as f:
                metadata = CacheMetadata.from_dict(json.load(f))

            # Check version compatibility
            if metadata.version != CACHE_VERSION:
                self.logger.debug(f"Cache version mismatch: {metadata.version} vs {CACHE_VERSION}")
                return False

            # Check cache directory is non-empty
            if not any(cache_dir.iterdir()):
                return False

            return True

        except (json.JSONDecodeError, IOError, KeyError) as e:
            self.logger.debug(f"Cache validation failed: {e}")
            return False

    def store_partition(
        self,
        rom_path: Union[str, Path],
        partition: str,
        source_dir: Union[str, Path],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Store partition to cache.

        Args:
            rom_path: ROM file path
            partition: Partition name
            source_dir: Source directory path
            metadata: Additional metadata

        Returns:
            True if storage successful
        """
        if not self.cache_partitions:
            self.logger.debug(f"Partition caching disabled, skipping cache store for {partition}")
            return False

        rom_hash = self._compute_rom_hash(rom_path)
        cache_dir = self._get_partition_cache_dir(rom_hash, partition)
        lock_file = self._get_lock_file(rom_hash)

        with FileLock(lock_file):
            try:
                # Clean old cache
                if cache_dir.exists():
                    shutil.rmtree(cache_dir)
                cache_dir.mkdir(parents=True, exist_ok=True)

                # Copy files
                source = Path(source_dir)
                file_count = 0
                total_size = 0

                for item in source.rglob("*"):
                    if item.is_file():
                        rel_path = item.relative_to(source)
                        target = cache_dir / rel_path
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(item, target, follow_symlinks=False)
                        file_count += 1
                        total_size += item.stat().st_size

                # Save metadata
                cache_metadata = CacheMetadata(
                    rom_hash=rom_hash,
                    partition_name=partition,
                    file_count=file_count,
                    total_size=total_size,
                    source_size=Path(rom_path).stat().st_size,
                    **(metadata or {}),
                )

                metadata_file = cache_dir / "cache_metadata.json"
                with open(metadata_file, "w", encoding="utf-8") as f:
                    json.dump(cache_metadata.to_dict(), f, indent=2)

                # Update global metadata
                self._global_metadata["roms"][rom_hash] = {
                    "hash": rom_hash,
                    "cached_at": datetime.now().isoformat(),
                    "partitions": list(
                        self._global_metadata["roms"].get(rom_hash, {}).get("partitions", [])
                    )
                    + [partition],
                }
                self._save_global_metadata()

                self.logger.info(
                    f"Cached partition {partition}: {file_count} files, "
                    f"{total_size / 1024 / 1024:.1f} MB"
                )
                return True

            except Exception as e:
                self.logger.error(f"Failed to cache partition {partition}: {e}")
                # Clean failed cache
                if cache_dir.exists():
                    shutil.rmtree(cache_dir)
                return False

    def restore_partition(
        self, rom_path: Union[str, Path], partition: str, target_dir: Union[str, Path]
    ) -> bool:
        """
        Restore partition from cache.

        Args:
            rom_path: ROM file path
            partition: Partition name
            target_dir: Target directory path

        Returns:
            True if restoration successful
        """
        if not self.cache_partitions:
            return False

        rom_hash = self._compute_rom_hash(rom_path)
        cache_dir = self._get_partition_cache_dir(rom_hash, partition)
        target = Path(target_dir)

        try:
            # Clean target directory
            if target.exists():
                shutil.rmtree(target)
            target.mkdir(parents=True, exist_ok=True)

            # Copy files (exclude metadata files)
            for item in cache_dir.rglob("*"):
                if item.name == "cache_metadata.json":
                    continue
                if item.is_file():
                    rel_path = item.relative_to(cache_dir)
                    dst = target / rel_path
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, dst, follow_symlinks=False)

            self.logger.info(f"Restored partition {partition} from cache")
            return True

        except Exception as e:
            self.logger.error(f"Failed to restore partition {partition}: {e}")
            return False

    def get_cache_info(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        info: Dict[str, Any] = {
            "version": CACHE_VERSION,
            "cache_root": str(self.cache_root),
            "total_size_bytes": 0,
            "total_size_mb": 0,
            "cached_roms": [],
        }

        try:
            for rom_dir in self.cache_root.iterdir():
                if not rom_dir.is_dir():
                    continue
                if rom_dir.name in ["metadata.json", ".lock"]:
                    continue

                rom_info: Dict[str, Any] = {
                    "hash": rom_dir.name,
                    "partitions": [],
                    "total_size_bytes": 0,
                }

                partitions_dir = rom_dir / "partitions"
                if partitions_dir.exists():
                    for part_dir in partitions_dir.iterdir():
                        if part_dir.is_dir():
                            part_size = sum(
                                f.stat().st_size for f in part_dir.rglob("*") if f.is_file()
                            )
                            rom_info["partitions"].append(
                                {
                                    "name": part_dir.name,
                                    "size_bytes": part_size,
                                    "size_mb": round(part_size / 1024 / 1024, 2),
                                }
                            )
                            rom_info["total_size_bytes"] += part_size

                info["cached_roms"].append(rom_info)
                info["total_size_bytes"] += rom_info["total_size_bytes"]

            info["total_size_mb"] = round(info["total_size_bytes"] / 1024 / 1024, 2)

        except Exception as e:
            self.logger.error(f"Error getting cache info: {e}")

        return info

    def list_cached_roms(self) -> List[Dict[str, Any]]:
        """List all cached ROMs."""
        cached_roms = self.get_cache_info().get("cached_roms")
        if isinstance(cached_roms, list):
            return cached_roms
        return []

    def clear_partition(self, rom_path: Union[str, Path], partition: str) -> bool:
        """
        Clear specific partition cache.

        Args:
            rom_path: ROM file path
            partition: Partition name

        Returns:
            True if clearance successful
        """
        try:
            rom_hash = self._compute_rom_hash(rom_path)
            cache_dir = self._get_partition_cache_dir(rom_hash, partition)
            lock_file = self._get_lock_file(rom_hash)

            with FileLock(lock_file):
                if cache_dir.exists():
                    shutil.rmtree(cache_dir)
                    self.logger.info(f"Cleared cache for partition {partition}")
                    return True
            return False

        except Exception as e:
            self.logger.error(f"Failed to clear partition cache: {e}")
            return False

    def clear_rom(self, rom_path: Union[str, Path]) -> bool:
        """
        Clear all cache for specific ROM.

        Args:
            rom_path: ROM file path

        Returns:
            True if clearance successful
        """
        try:
            rom_hash = self._compute_rom_hash(rom_path)
            rom_dir = self._get_rom_cache_dir(rom_hash)
            lock_file = self._get_lock_file(rom_hash)

            with FileLock(lock_file):
                if rom_dir.exists():
                    shutil.rmtree(rom_dir)

                # Remove from global metadata
                if rom_hash in self._global_metadata.get("roms", {}):
                    del self._global_metadata["roms"][rom_hash]
                    self._save_global_metadata()

                self.logger.info(f"Cleared all cache for ROM {rom_hash[:16]}...")
                return True

        except Exception as e:
            self.logger.error(f"Failed to clear ROM cache: {e}")
            return False

    def clear_all(self) -> bool:
        """
        Clear all cache.

        Returns:
            True if clearance successful
        """
        try:
            for item in self.cache_root.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                elif item.is_file() and item.name != ".gitkeep":
                    item.unlink()

            self._global_metadata = {"version": CACHE_VERSION, "roms": {}}
            self._save_global_metadata()

            self.logger.info("Cleared all cache")
            return True

        except Exception as e:
            self.logger.error(f"Failed to clear all cache: {e}")
            return False

    def verify_integrity(self, rom_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
        """
        Verify cache integrity.

        Args:
            rom_path: Optional, specify ROM to verify. None verifies all.

        Returns:
            Verification results dictionary
        """
        results: Dict[str, List[Dict[str, Any]]] = {
            "valid": [],
            "invalid": [],
            "errors": [],
        }

        try:
            if rom_path:
                roms_to_check = [Path(rom_path)]
            else:
                # Get all cached ROMs from metadata
                roms_to_check = [
                    self.cache_root / rom_hash[:16]
                    for rom_hash in self._global_metadata.get("roms", {}).keys()
                ]

            for rom_item in roms_to_check:
                if not rom_item.exists():
                    continue

                partitions_dir = rom_item / "partitions"
                if not partitions_dir.exists():
                    continue

                for part_dir in partitions_dir.iterdir():
                    if not part_dir.is_dir():
                        continue

                    metadata_file = part_dir / "cache_metadata.json"
                    if not metadata_file.exists():
                        results["invalid"].append(
                            {
                                "rom": rom_item.name,
                                "partition": part_dir.name,
                                "reason": "Missing metadata",
                            }
                        )
                        continue

                    try:
                        with open(metadata_file, "r", encoding="utf-8") as f:
                            metadata = json.load(f)

                        # Verify file count
                        actual_files = (
                            sum(1 for _ in part_dir.rglob("*") if _.is_file()) - 1
                        )  # Exclude metadata
                        expected_files = metadata.get("file_count", 0)

                        if actual_files != expected_files:
                            results["invalid"].append(
                                {
                                    "rom": rom_item.name,
                                    "partition": part_dir.name,
                                    "reason": f"File count mismatch: {actual_files} vs {expected_files}",
                                }
                            )
                        else:
                            results["valid"].append(
                                {
                                    "rom": rom_item.name,
                                    "partition": part_dir.name,
                                    "files": actual_files,
                                }
                            )

                    except Exception as e:
                        results["errors"].append(
                            {
                                "rom": rom_item.name,
                                "partition": part_dir.name,
                                "error": str(e),
                            }
                        )

        except Exception as e:
            results["errors"].append({"global": str(e)})

        return results


# Convenience functions
def get_cache_manager(cache_root: Union[str, Path] = DEFAULT_CACHE_ROOT) -> PortRomCacheManager:
    """Get cache manager instance."""
    return PortRomCacheManager(cache_root)
