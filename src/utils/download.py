import logging
from pathlib import Path

from .file_downloader import download_file


class AssetDownloader:
    def __init__(
        self,
        repo="Z-Fovik-RT/HyperOS4.0-Port-Windows-Python",
        tag="assets",
        fallback_repo="toraidl/HyperOS-Port-Python",
    ):
        self.repo = repo
        self.tag = tag
        self.fallback_repo = fallback_repo
        # Use a mirror if you are in a region with poor GitHub connectivity
        # Example: 'https://mirror.ghproxy.com/'
        self.mirror_url = ""
        self.base_url = f"https://github.com/{repo}/releases/download/{tag}"
        self.fallback_base_url = (
            f"https://github.com/{fallback_repo}/releases/download/{tag}"
            if fallback_repo
            else ""
        )
        self.logger = logging.getLogger("Downloader")

    def _get_asset_name(self, local_path: Path) -> str:
        """
        Convert local path to remote asset name with prefix.
        Rules:
        - devices/common/file.zip -> common_file.zip
        - devices/fuxi/file.ko    -> fuxi_file.ko
        - assets/ksuinit          -> assets_ksuinit
        """
        parts = local_path.parts
        # If it's inside devices/...
        if "devices" in parts:
            idx = parts.index("devices")
            if len(parts) > idx + 1:
                # Get the folder name after 'devices' (e.g., 'common', 'fuxi')
                prefix = parts[idx + 1]
                name = parts[-1]
                return f"{prefix}_{name}"
        
        # If it's inside assets/...
        if "assets" in parts:
            name = parts[-1]
            return f"assets_{name}"
            
        return local_path.name

    def download_if_missing(self, local_path: Path) -> bool:
        """
        Check if file exists, if not, try to download from GitHub Assets.
        Tries this fork's Release first, then the upstream assets Release.
        """
        if local_path.exists():
            return True

        asset_name = self._get_asset_name(local_path)
        bases = [self.base_url]
        if self.fallback_base_url and self.fallback_base_url != self.base_url:
            bases.append(self.fallback_base_url)

        max_retries = 2
        for base in bases:
            if self.mirror_url:
                url = f"{self.mirror_url.rstrip('/')}/{base}/{asset_name}"
            else:
                url = f"{base}/{asset_name}"

            for attempt in range(max_retries + 1):
                self.logger.info(
                    f"Downloading: {asset_name} from {base} (Attempt {attempt+1}/{max_retries+1})..."
                )
                if download_file(url, local_path, self.logger):
                    return True
                if attempt == max_retries and not self.mirror_url:
                    self.logger.info(
                        "Tip: Try setting a mirror URL in AssetDownloader if network is unstable."
                    )

        return False
