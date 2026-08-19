"""
R4-A5: 插件加载器安全测试。

覆盖 execute_plugin 的两个加固点:
1. entry_point 路径白名单 — ../ 逃逸被拒绝
2. DEFAULT_MEMORY_LIMIT_MB 死配置修复 — RLIMIT_AS 经 preexec_fn 落地到子进程
"""
import os
import textwrap

import pytest

from external_integration.plugin_loader import execute_plugin


def _make_entry_script(extract_dir, name="entry.py", body=None):
    """在解压目录内创建可执行入口脚本,返回路径"""
    entry = os.path.join(extract_dir, name)
    body = body or textwrap.dedent(
        """\
        #!/usr/bin/env python3
        print("ok")
        """
    )
    with open(entry, "w") as f:
        f.write(body)
    os.chmod(entry, 0o700)
    return entry


@pytest.mark.django_db
class TestPluginLoaderSecurity:
    def test_entry_point_path_traversal_rejected(self, tmp_path):
        """entry_point 含 ../ 逃逸解压目录 → FileNotFoundError,不执行"""
        entry = _make_entry_script(str(tmp_path))
        with pytest.raises(FileNotFoundError):
            execute_plugin(
                extract_dir=str(tmp_path),
                entry_point="sub/../../" + os.path.basename(entry),
                input_data={},
            )

    def test_entry_point_absolute_path_rejected(self, tmp_path):
        """entry_point 为绝对路径(逃逸) → FileNotFoundError"""
        with pytest.raises(FileNotFoundError):
            execute_plugin(
                extract_dir=str(tmp_path),
                entry_point="/etc/passwd",
                input_data={},
            )

    def test_entry_point_missing_raises(self, tmp_path):
        """入口文件不存在 → FileNotFoundError"""
        with pytest.raises(FileNotFoundError):
            execute_plugin(str(tmp_path), "nope.py", {})

    def test_memory_limit_applied_to_subprocess(self, tmp_path):
        """RLIMIT_AS 经 preexec_fn 落地到子进程(死配置修复验证)。

        脚本读取 /proc/self/limits 打印 Max address space 行,
        断言限制值等于传入的 memory_limit_mb。
        """
        entry = _make_entry_script(
            str(tmp_path),
            body=textwrap.dedent(
                """\
                #!/usr/bin/env python3
                import os
                for line in open('/proc/self/limits'):
                    if line.startswith('Max address space'):
                        print(line.strip())
                        break
                """
            ),
        )
        returncode, stdout_data, stderr, _ = execute_plugin(
            extract_dir=str(tmp_path),
            entry_point=os.path.basename(entry),
            input_data={},
            memory_limit_mb=64,
        )
        assert returncode == 0, f"插件执行失败: stderr={stderr!r}"
        assert stdout_data is not None
        raw = (
            stdout_data.get("raw_output", "")
            if isinstance(stdout_data, dict)
            else str(stdout_data)
        )
        # 64 MB = 67108864 bytes
        assert "67108864" in raw, (
            f"RLIMIT_AS 未设置为 64MB, got stdout={raw!r}, stderr={stderr!r}"
        )

    def test_default_memory_limit_is_256mb(self, tmp_path):
        """不传 memory_limit_mb 时使用默认 256MB(校验默认配置生效)"""
        entry = _make_entry_script(
            str(tmp_path),
            body=textwrap.dedent(
                """\
                #!/usr/bin/env python3
                import os
                for line in open('/proc/self/limits'):
                    if line.startswith('Max address space'):
                        print(line.strip())
                        break
                """
            ),
        )
        returncode, stdout_data, stderr, _ = execute_plugin(
            extract_dir=str(tmp_path),
            entry_point=os.path.basename(entry),
            input_data={},
        )
        assert returncode == 0, f"插件执行失败: stderr={stderr!r}"
        raw = (
            stdout_data.get("raw_output", "")
            if isinstance(stdout_data, dict)
            else str(stdout_data)
        )
        # 256 MB = 268435456 bytes
        assert "268435456" in raw, (
            f"默认 RLIMIT_AS 未设置为 256MB, got stdout={raw!r}, stderr={stderr!r}"
        )
