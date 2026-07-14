# 12 各发布渠道部署指引

本文档面向运维/部署人员,说明如何识别、选择、升级不同发布渠道的 OmniDesk 离线包。

## 渠道识别

打开离线包目录或解压后的 `BUILD-MANIFEST.json`,看 `channel` 字段:

| channel 值 | 含义 | 适用环境 |
|---|---|---|
| `alpha` | 开发自测版 | 仅开发人员本地测试 |
| `beta` | 内测版 | 内测组指定环境 |
| `preview` | 预发布 (RC) | 客户/领导预览环境 |
| `stable` | 正式版 | 生产环境 |
| `hotfix` | 紧急修复 | 生产环境,已是 stable |

启动 banner 也会显示当前渠道:

```
==========================================
  OmniDesk 离线部署
  渠道: preview (v1.2.0-rc.1)
  版本: 1.2.0-rc.1
==========================================
```

## 选择合适的渠道

| 你要做的事 | 用哪个渠道 |
|---|---|
| 本地开发新功能 | alpha |
| 给内测组部署 | beta |
| 给客户/领导演示新版本 | preview (RC) |
| 上生产 | stable |
| 修生产环境的紧急 bug | hotfix(从 release 分支 cherry-pick) |

## 升级流程

### 升级到 stable(生产)

```bash
cd omnidesk-offline-v1.2.0/
./scripts/verify.sh           # 1. 校验完整性
./scripts/deploy.sh start     # 2. 启动(自动同步 IMAGE_TAG)
```

### 从 preview 升到 stable

```bash
cd omnidesk-offline-v1.2.0/
./scripts/upgrade.sh --target-channel=stable
```

### 应用 hotfix

```bash
cd omnidesk-offline-hotfix-v1.2.1/
./scripts/upgrade.sh --target-channel=stable
```

## 回滚

回滚备份按渠道隔离存放,默认只显示同渠道备份:

```bash
# 回滚到当前 stable 渠道的上一版本
./scripts/deploy.sh rollback

# 回滚到 preview 渠道的备份
./scripts/deploy.sh rollback --channel=preview
```

回滚时系统会列出该渠道下所有 `backup_v<VERSION>_<timestamp>.sql.gz`,选择序号即可。

## 常见问题

**Q: 怎么判断一个 GHCR tag 属于哪个渠道?**

A: 看 tag 后缀:
- 无后缀 = stable
- `-rc.N` = preview
- `-beta.N` = beta
- `-alpha.N` = alpha

**Q: 渠道可以回退吗?**

A: 不可以。`stable → beta` / `preview → alpha` 都会被 `upgrade.sh` 拒绝。

**Q: 旧版 `omnidesk-offline-v0.5.x/` 还能用吗?**

A: 可以。stable 渠道命名约定不变,旧包继续可用。