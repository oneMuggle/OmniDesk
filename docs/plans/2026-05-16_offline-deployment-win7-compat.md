# 内网离线部署镜像方案（含 Win7 客户端兼容）

> 日期：2026-05-16
> 状态：待审批
> 相关文档：[[win7_browser_compatibility_plan]]（旧 CRA 时代的 Win7 方案，已过时）

## 1. 背景与目标

### 1.1 现状

项目已有较完善的 Docker 构建和离线导出机制（`build_and_export.sh` + `deploy_offline.sh`），但存在以下缺口：

1. **基础镜像依赖外部注册表** — `python:3.11-slim-bookworm`、`node:20-alpine`、`nginx:stable-alpine`、`postgres:14-alpine`、`redis:7-alpine` 均需从 Docker Hub 拉取
2. **前端未针对 Win7 浏览器做兼容性处理** — React 18 已放弃 IE11，browserslist 目标为 `chrome >= 109`，Vite/esbuild 产物不保证 Win7 上 Chrome 109 完全兼容
3. **MathJax 内置 CDN 引用** — `tex-mml-chtml.js` 内含 `cdn.jsdelivr.net` 回退地址，内网中会失败
4. **构建产物未与导出流程解耦** — 构建机需联网拉取基础镜像后打包 `.tar`，无法做到"一次打包，多处离线部署"
5. **postgres.tar 仅 12KB** — 已导出的基础镜像中 postgres 包疑似损坏或不完整

### 1.2 目标

| 目标 | 说明 |
|------|------|
| **完全离线可部署** | 所有镜像、依赖、静态资源打包为一套离线介质，目标服务器无需任何互联网连接 |
| **Win7 客户端可访问** | Win7 上的 Chrome 109 / Edge 109 能正常加载和运行前端 |
| **一键部署** | 目标服务器上通过一个脚本完成镜像导入、服务启动、健康检查 |
| **可验证完整性** | 提供 SHA256 校验，确保离线介质在传输过程中未损坏 |

---

## 2. 风险评估

| 风险 | 等级 | 影响 | 缓解措施 |
|------|------|------|----------|
| React 18 不支持 IE11 | **高** | Win7 上的 IE11 完全无法使用 | 明确不支持 IE11，仅支持 Win7 上的 Chrome 109+ |
| Win7 TLS 1.2 默认未启用 | **中** | 若启用 HTTPS，Win7 可能无法建立连接 | HTTP 内网部署默认不启用 TLS；如需 HTTPS，要求客户安装 KB3140245 补丁 |
| Ant Design 5 使用了 `:has()` 等现代 CSS | **中** | 部分 UI 组件在旧浏览器中样式异常 | 构建前审查 Ant Design 兼容性，必要时降级或添加 polyfill |
| 基础镜像架构不匹配 | **中** | 目标服务器为 amd64 但拉取了 arm64 镜像 | 构建时显式指定 `--platform linux/amd64` |
| 离线包体积过大 | **低** | 传输困难 | 当前全量约 800MB-1.5GB，在可接受范围内 |

---

## 3. 技术方案

### 3.1 整体架构

```
┌─────────────────────────────────────────┐
│          构建机（可联网）                  │
│                                         │
│  1. 拉取并固定基础镜像                     │
│  2. 构建后端镜像（wheelhouse 离线安装）     │
│  3. 构建前端镜像（Win7 兼容构建）           │
│  4. 导出所有镜像为 .tar                    │
│  5. 打包离线部署介质                      │
└──────────────────┬──────────────────────┘
                   │  U盘/内网传输
                   ▼
┌─────────────────────────────────────────┐
│          目标服务器（完全离线）             │
│                                         │
│  1. 校验 SHA256                         │
│  2. docker load 导入镜像                 │
│  3. docker-compose 启动                  │
│  4. 健康检查 + 冒烟测试                   │
└─────────────────────────────────────────┘
```

### 3.2 离线包内容清单

```
omnidesk-offline-v{VERSION}/
├── images/                          # Docker 镜像
│   ├── omni-desk-backend.tar
│   ├── omni-desk-frontend.tar
│   ├── postgres-14-alpine.tar
│   ├── redis-7-alpine.tar
│   └── nginx-stable-alpine.tar
├── scripts/                         # 部署脚本
│   ├── deploy.sh                    # 一键部署入口
│   ├── verify.sh                    # 完整性校验
│   ├── rollback.sh                  # 回滚脚本
│   └── backup.sh                    # 备份脚本
├── compose/                         # docker-compose 配置
│   └── docker-compose.offline.yml
├── config/                          # 配置文件模板
│   ├── .env.production.template     # 环境变量模板
│   └── nginx.conf                   # 前端 Nginx 配置
├── VERSION                          # 版本号
├── CHECKSUMS.sha256                 # 全量校验和
├── BUILD-MANIFEST.json              # 构建元信息
└── README.md                        # 部署说明
```

