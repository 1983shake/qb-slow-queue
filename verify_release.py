#!/usr/bin/env python3
"""交付前一致性校验：qbslowqueue/__init__.py ↔ Dockerfile ↔ docker-compose.yml。

校验项：
1. __init__.py 字段完整（__version__ / __release_status__ / __test_sequence__ / __docker_tag__）。
2. __docker_tag__ 与发行状态一致：
   - test：含 -test.N 且 __test_sequence__ == N，并包含 __version__；
   - formal：不含 -test.N，且 __test_sequence__ == 0。
3. docker-compose.yml 的 image 字段引用 ${QB_IMAGE_TAG} 变量（版本从 __init__.py 派生）。
4. Dockerfile 未硬编码项目版本号（版本来源只能是 __init__.py）。
"""

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import qbslowqueue as pkg

REQUIRED = ("__version__", "__release_status__", "__test_sequence__", "__docker_tag__")
errors = []

# 1. 字段完整
for f in REQUIRED:
    if not hasattr(pkg, f):
        errors.append(f"__init__.py 缺少字段: {f}")

version = getattr(pkg, "__version__", "")
status = getattr(pkg, "__release_status__", "")
seq = getattr(pkg, "__test_sequence__", None)
tag = getattr(pkg, "__docker_tag__", "")

# 2. 状态与 tag 一致性
if status == "test":
    if not isinstance(seq, int) or seq <= 0:
        errors.append("测试版要求 __test_sequence__ 为 >=1 的整数")
    if f"-test.{seq}" not in tag:
        errors.append(f"__docker_tag__ 应包含测试标识 -test.{seq}")
    if version and version not in tag:
        errors.append("__docker_tag__ 应包含 __version__")
elif status == "formal":
    if seq != 0:
        errors.append("正式版要求 __test_sequence__ == 0")
    if re.search(r"-test\.\d+", tag):
        errors.append("正式版 __docker_tag__ 不得含 -test.N 标识")
else:
    errors.append(f"__release_status__ 必须为 'test' 或 'formal'，当前: {status!r}")

# 3. compose image 引用派生变量
compose_path = ROOT / "docker-compose.yml"
if not compose_path.exists():
    errors.append("缺少 docker-compose.yml")
else:
    compose = compose_path.read_text(encoding="utf-8")
    if "image:" not in compose:
        errors.append("docker-compose.yml 缺少 image 字段")
    elif "QB_IMAGE_TAG" not in compose:
        errors.append("docker-compose.yml 的 image 未引用 ${QB_IMAGE_TAG}（版本应从 __init__.py 派生）")

# 4. Dockerfile 无硬编码项目版本号
dockerfile_path = ROOT / "Dockerfile"
if dockerfile_path.exists():
    dockerfile = dockerfile_path.read_text(encoding="utf-8")
    if version and version in dockerfile:
        errors.append("Dockerfile 不应硬编码项目版本号（版本来源应为 __init__.py）")

if errors:
    print("❌ 校验失败：")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)

print("✅ 校验通过")
print(f"  版本:    {version}")
print(f"  状态:    {status}")
print(f"  测试序号: {seq}")
print(f"  镜像 tag: {tag}")
