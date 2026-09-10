import argparse
import json
import logging
import shutil
import sys
import zipfile
from pathlib import Path

# Add project root to sys.path to allow imports
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from src.core.rom import RomPackage


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def get_aapt2_path(project_root: Path) -> Path:
    """Auto-detect system environment and return aapt2 path."""
    import platform
    system = platform.system().lower()
    machine = platform.machine().lower()
    
    if machine in ["amd64", "x86_64"]: arch = "x86_64"
    elif machine in ["aarch64", "arm64"]: arch = "arm64"
    else: arch = "x86_64"

    plat_dir = "linux" if system == "linux" else "windows" if system == "windows" else "macos"
    exe_ext = ".exe" if system == "windows" else ""
    
    bin_dir = project_root / "bin" / plat_dir / arch
    aapt2 = bin_dir / f"aapt2{exe_ext}"
    
    if not aapt2.exists():
        # Try fallback to generic platform dir
        aapt2 = project_root / "bin" / plat_dir / f"aapt2{exe_ext}"
        
    return aapt2

def main():
    setup_logging()
    logger = logging.getLogger("BundleGen")
    
    parser = argparse.ArgumentParser(description="HyperOS EU Localization Bundle Generator")
    parser.add_argument("--rom", required=True, help="Path to Source ROM (e.g., CN ROM payload.bin/zip)")
    parser.add_argument("--config", required=True, help="Path to JSON config defining apps to extract")
    parser.add_argument("--version", default="1.0", help="Version tag for the bundle")
    parser.add_argument("--out", default=".", help="Output directory")
    parser.add_argument("--no-zip", action="store_true", help="Do not generate ZIP package, only output folder (for manual modification)")
    args = parser.parse_args()

    work_dir = Path("build_bundle_temp").resolve()
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True)

    try:
        # 1. Load Config
        with open(args.config, 'r') as f:
            config = json.load(f)
        
        apps_list = config.get("apps", [])
        if not apps_list:
            logger.error("No apps defined in config file.")
            return

        # 2. Extract ROM
        logger.info(f"Extracting Source ROM: {args.rom}")
        rom = RomPackage(args.rom, work_dir / "rom_extract", label="Source")
        
        # Add minimal tools attribute to rom for syncer compatibility
        from types import SimpleNamespace
        rom.tools = SimpleNamespace()
        rom.tools.aapt2 = get_aapt2_path(project_root)
        logger.info(f"Using aapt2 tool: {rom.tools.aapt2}")
        
        # Determine which partitions we need to mount/extract based on config
        # Simply extract common system partitions to be safe
        partitions_to_extract = ["system", "product", "system_ext", "mi_ext"]
        rom.extract_images(partitions_to_extract)

        # 3. Harvest Apps
        bundle_root = work_dir / "bundle_root"
        bundle_root.mkdir(parents=True)
        
        extracted_root = rom.extracted_dir
        
        # Build global package index for the source ROM
        logger.info("Building package index for Source ROM...")
        from src.utils.sync_engine import ROMSyncEngine
        syncer = ROMSyncEngine(rom, logger)
        syncer._build_package_cache(extracted_root)
        
        count = 0
        for item in apps_list:
            # Handle both string (legacy) and dict (extended) config
            if isinstance(item, str):
                app_path_str = item
                pkg_name = None
            else:
                app_path_str = item.get("path")
                pkg_name = item.get("package")

            found_srcs = []

            # 1. Try package-based lookup first if provided
            if pkg_name:
                matches = syncer.find_apks_by_package(pkg_name, extracted_root)
                if matches:
                    logger.info(f"Found package {pkg_name} at {len(matches)} location(s)")
                    for apk_path in matches:
                        # For split APKs or apps in folders, we want the parent directory
                        # unless it's a root partition directory
                        parent = apk_path.parent
                        protected_dirs = {"app", "priv-app", "data-app", "overlay", "framework"}
                        if parent.name not in protected_dirs:
                            found_srcs.append(parent)
                        else:
                            found_srcs.append(apk_path)
            
            # 2. Try path-based lookup if no package found or package not specified
            if not found_srcs and app_path_str:
                parts = Path(app_path_str).parts
                if parts:
                    partition = parts[0]
                    relative_path = Path(*parts[1:])
                    
                    candidates = [
                        extracted_root / app_path_str,
                        extracted_root / partition / partition / relative_path
                    ]
                    
                    for candidate in candidates:
                        if candidate.exists():
                            found_srcs.append(candidate)
                            break
            
            if not found_srcs:
                logger.warning(f"App not found: {item}")
                continue
                
            # 3. Copy found sources to bundle root
            for src in found_srcs:
                # Determine destination path
                # If we found it by package, we need to map it back to a standard path
                rel_to_extracted = src.relative_to(extracted_root)
                
                # Handle SAR (System-as-Root) double-folder structure if present
                # e.g. system/system/app/Foo -> system/app/Foo
                path_parts = list(rel_to_extracted.parts)
                if len(path_parts) > 1 and path_parts[0] == path_parts[1]:
                    path_parts.pop(0)
                
                dest_path = bundle_root / Path(*path_parts)
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                
                if src.is_dir():
                    if dest_path.exists(): shutil.rmtree(dest_path)
                    shutil.copytree(src, dest_path, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, dest_path)
                
                logger.info(f"Collected: {Path(*path_parts)}")
                count += 1

        if count == 0:
            logger.error("No apps collected! Check your config and ROM.")
            return

        # 4. Finalize Bundle
        out_name = f"eu_localization_bundle_v{args.version}"
        if not args.no_zip:
            out_name += ".zip"
            
        out_path = Path(args.out).resolve() / out_name
        
        if out_path.exists():
            if out_path.is_dir():
                shutil.rmtree(out_path)
            else:
                out_path.unlink()
            
        if args.no_zip:
            # Output folder only
            logger.info(f"Moving bundle to {out_path}...")
            shutil.move(str(bundle_root), str(out_path))
            
            logger.info(f"Done! Bundle folder generated at: {out_path}")
            logger.info("You can now manually add missing APKs to this folder before zipping.")
        else:
            # Pack as ZIP
            logger.info(f"Zipping bundle to {out_path}...")
            
            with zipfile.ZipFile(out_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
                for file_path in bundle_root.rglob("*"):
                    if file_path.is_file():
                        arcname = file_path.relative_to(bundle_root)
                        zf.write(file_path, arcname)
            
            logger.info("Done!")

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
    finally:
        # Cleanup
        if work_dir.exists():
            shutil.rmtree(work_dir)

if __name__ == "__main__":
    main()
