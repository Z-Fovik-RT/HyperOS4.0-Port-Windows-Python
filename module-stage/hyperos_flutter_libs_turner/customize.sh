#!/system/bin/sh

if [ "$KSU" = "true" ]; then
    # KernelSU needs module-root system_ext/ when /system_ext is a real
    # separate mount; keep system/system_ext/ otherwise (Magisk-style layout).
    if [ -d "$MODPATH/system/system_ext" ] && [ ! -e "$MODPATH/system_ext" ]; then
        if grep -q ' /system_ext ' /proc/mounts 2>/dev/null; then
            mv "$MODPATH/system/system_ext" "$MODPATH/system_ext"
            ui_print "- KernelSU separate /system_ext detected, using root layout"
        fi
    fi
fi

if [ "$ARCH" != "arm64" ] && [ "$ARCH" != "aarch64" ]; then
    abort "! This module only supports arm64 devices"
fi
