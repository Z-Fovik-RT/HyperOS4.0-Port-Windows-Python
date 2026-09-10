import logging
import sys
import urllib.request
from pathlib import Path
from typing import Optional


def download_file(url: str, target_path: Path, logger: Optional[logging.Logger] = None) -> bool:
    """
    Download a file from a URL with a text-based progress bar using only standard libraries.
    
    Args:
        url: The URL to download from.
        target_path: The local path to save the file to.
        logger: Optional logger for info/error messages.
        
    Returns:
        True if download succeeded, False otherwise.
    """
    if logger is None:
        logger = logging.getLogger("FileDownloader")
        
    try:
        logger.info(f"Downloading from {url}...")
        
        # Create parent directories if needed
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        with urllib.request.urlopen(url) as response:
            total_size = int(response.info().get("Content-Length", 0))
            block_size = 8192
            downloaded = 0
            
            with open(target_path, "wb") as f:
                while True:
                    buffer = response.read(block_size)
                    if not buffer:
                        break
                    downloaded += len(buffer)
                    f.write(buffer)
                    
                    if total_size > 0:
                        percent = downloaded * 100 / total_size
                        # Simple progress bar: [#####     ] 50%
                        bar_length = 30
                        filled_length = int(bar_length * downloaded // total_size)
                        bar = '#' * filled_length + '-' * (bar_length - filled_length)
                        
                        # Convert bytes to MB for display
                        downloaded_mb = downloaded / (1024 * 1024)
                        total_mb = total_size / (1024 * 1024)
                        
                        sys.stdout.write(f'\rProgress: [{bar}] {percent:.1f}% ({downloaded_mb:.1f}/{total_mb:.1f} MB)')
                        sys.stdout.flush()
            
            if total_size > 0:
                print()  # New line after completion
                
        logger.info(f"Successfully downloaded to {target_path}")
        return True

    except Exception as e:
        logger.error(f"Download failed: {e}")
        if target_path.exists():
            target_path.unlink()
        return False
