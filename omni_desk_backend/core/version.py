"""Application version — source of truth for the deployment."""

import os
from pathlib import Path

# 多路径 fallback,按优先级排序:
#   1. 生产容器标准位置 /etc/omnidesk/VERSION(由 Dockerfile COPY,不受 compose bind mount 影响)
#   2. 开发环境相对路径(项目根在 parent.parent.parent)
#   3. 生产容器备用相对路径(项目根在 parent.parent,所有代码位于 /usr/src/app/)
#      注:若 compose 用 bind mount 覆盖 /usr/src/app,此路径会失效,优先使用 /etc/omnidesk/
_VERSION_CANDIDATES = [
    Path("/etc/omnidesk/VERSION"),
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
