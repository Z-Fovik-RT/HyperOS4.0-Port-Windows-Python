#!/usr/bin/env python3
"""
Cache Management Tool for HyperOS Porting Tool

This tool provides a CLI for managing Port ROM caches, allowing users to:
- List cached ROMs
- View cache statistics
- Clean cache (all or selective)
- Verify cache integrity

Usage:
    python tools/cache_manager.py stats
    python tools/cache_manager.py list
    python tools/cache_manager.py clean --all
    python tools/cache_manager.py verify
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.cache_manager import PortRomCacheManager


def main():
    parser = argparse.ArgumentParser(
        description="Cache Manager for Port ROMs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show cache statistics
  python tools/cache_manager.py stats
  
  # List all cached ROMs
  python tools/cache_manager.py list
  
  # Clean all cache
  python tools/cache_manager.py clean --all
  
  # Verify cache integrity
  python tools/cache_manager.py verify
        """,
    )
    parser.add_argument(
        "--cache-dir", default=".cache/portroms", help="Cache directory (default: .cache/portroms)"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # list command
    list_parser = subparsers.add_parser(
        "list",
        help="List cached ROMs",
        description="List all cached Port ROMs with their partitions",
    )
    list_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    # stats command
    stats_parser = subparsers.add_parser(
        "stats",
        help="Show cache statistics",
        description="Show detailed cache statistics including size and count",
    )
    stats_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    # clean command
    clean_parser = subparsers.add_parser(
        "clean", help="Clean cache", description="Clean cache entries"
    )
    clean_parser.add_argument("--all", action="store_true", help="Remove all cache")
    clean_parser.add_argument("--rom-hash", help="Remove specific ROM cache by hash")
    clean_parser.add_argument("--older-than-days", type=int, help="Remove cache older than N days")

    # verify command
    verify_parser = subparsers.add_parser(
        "verify",
        help="Verify cache integrity",
        description="Verify integrity of all cached entries",
    )
    verify_parser.add_argument(
        "--fix", action="store_true", help="Automatically fix/remove corrupted entries"
    )
    verify_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    cache = PortRomCacheManager(args.cache_dir)

    if args.command == "list":
        roms = cache.list_cached_roms()

        if args.json:
            print(json.dumps(roms, indent=2))
        else:
            if not roms:
                print("No cached ROMs found.")
            else:
                print(f"Cached ROMs ({len(roms)} total):")
                print("-" * 70)
                for rom in roms:
                    print(f"Hash: {rom['hash'][:16]}...")
                    print(f"  Partitions: {', '.join(p['name'] for p in rom['partitions'])}")
                    print(f"  Total size: {rom['total_size_bytes'] / 1024 / 1024:.1f} MB")
                    print()

    elif args.command == "stats":
        stats = cache.get_cache_info()

        if args.json:
            print(json.dumps(stats, indent=2))
        else:
            print("Cache Statistics")
            print("=" * 70)
            print(f"Cache directory: {stats['cache_root']}")
            print(f"Cache version: {stats['version']}")
            print(
                f"Total size: {stats['total_size_mb']:.1f} MB ({stats['total_size_bytes']:,} bytes)"
            )
            print(f"Cached ROMs: {len(stats['cached_roms'])}")

            if stats["cached_roms"]:
                print("\nBreakdown by ROM:")
                for rom in stats["cached_roms"]:
                    print(
                        f"  {rom['hash'][:16]}...: {len(rom['partitions'])} partitions, "
                        f"{rom['total_size_bytes'] / 1024 / 1024:.1f} MB"
                    )

    elif args.command == "clean":
        if args.all:
            if cache.clear_all():
                print("All cache cleared successfully.")
            else:
                print("Failed to clear cache.", file=sys.stderr)
                sys.exit(1)
        elif args.rom_hash:
            # Create a dummy path to use with clear_rom

            class DummyPath:
                def __init__(self, hash_val):
                    self._hash = hash_val

                def stat(self):
                    class Stat:
                        st_size = 0

                    return Stat()

                def read_bytes(self):
                    return self._hash.encode()

            if cache.clear_rom(DummyPath(args.rom_hash)):
                print(f"Cache for ROM {args.rom_hash[:16]}... cleared successfully.")
            else:
                print(f"Failed to clear cache for ROM {args.rom_hash[:16]}...", file=sys.stderr)
                sys.exit(1)
        elif args.older_than_days:
            # TODO: Implement age-based cleanup
            print("Age-based cleanup not yet implemented.", file=sys.stderr)
            sys.exit(1)
        else:
            print("Please specify --all, --rom-hash, or --older-than-days", file=sys.stderr)
            sys.exit(1)

    elif args.command == "verify":
        results = cache.verify_integrity()

        if args.fix:
            # Remove invalid entries
            removed = 0
            for invalid in results["invalid"]:
                rom_dir = cache._get_rom_cache_dir(invalid["rom"])
                part_dir = rom_dir / "partitions" / invalid["partition"]
                if part_dir.exists():
                    import shutil

                    shutil.rmtree(part_dir)
                    removed += 1
            if removed:
                print(f"Removed {removed} corrupted cache entries.")
            results["removed"] = removed

        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print("Cache Integrity Verification")
            print("=" * 70)
            print(f"Valid entries: {len(results['valid'])}")
            print(f"Invalid entries: {len(results['invalid'])}")
            print(f"Errors: {len(results['errors'])}")

            if results["invalid"]:
                print("\nInvalid entries:")
                for inv in results["invalid"]:
                    print(f"  {inv['rom'][:16]}.../{inv['partition']}: {inv['reason']}")

            if results["errors"]:
                print("\nErrors:")
                for err in results["errors"]:
                    print(f"  {err}")

            if args.fix and "removed" in results:
                print(f"\nFixed: {results['removed']} entries removed")


if __name__ == "__main__":
    main()
