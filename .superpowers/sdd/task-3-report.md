# Task 3 报告

## 文件
- `omni_desk_backend/core/management/commands/backup_db.py`
- `deployment/docker/backup.sh`
- `omni_desk_backend/core/tests/test_backup_db.py`

## 验证
- `bash -n deployment/docker/backup.sh`：通过。
- `conda run -n omni_desk pytest --ds=omni_desk_backend.settings.test omni_desk_backend/core/tests/test_backup_db.py -v`：未执行，环境不存在（`/home/fz/anaconda3/envs/omni_desk`）。

## Commit
- `1b6718a` feat: 建立离线升级成组备份与校验

## Concerns
- 必须在可用的 `omni_desk` conda 环境中补跑 pytest；当前环境缺失，因此不能宣称测试通过。
- 备份脚本假设 Compose 将容器备份目录映射到 `${OMNIDESK_BACKUP_ROOT}`；应由离线 bundle Compose 配置验证该映射。