### 3.3 前端 Win7 兼容性方案

#### 3.3.1 浏览器支持矩阵

| 浏览器 | 支持 | 说明 |
|--------|------|------|
| Chrome 109 (Win7) | ✅ | 明确支持，最后支持 Win7 的 Chrome 版本 |
| Edge 109 (Win7) | ✅ | 基于 Chromium，与 Chrome 109 同源 |
| IE 11 (Win7) | ❌ | React 18 已放弃支持，不投入资源 |

#### 3.3.2 构建配置变更

**a) `omni_desk_frontend/package.json` — browserslist 调整**

```json
"browserslist": {
    "production": [
        "chrome >= 109"
    ],
    "development": [
        "last 1 chrome version"
    ]
}
```

移除 `">0.2%"`、`"not dead"`、`"not op_mini all"` 等模糊目标，明确锁定 `chrome >= 109`。

**b) `omni_desk_frontend/vite.config.js` — 构建目标**

```javascript
export default defineConfig({
  build: {
    target: 'chrome109',  // 从默认 es2020 降级
    outDir: 'build',
    sourcemap: true,
    // ...
  }
})
```

Vite 默认 `target: 'es2020'`，Chrome 109 支持 ES2020 大部分特性，但需确认：
- `es2020` 包含 optional chaining `?.` 和 nullish coalescing `??` — Chrome 109 ✅ 支持
- 若有 `top-level await` — Chrome 109 ✅ 支持（Chrome 89+）

**结论：`target: 'chrome109'` 是安全的**，esbuild 会自动处理不兼容语法。

**c) `core-js` polyfill 注入**

在 `omni_desk_frontend/src/main.jsx` 顶部添加：

```javascript
import 'core-js/stable';
// 其余 imports...
```

确保运行时 API（如 `Promise`、`Array.prototype.at`、`Object.hasOwn` 等）在 Chrome 109 上可用。Chrome 109 已支持绝大多数现代 API，`core-js` 作为保险。

**d) MathJax CDN 本地化**

审查 `public/static/js/mathjax/tex-mml-chtml.js` 中的 `cdn.jsdelivr.net` 引用：
- 这些是 MathJax 运行时动态加载的辅助组件（SRE 语音引擎）
- 方案：在 MathJax 配置中禁用 SRE 或将其静态资源下载到 `public/static/js/mathjax/sre/` 目录

修改 `index.html` 中的 MathJax 配置：

```html
<script>
window.MathJax = {
  sre: { speech: false },  // 禁用语音，避免 CDN 回退
  // 或指定本地路径
  loader: { load: [] }
};
</script>
```

#### 3.3.3 Nginx 兼容性配置

`omni_desk_frontend/nginx.conf` 中：
- 保持 `X-UA-Compatible` 响应头
- 若启用 HTTPS，确保 `ssl_protocols TLSv1.2 TLSv1.3;`（已配置）
- 添加 `AddHeader` 告知浏览器使用最新渲染引擎

### 3.4 后端离线构建方案

#### 3.4.1 基础镜像固定

在构建机上预先拉取并重新标记所有基础镜像：

```bash
# 拉取 amd64 架构的基础镜像
docker pull --platform linux/amd64 python:3.11-slim-bookworm
docker pull --platform linux/amd64 node:20-alpine
docker pull --platform linux/amd64 nginx:stable-alpine
docker pull --platform linux/amd64 postgres:14-alpine
docker pull --platform linux/amd64 redis:7-alpine

# 导出为基础镜像离线包
docker save python:3.11-slim-bookworm -o images/python-3.11-slim-bookworm.tar
docker save node:20-alpine -o images/node-20-alpine.tar
docker save nginx:stable-alpine -o images/nginx-stable-alpine.tar
docker save postgres:14-alpine -o images/postgres-14-alpine.tar
docker save redis:7-alpine -o images/redis-7-alpine.tar
```

#### 3.4.2 构建流程增强

现有 `build_and_export.sh` 已实现 wheelhouse 离线安装。需要增强：

1. **构建前预加载基础镜像** — 若本地不存在，先从 `.tar` 导入
2. **架构锁定** — 所有 `docker build` 添加 `--platform linux/amd64`
3. **依赖完整性校验** — 构建后验证 `pip check` 无缺失依赖
4. **构建产物记录** — 生成 `BUILD-MANIFEST.json` 包含每个镜像的 digest、大小、层数

### 3.5 docker-compose 离线配置

