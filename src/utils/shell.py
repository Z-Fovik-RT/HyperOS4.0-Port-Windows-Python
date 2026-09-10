import logging
import os
import platform
import subprocess
from pathlib import Path
from typing import Callable, List, Optional, Union


class ShellRunner:
    def __init__(self):
        self.logger = logging.getLogger("Shell")
        
        system = platform.system().lower()
        if system == "darwin":
            self.os_name = "darwin" # macOS
        elif system == "linux":
            self.os_name = "linux"
        else:
            self.os_name = "windows" 

        machine = platform.machine().lower()
        if machine in ["x86_64", "amd64"]:
            self.arch = "x86_64"
        elif machine in ["aarch64", "arm64"]:
            self.arch = "aarch64"
        else:
            self.arch = "x86_64" # 默认 fallback

        project_root = Path(__file__).resolve().parent.parent.parent
        self.bin_dir = project_root / "bin" / self.os_name / self.arch
        self.platform_bin_dir = project_root / "bin" / self.os_name
        self.flash_bin_dir = project_root / "bin" / "flash" / "platform-tools-windows"

        if not self.bin_dir.exists() and not self.platform_bin_dir.exists():
            self.logger.warning(f"Binary directory not found: {self.bin_dir}")
            
        self.otatools_bin = project_root / "otatools" / "bin"

    def get_binary_path(self, tool_name: str) -> Path:
        """
        Get the absolute path of the tool.
        Search Order:
        1. bin/{os}/{arch}/ (Platform specific tools)
        2. otatools/bin/ (Google OTA tools)
        3. bin/ (Common tools)
        4. System PATH
        """
        # 1. Platform specific
        names = [tool_name]
        if self.os_name == "windows" and not tool_name.lower().endswith(".exe"):
            names.append(f"{tool_name}.exe")
        for name in names:
            bin_path = self.bin_dir / name
            if bin_path.exists():
                return bin_path
        for name in names:
            flat_path = self.platform_bin_dir / name
            if flat_path.exists() and not self._is_unusable_windows_binary(flat_path):
                return flat_path

        # 2. OTATools
        for name in names:
            ota_path = self.otatools_bin / name
            if ota_path.exists() and not self._is_unusable_windows_binary(ota_path):
                return ota_path

        # 3. Common bin
        for name in names:
            common_bin = self.bin_dir.parent.parent / name
            if common_bin.exists():
                return common_bin

        if self.os_name == "windows":
            for name in names:
                bundled = self.flash_bin_dir / name
                if bundled.exists():
                    return bundled

        # 4. Fallback to command name (relies on PATH)
        return Path(tool_name)

    def _is_unusable_windows_binary(self, path: Path) -> bool:
        """Avoid selecting Linux ELF payloads shipped beside OTA scripts."""
        if self.os_name != "windows":
            return False
        try:
            with path.open("rb") as stream:
                return stream.read(4) == b"\x7fELF"
        except OSError:
            return False

    def run(self, cmd: Union[str, List[str]], cwd: Optional[Path] = None, 
            check: bool = True, capture_output: bool = False, 
            env: Optional[dict] = None, logger: Optional[logging.Logger] = None,
            on_line: Optional[Callable[[str], None]] = None,
            shell: bool = False) -> subprocess.CompletedProcess:
        """
        Core method to execute commands
        :param cmd: List of commands (recommended) or string. e.g. ["lpunpack", "super.img"]
        :param cwd: Working directory for execution
        :param check: If True, raise exception when command returns non-zero
        :param capture_output: Whether to capture stdout/stderr (do not print directly to console)
        :param env: Environment variables dict (will merge with system env)
        :param logger: Optional logger to stream output to (forces capture_output=True)
        :param on_line: Optional callback function called for each line of output
        :param shell: If True, execute the command through the shell
        """
        
        # Binary search logic (skipped if shell=True and cmd is a string)
        if not shell and isinstance(cmd, list):
            tool = cmd[0]
            tool_path = self.get_binary_path(tool)
            if tool_path.is_absolute() and tool_path.exists():
                cmd[0] = str(tool_path)
                if os.name != "nt" and not os.access(tool_path, os.X_OK):
                    os.chmod(tool_path, 0o755)
        
        run_env = os.environ.copy()
        if env:
            run_env.update(env)
            
        cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
        self.logger.debug(f"Running: {cmd_str}")

        # If a logger or on_line is provided, we must capture output
        should_capture = capture_output or (logger is not None) or (on_line is not None)

        try:
            if logger or on_line:
                # Streaming mode
                process = subprocess.Popen(
                    cmd,
                    cwd=cwd,
                    shell=shell if shell else (isinstance(cmd, str)),
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    env=run_env
                )
                
                output_lines = []
                if process.stdout:
                    for line in process.stdout:
                        clean_line = line.strip()
                        if on_line:
                            # If callback provided, it's responsible for logging/filtering
                            on_line(clean_line)
                        elif logger and clean_line:
                            # Standard streaming log
                            logger.info(f"  [SHELL] {clean_line}")
                        output_lines.append(line)
                
                returncode = process.wait()
                stdout = "".join(output_lines)
                
                if check and returncode != 0:
                    raise subprocess.CalledProcessError(returncode, cmd, output=stdout)
                
                return subprocess.CompletedProcess(cmd, returncode, stdout, "")
            else:
                # Normal mode
                result = subprocess.run(
                    cmd,
                    cwd=cwd,
                    check=check,
                    shell=shell if shell else (isinstance(cmd, str)),
                    text=True,
                    capture_output=should_capture,
                    env=run_env
                )
                return result
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Command failed with return code {e.returncode}")
            self.logger.error(f"Command: {cmd_str}")
            if hasattr(e, 'stderr') and e.stderr:
                self.logger.error(f"Stderr: {e.stderr.strip()}")
            elif hasattr(e, 'output') and e.output:
                self.logger.error(f"Output: {e.output.strip()}")
            raise e

    def run_java_jar(self, jar_path: Union[str, Path], args: List[str], **kwargs):
        """Helper method specifically for executing java -jar commands"""
        full_jar_path = self.get_binary_path(str(jar_path))
        cmd = ["java", "-jar", str(full_jar_path)] + args
        return self.run(cmd, **kwargs)
