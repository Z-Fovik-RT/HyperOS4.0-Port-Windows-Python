#!/bin/bash

# ================= 配置区 =================
REPO="toraidl/HyperOS-Port-Python"
TAG="assets"
# =========================================

# 检查 GitHub CLI 是否安装
if ! command -v gh &> /dev/null; then
    echo "[-] 错误: 未找到 GitHub CLI (gh)。"
    echo "    请先安装并登录: https://cli.github.com/"
    exit 1
fi

# 确保 Release 存在
echo "[*] 检查 Release Tag: $TAG ..."
gh release view "$TAG" -R "$REPO" &>/dev/null
if [ $? -ne 0 ]; then
    echo "[*] 正在创建新的 Release: $TAG ..."
    gh release create "$TAG" --title "Resources Storage" --notes "Auto-managed assets for HyperOS Porting." -R "$REPO"
fi

upload_file() {
    local file_path="$1"
    
    if [[ ! -f "$file_path" ]]; then
        echo "[-] 跳过: $file_path 不是有效文件。"
        return
    fi

    local filename=$(basename "$file_path")
    local dir_path=$(dirname "$file_path")
    local asset_name=""

    # 匹配 Python 中的命名逻辑
    if [[ "$dir_path" == *"devices/"* ]]; then
        # 提取 devices/ 后的第一级目录名作为前缀
        local prefix=$(echo "$dir_path" | sed 's/.*devices\///' | cut -d'/' -f1)
        asset_name="${prefix}_${filename}"
    elif [[ "$dir_path" == *"assets"* ]]; then
        asset_name="assets_${filename}"
    else
        asset_name="$filename"
    fi

    echo "[+] 正在上传: $file_path -> $asset_name"
    
    # 执行上传 (--clobber 表示如果已存在则覆盖)
    # 语法: gh release upload <tag> <local_path>#<remote_name>
    gh release upload "$TAG" "$file_path#$asset_name" --clobber -R "$REPO"
    
    if [ $? -eq 0 ]; then
        echo "    成功!"
    else
        echo "    失败!"
    fi
}

# 处理传入的所有参数
if [ $# -eq 0 ]; then
    echo "用法: $0 <文件1> [文件2] ..."
    echo "示例: $0 devices/common/wild_boost_5.10.zip devices/fuxi/perfmgr.ko"
    exit 1
fi

for arg in "$@"; do
    upload_file "$arg"
done

echo "[*] 所有操作已完成。"
