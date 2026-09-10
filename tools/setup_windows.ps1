param(
    [string]$InstallRoot = "$PSScriptRoot\..\bin\windows",
    [switch]$SkipChocolatey,
    [switch]$InstallPrerequisites
)

$ErrorActionPreference = "Stop"
$InstallRoot = [IO.Path]::GetFullPath($InstallRoot)
New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null

Write-Host "Preparing native Windows tooling in $InstallRoot"

function Copy-IfPresent([string]$Source, [string]$Destination) {
    if (Test-Path -LiteralPath $Source) {
        Copy-Item -LiteralPath $Source -Destination $Destination -Force
        Write-Host "  copied $([IO.Path]::GetFileName($Source))"
    }
}

# The repository already ships adb/fastboot and Windows compression helpers.
$flash = Join-Path $PSScriptRoot "..\bin\flash\platform-tools-windows"
foreach ($name in @('adb.exe','fastboot.exe','make_f2fs.exe','make_f2fs_casefold.exe','mke2fs.exe','zstd.exe')) {
    Copy-IfPresent (Join-Path $flash $name) (Join-Path $InstallRoot $name)
}

# Native Windows partition tools from Rprop/aosp15_partition_tools. The
# upstream repository publishes self-contained PE binaries (no Cygwin/WSL).
$partitionBase = "https://raw.githubusercontent.com/Rprop/aosp15_partition_tools/main/windows_x86"
foreach ($name in @('lpmake.exe','lpunpack.exe','simg2img.exe','img2simg.exe','append2simg.exe','ext2simg.exe')) {
    $destination = Join-Path $InstallRoot $name
    if (-not (Test-Path -LiteralPath $destination)) {
        try {
            Invoke-WebRequest -Uri "$partitionBase/$name" -OutFile $destination -UseBasicParsing
            $bytes = [IO.File]::ReadAllBytes($destination)
            if ($bytes.Length -lt 2 -or $bytes[0] -ne 0x4d -or $bytes[1] -ne 0x5a) {
                Remove-Item -LiteralPath $destination -Force
                throw "downloaded file is not a Windows PE executable"
            }
            Write-Host "  downloaded $name"
        } catch {
            Write-Warning "Could not download ${name}: $($_.Exception.Message)"
        }
    }
}

# Native payload.bin extractor (payload-dumper-go, pinned release).
$payloadArchive = Join-Path $env:TEMP "payload-dumper-go_2.0.2_windows_amd64.tar.gz"
$payloadUrl = "https://github.com/ssut/payload-dumper-go/releases/download/2.0.2/payload-dumper-go_2.0.2_windows_amd64.tar.gz"
$payloadExe = Join-Path $InstallRoot "payload-dumper.exe"
if (-not (Test-Path -LiteralPath $payloadExe)) {
    try {
        Invoke-WebRequest -Uri $payloadUrl -OutFile $payloadArchive -UseBasicParsing
        $extract = Join-Path $env:TEMP "payload-dumper-go-extract-$PID"
        Remove-Item -LiteralPath $extract -Recurse -Force -ErrorAction SilentlyContinue
        New-Item -ItemType Directory -Force -Path $extract | Out-Null
        tar -xzf $payloadArchive -C $extract
        $found = Get-ChildItem -LiteralPath $extract -Recurse -File | Where-Object { $_.Name -in @('payload-dumper.exe','payload-dumper-go.exe') } | Select-Object -First 1
        if (-not $found) { throw "payload dumper executable missing from archive" }
        Copy-Item -LiteralPath $found.FullName -Destination $payloadExe -Force
        Remove-Item -LiteralPath $extract -Recurse -Force
        Write-Host "  downloaded payload-dumper.exe"
    } catch {
        Write-Warning "Could not download payload-dumper.exe: $($_.Exception.Message)"
    }
}

# EROFS tools (Cygwin PE builds, no WSL). cygwin1.dll must sit beside the
# executables; the archive ships them together.
$erofsArchive = Join-Path $env:TEMP "erofs-utils-cygwin.zip"
$erofsUrl = "https://github.com/sekaiacg/erofs-tools/releases/download/v1.8.10-251217/erofs-utils-v1.8.10-gee46dd74-251217-Cygwin_x86_64.zip"
$erofsExe = Join-Path $InstallRoot "extract.erofs.exe"
if (-not (Test-Path -LiteralPath $erofsExe)) {
    try {
        Invoke-WebRequest -Uri $erofsUrl -OutFile $erofsArchive -UseBasicParsing
        $extract = Join-Path $env:TEMP "erofs-utils-extract-$PID"
        Remove-Item -LiteralPath $extract -Recurse -Force -ErrorAction SilentlyContinue
        New-Item -ItemType Directory -Force -Path $extract | Out-Null
        tar -xf $erofsArchive -C $extract
        foreach ($name in @('extract.erofs.exe','mkfs.erofs.exe','dump.erofs.exe','fsck.erofs.exe','cygwin1.dll')) {
            $found = Get-ChildItem -LiteralPath $extract -Recurse -File | Where-Object { $_.Name -eq $name } | Select-Object -First 1
            if ($found) {
                Copy-Item -LiteralPath $found.FullName -Destination (Join-Path $InstallRoot $name) -Force
                Write-Host "  downloaded $name"
            }
        }
        $bytes = [IO.File]::ReadAllBytes($erofsExe)
        if ($bytes.Length -lt 2 -or $bytes[0] -ne 0x4d -or $bytes[1] -ne 0x5a) {
            Remove-Item -LiteralPath $erofsExe -Force
            throw "downloaded file is not a Windows PE executable"
        }
        Remove-Item -LiteralPath $extract -Recurse -Force
    } catch {
        Write-Warning "Could not download erofs-utils: $($_.Exception.Message)"
    }
}

