import logging
import os
import platform
import shutil
import tarfile
import zipfile
from pathlib import Path

from src.utils.file_downloader import download_file
from src.utils.shell import ShellRunner


class Aria2Manager:
    def __init__(self):
        self.logger = logging.getLogger("Aria2Mgr")
        self.shell = ShellRunner()
        self.system = platform.system().lower()
        self.arch = platform.machine().lower()
        
        # Determine platform-specific binary name
        self.bin_name = "aria2c.exe" if self.system == "windows" else "aria2c"
        
        # Local binary path in project
        self.local_bin = self.shell.bin_dir / self.bin_name
        
    def ensure_aria2(self) -> Path:
        """
        Ensure aria2c is available. Checks system path, then local project bin.
        If missing, downloads a static build.
        """
        # 1. Check System PATH
        system_path = shutil.which(self.bin_name)
        if system_path:
            self.logger.debug(f"Found system aria2c: {system_path}")
            return Path(system_path)

        # 2. Check Local Bin
        if self.local_bin.exists():
            self.logger.debug(f"Found local aria2c: {self.local_bin}")
            return self.local_bin

        # 3. Download if missing
        self.logger.info("aria2c not found. Downloading static build...")
        return self._download_aria2()

    def _download_aria2(self) -> Path:
        """
        Downloads platform-specific static aria2c build.
        Source: https://github.com/q3aql/aria2-static-builds
        """
        # Map architecture/platform to download URL
        # Currently supporting Linux x86_64 and generic Windows
        download_url = ""
        is_zip = False # Linux uses tar.gz usually, Windows zip
        
        if self.system == "linux" and self.arch in ["x86_64", "amd64"]:
            download_url = "https://github.com/q3aql/aria2-static-builds/releases/download/v1.36.0/aria2-1.36.0-linux-gnu-64bit-build1.tar.gz"
        elif self.system == "windows":
            download_url = "https://github.com/q3aql/aria2-static-builds/releases/download/v1.36.0/aria2-1.36.0-win-64bit-build1.zip"
            is_zip = True
        else:
            raise RuntimeError(f"Auto-download not supported for {self.system} {self.arch}. Please install aria2c manually.")

        # Prepare download
        self.local_bin.parent.mkdir(parents=True, exist_ok=True)
        archive_path = self.local_bin.parent / ("aria2.zip" if is_zip else "aria2.tar.gz")
        
        try:
            self.logger.info(f"Downloading from {download_url}...")
            
            # Use shared downloader with progress bar
            if not download_file(download_url, archive_path, self.logger):
                raise RuntimeError("Failed to download aria2 archive")
            
            self.logger.info("Extracting...")
            extracted_bin = None
            
            if is_zip:
                with zipfile.ZipFile(archive_path, 'r') as z:
                    for name in z.namelist():
                        if name.endswith("aria2c.exe"):
                            with open(self.local_bin, 'wb') as f_out:
                                f_out.write(z.read(name))
                            extracted_bin = self.local_bin
                            break
            else:
                with tarfile.open(archive_path, 'r:gz') as t:
                    for member in t.getmembers():
                        if member.name.endswith("aria2c"):
                            f_in = t.extractfile(member)
                            with open(self.local_bin, 'wb') as f_out:
                                shutil.copyfileobj(f_in, f_out)
                            extracted_bin = self.local_bin
                            break
            
            if not extracted_bin or not extracted_bin.exists():
                raise FileNotFoundError("Could not locate aria2c binary in downloaded archive")

            # Make executable
            if self.system != "windows":
                os.chmod(extracted_bin, 0o755)
                
            self.logger.info(f"aria2c installed to {extracted_bin}")
            
            # Cleanup
            archive_path.unlink()
            
            return extracted_bin

        except Exception as e:
            self.logger.error(f"Failed to setup aria2c: {e}")
            if archive_path.exists(): archive_path.unlink()
            raise e

class RomDownloader:
    def __init__(self):
        self.logger = logging.getLogger("Downloader")
        self.aria2_mgr = Aria2Manager()
        self.shell = ShellRunner()
        
        # Project Root / roms
        self.rom_dir = Path("roms").resolve()
        self.rom_dir.mkdir(exist_ok=True)

    def download(self, url: str) -> Path:
        """
        Download ROM from URL using aria2c.
        Returns the absolute path to the downloaded file.
        """
        if not url.startswith("http"):
            return Path(url)

        # Ensure tool exists
        aria2_bin = self.aria2_mgr.ensure_aria2()

        # Extract filename (remove query params)
        # e.g. http://site.com/file.zip?token=123 -> file.zip
        clean_url = url.split('?')[0]
        filename = clean_url.split('/')[-1]
        
        if not filename:
            filename = "downloaded_rom.zip"
            
        target_path = self.rom_dir / filename
        
        if target_path.exists():
            self.logger.info(f"File already exists: {target_path}")
            # Optional: Add integrity check logic here if needed
            return target_path

        self.logger.info(f"Downloading {filename}...")
        self.logger.info(f"URL: {url}")
        
        # Build aria2c command matching port.sh optimization
        cmd = [
            str(aria2_bin),
            "--max-download-limit=1024M",
            "--file-allocation=none",
            "-s10", "-x10", "-j10",
            "-d", str(self.rom_dir),
            "-o", filename,
            url
        ]
        
        try:
            # We want to see download progress, so we don't capture output usually,
            # but ShellRunner might capture it. Ideally we stream it.
            # Using ShellRunner with check=True. 
            # Note: aria2c output is verbose.
            self.shell.run(cmd, check=True)
            
            if not target_path.exists():
                raise FileNotFoundError("Download finished but file not found.")
                
            self.logger.info(f"Download completed: {target_path}")
            return target_path
            
        except Exception as e:
            self.logger.error(f"Download failed: {e}")
            raise e
