"""Known-safe silent exception swallows whitelist.

Entries: (event_name, reason) tuples for ``except: pass`` blocks that are
deliberately silent (retry strategies, backward-compat fallbacks, ...).

The Task 8 AST guard counts ``except: pass`` regardless of this whitelist;
this list only feeds the ruff LOG rule (Task 12).
"""
from __future__ import annotations

ALLOWED_SILENT: set[tuple[str, str]] = {
    # office_download._cleanup: 下载后即删临时文件,删除失败无业务影响,
    # best-effort,日志噪音 > 价值,保留静默。
    ("smart_assistant.office_download.cleanup_failed", "best-effort temp file cleanup"),
}