# aapt2 is used by the APK package-name cache during Phase 2. The official
# Google Maven artifact is a zip/jar containing the Windows PE binary.
$aapt2Version = "9.0.1-14304508"
$aapt2Archive = Join-Path $env:TEMP "aapt2-$aapt2Version-windows.jar"
$aapt2Url = "https://dl.google.com/dl/android/maven2/com/android/tools/build/aapt2/$aapt2Version/aapt2-$aapt2Version-windows.jar"
$aapt2Exe = Join-Path $InstallRoot "aapt2.exe"
if (-not (Test-Path -LiteralPath $aapt2Exe)) {
    try {
        Invoke-WebRequest -Uri $aapt2Url -OutFile $aapt2Archive -UseBasicParsing
        $extract = Join-Path $env:TEMP "aapt2-extract-$PID"
        Remove-Item -LiteralPath $extract -Recurse -Force -ErrorAction SilentlyContinue
        New-Item -ItemType Directory -Force -Path $extract | Out-Null
        tar -xf $aapt2Archive -C $extract
        $found = Get-ChildItem -LiteralPath $extract -Recurse -File | Where-Object { $_.Name -eq 'aapt2.exe' } | Select-Object -First 1
        if (-not $found) { throw "aapt2.exe missing from Google Maven artifact" }
        Copy-Item -LiteralPath $found.FullName -Destination $aapt2Exe -Force
        $bytes = [IO.File]::ReadAllBytes($aapt2Exe)
        if ($bytes.Length -lt 2 -or $bytes[0] -ne 0x4d -or $bytes[1] -ne 0x5a) {
            Remove-Item -LiteralPath $aapt2Exe -Force
            throw "downloaded file is not a Windows PE executable"
        }
        Remove-Item -LiteralPath $extract -Recurse -Force
        Write-Host "  downloaded aapt2.exe"
    } catch {
        Write-Warning "Could not download aapt2.exe: $($_.Exception.Message)"
    }
}

if ($InstallPrerequisites) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host "Installing prerequisites with winget (user scope, no WSL)..."
        $failed = @()
        function Ensure-WingetPackage([string]$Id, [string]$Command) {
            if (Get-Command $Command -ErrorAction SilentlyContinue) {
                Write-Host "  $Command already available; skipping $Id"
                return
            }
            & winget install --id $Id --exact --accept-package-agreements --accept-source-agreements --silent --disable-interactivity
            if ($LASTEXITCODE -ne 0) { $script:failed += $Id }
        }
        Ensure-WingetPackage 'Python.Python.3.12' 'python'
        Ensure-WingetPackage 'EclipseAdoptium.Temurin.17.JDK' 'java'
        # 7-Zip is optional: Windows 10/11 already ships tar.exe and the
        # project uses it for the payload-dumper archive.
        if ((Get-Command 7z -ErrorAction SilentlyContinue) -or (Test-Path "$env:ProgramFiles\7-Zip\7z.exe")) {
            Write-Host "  7-Zip already available; skipping 7zip.7zip"
        } else {
            Write-Host "  7-Zip not found; skipping optional 7zip.7zip"
        }
        if ($failed.Count -gt 0) {
            Write-Warning "winget could not install: $($failed -join ', ')"
            Write-Host "Install those packages manually, then rerun this script."
        }
    } else {
        Write-Warning "winget is unavailable. Install Python 3.10+, Java 17+, and 7-Zip manually."
    }
} else {
    Write-Host "Skipping prerequisite installation. Use -InstallPrerequisites only when needed."
}

foreach ($required in @('lpmake.exe','lpunpack.exe','simg2img.exe','payload-dumper.exe','aapt2.exe')) {
    if (-not (Test-Path -LiteralPath (Join-Path $InstallRoot $required))) {
        Write-Warning "Missing native tool: $required"
    }
}
if (-not (Test-Path -LiteralPath $erofsExe)) {
    Write-Warning "Missing native tool: extract.erofs.exe"
}
Write-Host "Native Windows setup complete."
Write-Host "Windows tooling is placed in $InstallRoot (EROFS via Cygwin PE, aapt2 via Google Maven)."
