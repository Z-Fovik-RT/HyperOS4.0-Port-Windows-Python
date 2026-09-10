import logging
import zipfile
from pathlib import Path
from typing import Optional


class OtaToolsManager:
    # Prefer this fork's Release assets; fall back to upstream if missing here
    DEFAULT_URL = (
        "https://github.com/Z-Fovik-RT/HyperOS4.0-Port-Windows-Python"
        "/releases/download/assets/otatools.zip"
    )
    FALLBACK_URL = (
        "https://github.com/toraidl/HyperOS-Port-Python"
        "/releases/download/assets/otatools.zip"
    )

    def __init__(self, tools_dir: Path | None = None):
        project_root = Path(__file__).resolve().parents[2]
        self.tools_dir = tools_dir or (project_root / "otatools")
        self.logger = logging.getLogger("OtaToolsManager")

    def check_otatools_exists(self) -> bool:
        """Check if the otatools directory exists with basic components."""
        if not self.tools_dir.exists():
            return False
        
        # Check for some common directories that should be in otatools
        required_dirs = ["bin", "lib64"]
        for d in required_dirs:
            if not (self.tools_dir / d).exists():
                return False
                
        return True

    def download_otatools(self, url: Optional[str] = None) -> bool:
        """
        Download and extract otatools from given URL (or default URL).

        Args:
            url: URL to download otatools.zip from (optional, uses default if not provided)

        Returns:
            True if the download and extraction was successful, False otherwise
        """
        if url is None:
            # Try this fork first, then upstream asset host
            urls = [self.DEFAULT_URL, self.FALLBACK_URL]
        else:
            urls = [url]

        from .file_downloader import download_file

        temp_file = self.tools_dir.parent / "otatools_temp.zip"
        success = False
        for candidate in urls:
            try:
                if temp_file.exists():
                    temp_file.unlink()

                self.logger.info(f"Downloading otatools from {candidate}")
                if not download_file(candidate, temp_file, self.logger):
                    continue

                self.logger.info("Download completed. Extracting...")
                self.tools_dir.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(temp_file, "r") as zip_ref:
                    zip_ref.extractall(self.tools_dir)

                self.logger.info(f"otatools extracted to {self.tools_dir.resolve()}")
                bin_dir = self.tools_dir / "bin"
                if bin_dir.exists():
                    for file in bin_dir.iterdir():
                        if file.is_file():
                            current_mode = file.stat().st_mode
                            file.chmod(current_mode | 0o111)
                    self.logger.info("Set execute permissions on otatools binaries")

                if temp_file.exists():
                    temp_file.unlink()
                success = True
                break
            except Exception as e:
                self.logger.error(f"Failed to download/extract from {candidate}: {e}")
                continue

        if not success:
            self.logger.error("Failed to download otatools from all known sources.")
        return success

    def ensure_otatools(self) -> bool:
        """
        Check if otatools exists and is complete; if not, download it.

        Returns:
            True if otatools is available or successfully downloaded, False otherwise
        """
        if self.check_otatools_exists():
            self.logger.info(f"otatools already exists and is complete at {self.tools_dir.resolve()}")
            return True

        if self.tools_dir.exists():
            self.logger.warning(
                f"otatools directory exists but is incomplete or missing critical binaries. Re-downloading from {self.DEFAULT_URL}"
            )
        else:
            self.logger.info(
                f"otatools directory does not exist. Attempting to download from {self.DEFAULT_URL}"
            )
        return self.download_otatools()
