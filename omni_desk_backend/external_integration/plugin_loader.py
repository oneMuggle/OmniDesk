import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from observability import get_logger
from pathlib import Path

from django.conf import settings

logger = get_logger(__name__, "external_integration.plugin_loader")

PLUGIN_DIR = getattr(settings, "PLUGIN_UPLOAD_DIR", os.path.join(settings.MEDIA_ROOT, "plugins"))
DEFAULT_TIMEOUT = 30
DEFAULT_MEMORY_LIMIT_MB = 256


def compute_file_hash(file_obj, algorithm="sha256"):
    """计算文件的 SHA-256 哈希"""
    h = hashlib.new(algorithm)
    for chunk in file_obj.chunks():
        h.update(chunk)
    return h.hexdigest()


def extract_plugin_zip(uploaded_file):
    """解压插件 zip 文件到临时目录，返回目录路径"""
    tmp_dir = tempfile.mkdtemp(prefix="plugin_extract_")
    zip_path = os.path.join(tmp_dir, "upload.zip")
    with open(zip_path, "wb") as f:
        for chunk in uploaded_file.chunks():
            f.write(chunk)
    with zipfile.ZipFile(zip_path, "r") as zf:
        # SECURITY: 检查路径遍历 (Zip Slip 攻击) - 使用 Path.is_relative_to() 避免前缀冲突 bug
        tmp_path_resolved = Path(tmp_dir).resolve()
        for name in zf.namelist():
            member_path = (Path(tmp_dir) / name).resolve()
            if not member_path.is_relative_to(tmp_path_resolved):
                raise ValueError(f"插件包含不安全的路径: {name}")
        zf.extractall(tmp_dir)
    os.remove(zip_path)
    return tmp_dir


def validate_manifest(manifest_data):
    """验证插件清单格式"""
    required_fields = ["name", "version", "entry_point", "protocol"]
    for field in required_fields:
        if field not in manifest_data:
            raise ValueError(f"插件清单缺少必填字段: {field}")
    if manifest_data.get("protocol") not in ("stdio",):
        raise ValueError(f"不支持的协议: {manifest_data['protocol']}")
    return manifest_data


def execute_plugin(extract_dir, entry_point, input_data, timeout=None, memory_limit_mb=None):
    """通过子进程执行插件，stdin/stdout JSON 协议通信"""
    timeout = timeout or DEFAULT_TIMEOUT
    memory_limit_mb = memory_limit_mb or DEFAULT_MEMORY_LIMIT_MB

    # SECURITY: 入口路径白名单 — resolve 后必须位于解压目录内,防止 ../ 逃逸
    # (旧的 entry_point.lstrip("./") 只清前导字符,拦不住 "sub/../../evil" 形式)
    extract_dir_resolved = Path(extract_dir).resolve()
    entry_path = (extract_dir_resolved / entry_point).resolve()
    if not entry_path.is_relative_to(extract_dir_resolved):
        raise FileNotFoundError(f"插件入口路径不合法(必须位于解压目录内): {entry_point}")
    if not entry_path.is_file():
        raise FileNotFoundError(f"插件入口不存在: {entry_point}")
    executable = str(entry_path)

    os.chmod(executable, 0o700)  # owner read/write/execute only
    input_json = json.dumps(input_data, ensure_ascii=False)
    env = os.environ.copy()
    env["PYTHONPATH"] = ""

    def _apply_resource_limits():
        """preexec_fn: fork 后 exec 前落地资源限制。

        仅调用 resource.setrlimit(纯进程内状态,无锁/无 IO),
        在多线程 worker 下使用是安全的。
        落地 DEFAULT_MEMORY_LIMIT_MB(原为死配置)与 CPU 超时。
        """
        import resource

        limit_bytes = memory_limit_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (limit_bytes, limit_bytes))
        resource.setrlimit(resource.RLIMIT_CPU, (timeout + 10, timeout + 10))

    import time

    start = time.time()
    try:
        proc = subprocess.run(
            [executable],
            input=input_json,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            cwd=extract_dir,
            preexec_fn=_apply_resource_limits,
        )
        elapsed_ms = int((time.time() - start) * 1000)

        stdout_data = None
        if proc.stdout.strip():
            try:
                stdout_data = json.loads(proc.stdout.strip())
            except json.JSONDecodeError:
                stdout_data = {"raw_output": proc.stdout.strip()}

        return proc.returncode, stdout_data, proc.stderr.strip(), elapsed_ms

    except subprocess.TimeoutExpired:
        elapsed_ms = int((time.time() - start) * 1000)
        return -1, None, f"插件执行超时 ({timeout}s)", elapsed_ms
    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        return -2, None, str(e), elapsed_ms


def cleanup_plugin_dir(extract_dir):
    """清理插件临时目录"""
    if os.path.exists(extract_dir):
        shutil.rmtree(extract_dir, ignore_errors=True)
