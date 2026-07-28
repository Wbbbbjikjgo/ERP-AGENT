"""
技能下载工具 - 从URL下载技能包并解压到指定目录
用法: python download_skill.py --url <zip_url> --target <target_dir>
"""
import argparse
import os
import sys
import zipfile
import tempfile
import urllib.request
import shutil


def download_and_extract(url: str, target_dir: str) -> str:
    """下载zip并解压到目标目录，返回解压后的技能目录路径"""
    # 创建临时文件
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".zip")
    os.close(tmp_fd)

    try:
        print(f"[1/4] 下载技能包: {url}")
        urllib.request.urlretrieve(url, tmp_path)

        print(f"[2/4] 解压到: {target_dir}")
        os.makedirs(target_dir, exist_ok=True)
        with zipfile.ZipFile(tmp_path, "r") as zf:
            zf.extractall(target_dir)

        # 查找 SKILL.md
        print("[3/4] 验证技能结构...")
        skill_md_path = None
        for root, dirs, files in os.walk(target_dir):
            if "SKILL.md" in files:
                skill_md_path = os.path.join(root, "SKILL.md")
                break

        if not skill_md_path:
            raise ValueError("技能包中未找到 SKILL.md 文件")

        # 验证 frontmatter
        print("[4/4] 验证 frontmatter...")
        with open(skill_md_path, "r", encoding="utf-8") as f:
            content = f.read()

        if not content.startswith("---"):
            raise ValueError("SKILL.md 缺少 YAML frontmatter")

        required_fields = ["name", "description", "scope"]
        frontmatter = content.split("---")[1]
        for field in required_fields:
            if field not in frontmatter:
                raise ValueError(f"frontmatter 缺少必填字段: {field}")

        skill_dir = os.path.dirname(skill_md_path)
        print(f"✓ 技能下载成功: {skill_dir}")
        return skill_dir

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def main():
    parser = argparse.ArgumentParser(description="下载并安装技能包")
    parser.add_argument("--url", required=True, help="技能包ZIP下载地址")
    parser.add_argument("--target", required=True, help="目标解压目录")
    args = parser.parse_args()

    try:
        result = download_and_extract(args.url, args.target)
        print(f"\n技能安装完成: {result}")
    except Exception as e:
        print(f"\n✗ 安装失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
