"""Application version — source of truth for the deployment."""

import os
from pathlib import Path

# 多路径 fallback:同时支持开发环境(项目根在 parent.parent.parent)
# 与生产容器(项目根在 parent.parent,所有代码位于 /usr/src/app/)
_VERSION_CANDIDATES = [
    Path(__file__).resolve().parent.parent.parent / "deployment" / "docker" / "VERSION",
    Path(__file__).resolve().parent.parent / "deployment" / "docker" / "VERSION",
]


def get_version() -> str:
    # 1. 优先读取 APP_VERSION_FILE 环境变量(由 docker-compose 注入,用于生产镜像补救)
    env_path = os.environ.get("APP_VERSION_FILE")
    if env_path:
        p = Path(env_path)
        if p.is_file():
            return p.read_text().strip()
    # 2. 候选路径列表(开发 + 容器)
    for path in _VERSION_CANDIDATES:
        if path.is_file():
            return path.read_text().strip()
    return "0.0.0-dev"
