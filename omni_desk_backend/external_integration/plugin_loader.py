import hashlib
import json
import logging
import os
import shutil
import subprocess
import tempfile
import zipfile

from django.conf import settings

logger = logging.getLogger(__name__)

PLUGIN_DIR = getattr(settings, 'PLUGIN_UPLOAD_DIR', os.path.join(settings.MEDIA_ROOT, 'plugins'))
DEFAULT_TIMEOUT = 30
DEFAULT_MEMORY_LIMIT_MB = 256


def compute_file_hash(file_obj, algorithm='sha256'):
    """计算文件的 SHA-256 哈希"""
    h = hashlib.new(algorithm)
    for chunk in file_obj.chunks():
        h.update(chunk)
    return h.hexdigest()


def extract_plugin_zip(uploaded_file):
    """解压插件 zip 文件到临时目录，返回目录路径"""
    tmp_dir = tempfile.mkdtemp(prefix='plugin_extract_')
    zip_path = os.path.join(tmp_dir, 'upload.zip')
    with open(zip_path, 'wb') as f:
        for chunk in uploaded_file.chunks():
            f.write(chunk)
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for name in zf.namelist():
            if '..' in name or name.startswith('/'):
                raise ValueError(f'插件包含不安全的路径: {name}')
        zf.extractall(tmp_dir)
    os.remove(zip_path)
    return tmp_dir


def validate_manifest(manifest_data):
    """验证插件清单格式"""
    required_fields = ['name', 'version', 'entry_point', 'protocol']
    for field in required_fields:
        if field not in manifest_data:
            raise ValueError(f'插件清单缺少必填字段: {field}')
    if manifest_data.get('protocol') not in ('stdio',):
        raise ValueError(f'不支持的协议: {manifest_data["protocol"]}')
    return manifest_data


def execute_plugin(extract_dir, entry_point, input_data, timeout=None, memory_limit_mb=None):
    """通过子进程执行插件，stdin/stdout JSON 协议通信"""
    timeout = timeout or DEFAULT_TIMEOUT
    executable = os.path.join(extract_dir, entry_point.lstrip('./'))
    if not os.path.isfile(executable):
        raise FileNotFoundError(f'插件入口不存在: {executable}')

    os.chmod(executable, 0o750)  # B103: owner + group only, no world-execute
    input_json = json.dumps(input_data, ensure_ascii=False)
    env = os.environ.copy()
    env['PYTHONPATH'] = ''

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
        )
        elapsed_ms = int((time.time() - start) * 1000)

        stdout_data = None
        if proc.stdout.strip():
            try:
                stdout_data = json.loads(proc.stdout.strip())
            except json.JSONDecodeError:
                stdout_data = {'raw_output': proc.stdout.strip()}

        return proc.returncode, stdout_data, proc.stderr.strip(), elapsed_ms

    except subprocess.TimeoutExpired:
        elapsed_ms = int((time.time() - start) * 1000)
        return -1, None, f'插件执行超时 ({timeout}s)', elapsed_ms
    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        return -2, None, str(e), elapsed_ms


def cleanup_plugin_dir(extract_dir):
    """清理插件临时目录"""
    if os.path.exists(extract_dir):
        shutil.rmtree(extract_dir, ignore_errors=True)
