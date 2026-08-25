# deployment/docker 目录说明

## 环境变量文件(含敏感凭据,不入库)

| 文件 | 用途 | 是否入库 |
|---|---|---|
| `.env.example` | 开发环境模板 | ✅ 入库 |
| `.env` | 开发环境实际凭据 | ❌ 不入库 |
| `.env.production.example` | 生产环境模板 | ✅ 入库 |
| `.env.production` | 生产环境实际凭据 | ❌ 不入库 |

### 凭据存放约定

**推荐做法:真实凭据存放在仓库外**,例如 `~/.omni_desk/dev.env`,然后在 `deployment/docker/.env` 创建符号链接:

```bash
mkdir -p ~/.omni_desk
cp .env.example ~/.omni_desk/dev.env
# 编辑 ~/.omni_desk/dev.env 填入真实值
ln -s ~/.omni_desk/dev.env .env
```

这样 `docker compose up -d`(自动加载 `./.env`)照常工作,而真实密码/SECRET_KEY 永远不落在仓库目录内,即使 `git add -f` 也无法把仓库外文件提交进去。

**最低要求**:若直接把 `.env` 放在本目录,务必确认它未被 git 跟踪(`git check-ignore -v deployment/docker/.env`)。`.gitignore` 已有显式规则 `**/deployment/docker/.env` 双重保护。

### 历史教训

本文件的早期版本曾因误提交进入 git 历史(commit 07f89d5d 才删除)。当前磁盘上的凭据已轮换,与历史泄露值不同。新凭据请勿再放回仓库目录内。

## 部署测试与冒烟测试(2026-08 可靠性收尾)

源码模式与离线包模式共享同一组测试入口,使用统一的 `smoke_common.sh` helper 管理上下文、Compose、锁、run id、HTTP 和结果。

### 源码模式(Source Mode)

在 `deployment/docker/` 目录执行:

| 命令 | 作用 | Result semantics |
|---|---|---|
| `bash deploy_tests.sh http://localhost` | 启动 + 健康 + 协议 | 启动期检查,产物 ready 但未必 deep-tested |
| `bash smoke_tests.sh http://localhost` | 完整业务冒烟 + 协议 + 资源清理 | 部署后行为验证,默认 `SMOKE_STRICT=1` |
| `bash upgrade.sh` | 真实目标镜像切换 | 升级成功 + 失败自动 recovery |
| `bash rollback.sh` | 真实源镜像恢复 | 健康检查失败触发 `SAFE_STOPPED` |

### 离线包模式(Bundle Mode)

在离线包根目录执行:

| 命令 | 作用 | Result semantics |
|---|---|---|
| `./scripts/deploy.sh verify` | 校验结构(checksum / manifest / image tar) | 仅表示包结构完整,不代表服务已部署 |
| `./scripts/deploy.sh deploy-test` | 真实 `deploy_tests.sh` 启动验证 | 启动期检查 |
| `./scripts/deploy.sh smoke` | 真实 `smoke_tests.sh` 完整冒烟 | 部署行为验证 |

**关键差别**:
- `verify` = structural validation(只校验文件结构)
- `deploy-test` = startup behavior(真实启动并探测连通性)
- `smoke` = deployed behavior(完整业务路径 + 资源清理)
- `upgrade recovery` = source restoration(失败时真实回退源版本)

### 共享 Shell 测试

所有 shell 测试位于 `deployment/docker/tests/`,通过 `test_*.sh` 命名:

```bash
cd deployment/docker
for f in tests/test_*.sh; do bash "$f"; done
```

CI 中 `.github/workflows/ci.yml` 的 `shell-tests` job 持续执行这套测试。`test_ci_deployment_gate.sh` 还会校验 workflow 不含 fail-open 配置(`continue-on-error: true` 在 acceptance job、`SMOKE_STRICT=0`、`pull_policy: missing`)。

### Required 环境变量

部署验收默认(`SMOKE_*` 系):

```bash
SMOKE_STRICT=1                   # 任何 SKIP/WARN 必须使最终测试失败
SMOKE_ALLOW_NETWORK_SKIP=0       # 网络瞬态必须 FAIL,不允许降级为 SKIP
SMOKE_ALLOW_RATE_LIMIT_SKIP=0    # HTTP 429 必须 FAIL,不允许降级为 WARN
SMOKE_RUN_ID=<UTC秒>-<PID>       # 隔离 run id,避免 cleanup 串扰
```

升级与回滚额外:

```bash
SOURCE_BACKEND_IMAGE_TAG=v0.7.0-rc.1   # 升级失败回退源 tag
SOURCE_FRONTEND_IMAGE_TAG=v0.7.0-rc.1
COMPOSE_PROJECT_NAME=omnidesk-<channel>-<run_id>  # 隔离 compose project
```

### 隔离与清理

- 同一 `COMPOSE_PROJECT_NAME` 的 destructive smoke 通过 `flock` 互斥,锁冲突返回退出码 `2`
- 资源(数据库行 / media 文件 / output 临时文件)按 `SMOKE_RUN_ID` 前缀清理
- 清理必须显式校验 `SMOKE_RUN_ID` 前缀,不删历史 run 数据
- 成功 run 的 screenshot / trace / 临时 bundle 必须清理;只保留 `test-artifacts/` 中失败 diagnostics

## 相关文档

- 生产部署:`DEPLOYMENT_GUIDE_DOCKER.md`
- 离线部署:`docs/technical/23-offline-deployment.md`
- 设计 spec:`docs/superpowers/specs/2026-08-23-offline-smoke-reliability-design.md`