使用现有 `docker-compose.offline-standalone.yml` 作为基础，确认：
- `image:` 引用本地标签（非远程）
- `depends_on` 含健康检查条件
- 数据卷持久化配置正确
- 网络隔离配置

---

## 4. 实施步骤

### Phase 1: 前端 Win7 兼容性改造

- [x] 4.1.1 修改 `package.json` browserslist，锁定 `chrome >= 109`
- [x] 4.1.2 修改 `vite.config.js`，设置 `build.target = 'chrome109'`
- [x] 4.1.3 在 `index.jsx` 顶部注入 `core-js/stable` polyfill（已存在，无需修改）
- [x] 4.1.4 审查并修复 MathJax CDN 回退问题（禁用 SRE）
- [x] 4.1.5 审查 Ant Design 5 组件是否使用了 Chrome 109 不支持的 CSS/JS 特性（无 `:has()` 使用）
- [x] 4.1.6 本地构建验证 — 构建成功，耗时 20.52s
- [x] 4.1.7 更新 `nginx.conf` 添加 `X-UA-Compatible` 响应头

### Phase 2: 后端离线构建增强

- [x] 4.2.1 确认 `Dockerfile` 已使用 `--no-index --find-links` 离线安装
- [x] 4.2.2 确认 `requirements-prod.txt` 无任何 `--extra-index-url`
- [x] 4.2.3 在 `build_and_export.sh` 中添加 `pip check` 验证步骤

### Phase 3: 离线打包与部署脚本完善

- [x] 4.3.1 增强 `build_and_export.sh`：`--platform linux/amd64` 架构锁定 + `pip check` 验证
- [x] 4.3.2 创建离线包打包脚本 `package_offline_bundle.sh`
- [x] 4.3.3 创建离线包入口 `scripts/deploy.sh`（由 `package_offline_bundle.sh` 自动生成）
- [x] 4.3.4 创建 `verify.sh` 校验脚本
- [x] 4.3.5 创建 `.env.production.template` 环境变量模板

### Phase 4: 端到端验证

- [ ] 4.4.1 在构建机上执行完整构建 + 打包流程
- [ ] 4.4.2 模拟离线环境（断网或禁用 Docker 外部拉取）
- [ ] 4.4.3 在目标机器上执行一键部署
- [ ] 4.4.4 在 Win7 虚拟机（Chrome 109）中验证前端功能
- [ ] 4.4.5 验证后端 API 可达性
- [ ] 4.4.6 记录部署日志和问题

### Phase 5: 文档

- [ ] 4.5.1 编写《离线部署手册》（`docs/user-manual/`）
- [x] 4.5.2 更新 `VERSION`（0.1.0 → 0.2.0）和 `CHANGELOG.md`
- [x] 4.5.3 本计划文档即为实施记录

---

## 5. 依赖与前置条件

| 依赖 | 说明 |
|------|------|
| 构建机需能访问 Docker Hub 和 PyPI | 首次构建需要，后续可复用缓存 |
| Win7 测试环境 | Chrome 109 虚拟机或 BrowserStack 订阅 |
| Docker Buildx | 用于 `--platform` 跨架构构建 |

---

## 6. 时间估算

| Phase | 复杂度 | 预估时间 |
|-------|--------|----------|
| Phase 1: 前端 Win7 兼容 | 中 | 2-3 小时 |
| Phase 2: 后端离线构建增强 | 低 | 1 小时 |
| Phase 3: 离线打包脚本 | 中 | 3-4 小时 |
| Phase 4: 端到端验证 | 中 | 2-3 小时 |
| Phase 5: 文档 | 低 | 1 小时 |
| **合计** | | **9-12 小时** |

---

## 7. 关键决策点

### 7.1 IE11 支持

**决策：不支持 IE11**

- React 18 已完全移除 IE11 支持
- Ant Design 5 不支持 IE11
- 投入产出比极低
- 需与客户明确沟通：Win7 上使用 Chrome 109 是最低要求

### 7.2 HTTPS

**决策：默认 HTTP，HTTPS 可选**

- 内网环境通常不需要 TLS
- 若启用，需确保客户 Win7 安装了 KB3140245（启用 TLS 1.2）
- 在部署说明中明确标注此依赖

### 7.3 基础镜像选择

**决策：保持现有版本，不做升级**

- `python:3.11-slim-bookworm` — 稳定，wheelhouse 方案成熟
- `node:20-alpine` — 构建效率高
- `nginx:stable-alpine` — 体积小
- `postgres:14-alpine` — 与现有数据兼容
- `redis:7-alpine` — 稳定

若将来需要进一步缩小镜像体积，可考虑 `alpine` 变体或 `distroless` 基础镜像。
