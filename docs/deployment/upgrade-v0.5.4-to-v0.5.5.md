# v0.5.4 → v0.5.5 服务器升级 checklist

## 升级前检查

- [ ] 服务器当前跑 v0.5.4:`curl -s http://localhost/api/health/ | python3 -c "import json,sys; print(json.load(sys.stdin)['version'])"`
- [ ] 备份 DB:`cd /opt/omni-desk && ./deploy.sh exec backend python manage.py dumpdata > /backup/v0.5.4-dump.json`
- [ ] 备份 volumes(如果用 `docker volume`):`docker run --rm -v omni_desk_postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres-v0.5.4.tgz /data`
- [ ] 备份当前 `.env.production`(记录当前 IMAGE_TAG,部署后会用 `deploy.sh` 自动同步)

## 升级流程

### 1. 上传离线包

```bash
# 在本地(有 omnidesk-offline-v0.5.5.zip)
scp omnidesk-offline-v0.5.5.zip user@server:/tmp/
```

### 2. 在服务器解压 + 加载镜像

```bash
# SSH 到服务器
ssh user@server

# 解压
cd /opt/omni-desk  # 或部署目录
unzip /tmp/omnidesk-offline-v0.5.5.zip -d /opt/omni-desk/
cd omnidesk-offline-v0.5.5

# (可选) 备份当前 v0.5.4 .env.production(用于回滚)
cp config/.env.production /tmp/env.v0.5.4.backup
```

### 3. 跑 v0.5.5 deploy.sh start

```bash
./scripts/deploy.sh start
```

deploy.sh 会自动:
1. ✅ verify.sh 校验完整性(15/15 PASS)
2. ✅ 加载 v0.5.5 镜像
3. ✅ generate_env 检测 IMAGE_TAG 不一致 → 自动同步到 v0.5.5(本次新增)
4. ✅ 启动新容器(v0.5.5 镜像)
5. ✅ 等服务 healthy(最多 120s)
6. ✅ 冒烟测试

### 4. 验证升级成功

```bash
# 1. 检查容器跑 v0.5.5
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}"
# 期望: 5/5 容器 IMAGE 包含 v0.5.5

# 2. 检查 health endpoint
curl -s http://localhost/api/health/ | python3 -m json.tool
# 期望: "version": "0.5.5"

# 3. 验证数据保留(对比升级前用户数)
docker exec compose-db-1 psql -U omni_desk_user -d omni_desk -c "SELECT COUNT(*) FROM users_customuser;"
# 期望: 与升级前数字一致

# 4. 跑 migrate
./scripts/deploy.sh exec backend python manage.py migrate --noinput
# 期望: "No migrations to apply"(v0.5.4 → v0.5.5 无 schema 变化)
```

### 5. 跑 collectstatic(可选)

```bash
./scripts/deploy.sh exec backend python manage.py collectstatic --noinput
```

### 6. 浏览器实测

访问 `http://服务器IP/`,用 admin 登录,验证:
- 登录正常
- 人员管理、会议室、传感器、项目等页面正常显示
- 新用户注册功能正常(测试 JsonResponse 错误格式)
- 18 字符身份证注册(EncryptedCharField 修复)

## 升级后确认

- [ ] `/api/health/` 返回 `version: 0.5.5`
- [ ] 5 个容器都跑 v0.5.5 镜像
- [ ] 用户数据完整保留
- [ ] 关键 fix 仍生效(JsonResponse 错误格式 + 18 字符身份证存储)
- [ ] backend 0 个 500 错误
- [ ] gunicorn 0 个 Permission denied

## 回滚(如需要)

```bash
# 停 v0.5.5 部署
cd /opt/omni-desk/omnidesk-offline-v0.5.5
./scripts/deploy.sh stop

# 恢复 v0.5.4 部署
cd /opt/omni-desk/omnidesk-offline-v0.5.4
cp /tmp/env.v0.5.4.backup config/.env.production
./scripts/deploy.sh start

# 如需要,恢复 DB 备份
```

## v0.5.4 → v0.5.5 关键变更

1. **deploy.sh generate_env IMAGE_TAG 自动同步**(本次新增)
   - 升级时不用再手动 sed 改 IMAGE_TAG
   - 升级流程简化

2. **其他 14 个 fix 已经在 v0.5.4 中** — v0.5.5 主要是 deploy.sh 体验改进,无新业务功能

## 联系

- 仓库:https://github.com/oneMuggle/OmniDesk
- v0.5.5 release:https://github.com/oneMuggle/OmniDesk/releases/tag/untagged-155a49f7c7ec66e39c32
- 上游问题:issue 跟踪
