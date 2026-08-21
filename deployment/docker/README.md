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

## 相关文档

- 生产部署:`DEPLOYMENT_GUIDE_DOCKER.md`
- 离线部署:`docs/technical/23-offline-deployment.md`
