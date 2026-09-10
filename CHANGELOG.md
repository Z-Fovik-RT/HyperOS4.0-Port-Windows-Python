# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

---

## [1.5.0] - 2026-03-28

### Added

#### Virtual A/B Compression (VABC) Metadata Integration
- **payload-dumper**: Enhanced binary to extract `dynamic_partition_metadata` from payload.bin via `--json` flag
  - `cow_version`: COW format version for snapshot optimization
  - `compression_factor`: Compression factor value
  - `snapshot_enabled`: Virtual A/B snapshot status
  - `vabc_enabled`: Virtual A/B compression enablement
  - `vabc_compression_param`: Compression algorithm (lz4, gz, etc.)
- **DynamicPartitionMetadata dataclass**: New dataclass in `payload_dumper.py` to represent VABC settings
- **partition_info.json storage**: VABC metadata now automatically stored in device configuration
- **OTA packaging integration**: `misc_info.txt` now uses accurate VABC settings from Stock ROM
  - `virtual_ab_compression_method`
  - `virtual_ab_cow_version`
  - `virtual_ab_compression_factor`

### Fixed
- **workflow**: Handle resume context gracefully when `stock` attribute is not set in PortingContext

---

## [1.4.0] - 2026-03-26

### Added

#### Custom AVB Chain Support
- **AVB auto-sync**: Automatically sync `partition_info.json` from stock vbmeta profile
- **AVB chain alignment**: Custom packaging now aligns with stock AVB chain and partition caps
- **AVB chain toggle**: New `--custom-avb-chain` CLI flag to enable/disable custom AVB chain
- **Resume from packer**: Checkpoint-based resume capability for interrupted packaging runs
  - New `--resume` CLI flag to resume from last successful phase
  - Saves progress at each major phase (extraction, initialization, modification, packing)

### Fixed
- **types**: Resolved curated mypy errors in AVB misc generation

---

## [1.3.0] - 2026-03-20

### Added

#### Global ROM Region Support
- **Region subtype detection**: Automatically detect Global ROM region subtype from `mod_device` prop
- **Region metadata entry point**: Reserved stock region metadata for cross-region porting
- **Package naming**: OTA packages now include global region device tags

#### Props Synchronization
- **Product build.prop sync**: Sync product build.prop from stock with layered skip-key control
- **Skip key configuration**: Configurable key skipping for build.prop synchronization

#### Plugin System
- **Dynamic plugin discovery**: APK modifier plugins now auto-discovered from `plugins/apk/` directory
- **Global ROM detection**: Separated Global ROM detection from EU localization path

### Changed
- **lint**: Applied Ruff lint fixes across repository

---

## [1.2.0] - 2026-03-19

### Added

#### EU Localization Plugin
- **HTMLViewer plugin**: Full `doInBackground` rewrite for EU locale support
- **EU-specific overrides**: Support for EU-specific override directory (`overrides_eu/`)
- **Smali idempotent append**: New idempotent method append support in smalikit

#### Device Support
- **Xiaomi 17 (pudding)**: New device configuration for Xiaomi 17 series
- **General override directory**: Support for general override directory structure

### Fixed
- **smalikit**: Detect existing appended method by declaration, not by reference
- **htmlviewer**: Avoid patching bridge `doInBackground` method
- **htmlviewer**: Fixed two fatal smali register errors in EU ROM plugin
- **vbmeta**: Set AVB flags to `0x01` to prevent Android 16 fastboot lock
- **replacements.json**: Corrected format for pudding device

### Changed
- **pudding**: Updated CPU zh label in EU device_info

---

## [1.1.0] - 2026-03-18

### Added

#### Auto-Configuration
- **Device auto-configuration**: Automatically configure device when config is missing
- **partition_info.json**: Read partition list from auto-generated partition_info.json
- **Payload metadata storage**: Store payload metadata in RomPackage for later use
- **Payload metadata extraction**: Integrated metadata extraction in extractors module
- **payload-dumper wrapper**: New Python wrapper module for payload-dumper CLI

### Changed
- **firmware**: Simplified AVB disabling by patching only vbmeta.img (removed fstab modification)

### Fixed
- **mypy**: Resolved `no-any-return` error in packer.py
- **CLI**: Fail fast on invalid local ROM input paths

---

## [1.0.0] - 2026-03-17

### Added

#### Core Features
- **Full ROM porting workflow**: From stock/port ZIP to OTA package
- **System patching**: Firmware, system, framework, and ROM property modifications
- **GKI support**: KernelSU injection for GKI 2.0+ devices (kernel 5.10+)
- **AVB disable**: Disable Android Verified Boot via vbmeta.img modification
- **Wild Boost**: Port Redmi Wild Boost to Xiaomi devices (verified on Xiaomi 12S/13)
- **Modular configuration**: Enable/disable features via JSON config files
- **EU localization**: Restore CN-specific features (NFC, Mi Wallet, Xiao AI) for Global/EU ROMs
- **Multiple output formats**: `payload.bin` (Recovery/OTA) or `super.img` (Hybrid/Fastboot)
- **Official OTA compatibility**: Produce OTA packages compatible with official update app

#### Diff Report
- **Artifact diff reports**: Generate post-porting diff reports for review
- **Risk highlights**: Improve diff-report readability with partition groups and risk flags
- **Summary logs**: Surface diff-report summary and risk flags in workflow logs

### Performance
- **Artifact state collection**: Optimized and removed redundant APK hashing

---

## Device Support

| Device | Codename | Status |
|--------|----------|--------|
| Xiaomi 13 | fuxi | ✅ Verified |
| Xiaomi 12S | mayfly | ✅ Verified |
| Xiaomi 17 | pudding | ✅ Verified |
| Xiaomi 14 | - | ✅ Port Source |
| Xiaomi 15 | - | ✅ Port Source |
| Redmi K90 | - | ✅ Port Source |
| Redmi K90 Pro | - | ✅ Port Source |

---

## Wild Boost Compatibility

| Target Device | Kernel | Installation Path |
|---------------|--------|-------------------|
| Xiaomi 12S (mayfly) | 5.10 | vendor_boot ramdisk |
| Xiaomi 13 (fuxi) | 5.15 | vendor_dlkm |

---

[Unreleased]: https://github.com/toraidl/HyperOS-Port-Python/compare/v1.5.0...HEAD
[1.5.0]: https://github.com/toraidl/HyperOS-Port-Python/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/toraidl/HyperOS-Port-Python/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/toraidl/HyperOS-Port-Python/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/toraidl/HyperOS-Port-Python/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/toraidl/HyperOS-Port-Python/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/toraidl/HyperOS-Port-Python/releases/tag/v1.0.0