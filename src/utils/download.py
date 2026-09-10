import logging
from pathlib import Path

from .file_downloader import download_file


class AssetDownloader:
    def __init__(self, repo="toraidl/HyperOS-Port-Python", tag="assets"):
        self.repo = repo
        self.tag = tag
        # Use a mirror if you are in a region with poor GitHub connectivity
        # Example: 'https://mirror.ghproxy.com/'
        self.mirror_url = "" 
        self.base_url = f"https://github.com/{repo}/releases/download/{tag}"
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
        """
        if local_path.exists():
            return True

        asset_name = self._get_asset_name(local_path)
        
        # Apply mirror if set
        if self.mirror_url:
            url = f"{self.mirror_url.rstrip('/')}/{self.base_url}/{asset_name}"
        else:
            url = f"{self.base_url}/{asset_name}"
        
        # Attempt standard download with a few retries
        max_retries = 2
        for attempt in range(max_retries + 1):
            self.logger.info(f"Downloading: {asset_name} (Attempt {attempt+1}/{max_retries+1})...")
            
            if download_file(url, local_path, self.logger):
                return True
            
            # If failed, retry logic handled by loop
            if attempt == max_retries:
                if not self.mirror_url:
                    self.logger.info("Tip: Try setting a mirror URL in AssetDownloader if network is unstable.")
        
        return False
