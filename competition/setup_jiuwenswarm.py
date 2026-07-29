#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JiuwenSwarm 源码修改脚本
将 FinAssistant 金融分析 Skills 安装到 JiuwenSwarm 源码中

用法:
    python competition/setup_jiuwenswarm.py [--jiuwen-path D:\jiuwenswarm]
"""
import os
import sys
import shutil
import argparse


COMPETITION_DIR = os.path.dirname(os.path.abspath(__file__))
JIUWEN_SKILLS_DIR_TEMPLATE = "{jiuwen_path}/jiuwenswarm/resources/agent/workspace/skills"

# 需要安装的 Skills
SKILLS = [
    "stock-fundamental-analysis",
    "stock-valuation-analysis",
    "stock-technical-analysis",
    "financial-anomaly-detection",
    "portfolio-construction",
    "investment-report-generation",
    "financial-analysis-team",
]


def install_skills(jiuwen_path):
    """将 Skills 安装到 JiuwenSwarm 源码"""
    jiuwen_skills = JIUWEN_SKILLS_DIR_TEMPLATE.format(jiuwen_path=jiuwen_path)
    src_base = os.path.join(COMPETITION_DIR, "jiuwenswarm-skills")

    if not os.path.exists(src_base):
        print(f"错误: 源目录不存在: {src_base}")
        return False

    os.makedirs(jiuwen_skills, exist_ok=True)

    installed = 0
    for skill_name in SKILLS:
        src = os.path.join(src_base, skill_name)
        dst = os.path.join(jiuwen_skills, skill_name)

        if not os.path.exists(src):
            print(f"  跳过 {skill_name}: 源目录不存在")
            continue

        # 删除旧版本
        if os.path.exists(dst):
            shutil.rmtree(dst)

        # 复制新版本
        shutil.copytree(src, dst)
        installed += 1
        print(f"  已安装: {skill_name}")

    print(f"\n共安装 {installed}/{len(SKILLS)} 个 Skills 到:")
    print(f"  {jiuwen_skills}")
    return True


def make_gittrackable(jiuwen_path):
    """修改 .gitignore 使 Skills 可被 git 追踪"""
    gitignore = os.path.join(jiuwen_path, ".gitignore")

    if not os.path.exists(gitignore):
        print("警告: .gitignore 不存在，跳过")
        return

    with open(gitignore, 'r', encoding='utf-8') as f:
        content = f.read()

    # 检查是否已经处理过
    if "# JiuwenSwarm Skills (competition)" in content:
        print(".gitignore 已包含 Skills 排除规则，跳过")
        return

    # 在 workspace/ 忽略规则后面添加例外
    old_line = "jiuwenswarm/resources/agent/workspace/"
    new_lines = old_line + "\n"

    # 添加每个 skill 的排除规则
    for skill_name in SKILLS:
        new_lines += f"!jiuwenswarm/resources/agent/workspace/skills/{skill_name}/\n"

    content = content.replace(old_line, new_lines)

    with open(gitignore, 'w', encoding='utf-8') as f:
        f.write(content)

    print("已修改 .gitignore，Skills 可被 git 追踪")


def main():
    parser = argparse.ArgumentParser(description='安装金融分析 Skills 到 JiuwenSwarm')
    parser.add_argument('--jiuwen-path', default=r'D:\jiuwenswarm',
                        help='JiuwenSwarm 仓库根目录')
    args = parser.parse_args()

    print("=" * 60)
    print("JiuwenSwarm 源码修改 — 安装金融分析 Skills")
    print("=" * 60)

    # 1. 安装 Skills
    print("\n[Step 1] 安装 Skills...")
    if not install_skills(args.jiuwen_path):
        sys.exit(1)

    # 2. 修改 .gitignore
    print("\n[Step 2] 修改 .gitignore...")
    make_gittrackable(args.jiuwen_path)

    # 3. 验证
    print("\n[Step 3] 验证安装...")
    jiuwen_skills = JIUWEN_SKILLS_DIR_TEMPLATE.format(jiuwen_path=args.jiuwen_path)
    for skill_name in SKILLS:
        skill_md = os.path.join(jiuwen_skills, skill_name, "SKILL.md")
        if os.path.exists(skill_md):
            print(f"  OK: {skill_name}/SKILL.md")
        else:
            print(f"  MISSING: {skill_name}/SKILL.md")

    print("\n" + "=" * 60)
    print("完成！JiuwenSwarm 源码已修改。")
    print("=" * 60)


if __name__ == '__main__':
    main()
