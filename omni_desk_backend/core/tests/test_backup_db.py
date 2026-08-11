import gzip
import json
from unittest.mock import patch

from django.core.management import call_command


def test_backup_streams_pg_dump_and_writes_paired_metadata(tmp_path):
    output_dir = tmp_path / "batch"
    output_dir.mkdir()
    class FakeProcess:
        returncode = 0
        stdout = iter([b"CREATE TABLE sample(id integer);\n"])
        stderr = iter([])
        def wait(self): return self.returncode
    with patch("subprocess.Popen", return_value=FakeProcess()) as popen:
        call_command("backup_db", batch_id="test", output_dir=str(output_dir), verify=True, skip_media=True)
    assert "capture_output" not in popen.call_args.kwargs
    with gzip.open(output_dir / "database.sql.gz", "rb") as gz:
        assert gz.read().startswith(b"CREATE")
    metadata = json.loads((output_dir / "metadata.json").read_text())
    assert set(metadata) == {"upgrade_id", "channel", "source_version", "database_file", "media_file", "database_sha256", "media_sha256", "database_size", "media_size", "restore_verified", "created_at"}
    assert metadata["restore_verified"] is True
    assert (output_dir / "media.tar.gz").exists()
