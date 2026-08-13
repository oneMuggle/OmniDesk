"""Known-safe silent exception swallows whitelist.

Entries: (event_name, reason) tuples for ``except: pass`` blocks that are
deliberately silent (retry strategies, backward-compat fallbacks, ...).

Currently empty -- Task 10 populates real entries as it converts ``except:
pass`` blocks in the remaining smart_assistant modules. The Task 8 AST
guard counts ``except: pass`` regardless of this whitelist; this list only
feeds the ruff LOG rule (Task 12).
"""
from __future__ import annotations

ALLOWED_SILENT: set[tuple[str, str]] = set()
