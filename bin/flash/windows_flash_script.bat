@echo off
cls
setlocal enabledelayedexpansion
reg query "HKEY_LOCAL_MACHINE\SYSTEM\ControlSet001\Control\Nls\Language" /v InstallLanguage|find "0804">nul&& set LANG=Chinese
if "%LANG%"=="Chinese" (
    TITLE windows ˢ���ű� [����ѡ�д��ڣ���ס���Ҽ���س���Ŵ���С���ڻָ�]
) else (
    TITLE Windows Flash Script
)
color 3f
echo.
if exist "super.zst" (
    if "%LANG%"=="Chinese" (
        echo. ���ڽ�ѹsuper����,���ĵȴ�
    ) else (
        echo. Extracting the super image, wait patiently
    )
    bin\windows\zstd.exe --rm -d super.zst -o super.img
    if not "%errorlevel%" == "0" (
        if "%LANG%"=="Chinese" (
            echo. ת��ʧ��,��������˳�
        ) else (
            echo. Conversion failed. Press any key to exit
        )
        pause >nul 2>nul
        exit
    )
)

if "%LANG%"=="Chinese" (
    echo.
    echo. 1. ��������ˢ��
    echo.
    echo. 2. ˫��ˢ��
    echo.
    set /p input=��ѡ��-Ĭ��ѡ��1,�س�ִ��:
) else (
    echo.
    echo. 1. Preserve user data during flashing
    echo.
    echo. 2. Wiping data without wiping /data/media
    echo.
    set /p input=Please select - 1 is selected by default, and enter to execute:
)

if "%LANG%"=="Chinese" (
    echo.
    echo. ������֤��...��ȷ�������豸����Ϊdevice_code�����Ѿ�����fastbootdģʽ adb reboot fastboot��

    echo.
) else (
    echo.
    echo. Validating device...please boot your device into bootloader and make sure your device code is umi
    echo.
)

for /f "tokens=2 delims=: " %%i in ('fastboot %* getvar product 2^>^&1 ^| findstr /r /c:"^product: "') do set "product=%%i"
set "expected_device=device_code"
if "%LANG%"=="Chinese" (
    set "msg_mismatch= �豸device_code��ƥ�䡣�����Ƿ��ǽ���fastbootdģʽ"
    set "msg_continue=���������(y/n):  "
    set "msgort= �����ѱ��û���ֹ��"
    set "msg_continue_process=��������..."
) else (
    set "msg_mismatch=Mismatching image and device."
    set "msg_continue=Do you want to continue anyway? (y/n): "
    set "msgort=Operation aborted by user."
    set "msg_continue_process=Continuing with the process..."
)

if /i "!product!" neq "%expected_device%" (
    echo %msg_mismatch%
    set /p "choice=%msg_continue%"
    if /i "!choice!" neq "y" (
        echo %msgort%
        exit /B 1
    )
)

    bin\windows\fastboot.exe flash boot_a %~dp0boot.img
    bin\windows\fastboot.exe flash boot_b %~dp0boot.img
    bin\windows\fastboot.exe flash dtbo_a %~dp0firmware-update/dtbo.img
    bin\windows\fastboot.exe flash dtbo_b %~dp0firmware-update/dtbo.img


REM firmware

bin\windows\fastboot.exe reboot bootloader
ping 127.0.0.1 -n 5 >nul 2>nul
bin\windows\fastboot.exe flash super %~dp0super.img
if "%input%" == "2" (
	if "%LANG%"=="Chinese" (
	    echo. ����˫��ϵͳ,���ĵȴ�
    ) else (
        echo. Wiping data without wiping /data/media/, please wait patiently
    ) 
	bin\windows\fastboot.exe erase userdata
	bin\windows\fastboot.exe erase metadata
)

REM SET_ACTION_SLOT_A_BEGIN
if "%LANG%"=="Chinese" (
	echo. ���û����Ϊ 'a'��������ҪһЩʱ�䡣�����ֶ�����������ε������ߣ�������ܵ����豸��ש��
) else (
    echo. Starting the process to set the active slot to 'a.' This may take some time. Please refrain from manually restarting or unplugging the data cable, as doing so could result in the device becoming unresponsive.

)
bin\windows\fastboot.exe set_active a
REM SET_ACTION_SLOT_A_END

bin\windows\fastboot.exe reboot

if "%LANG%"=="Chinese" (
    echo. ˢ�����,���ֻ���ʱ��δ�������ֶ�����,��������˳�
) else (
    echo. Flash completed. If the phone does not restart for an extended period, please manually restart. Press any key to exit.
)
pause
exit
