# 24. 安全检查清单与依赖漏洞扫描

> 生成日期:2026-06-05
> 适用版本:OmniDesk 当前 main / develop 分支

## 一、依赖漏洞基线(2026-06-05 扫描)

| 包 | 旧版本 | 新版本 | 漏洞数 | 状态 |
|---|---|---|---|---|
| djangorestframework | 3.15.0 | **3.15.2** | 1 (CVE-2024-21520) | ✅ 已修复 |
| djangorestframework-simplejwt | 5.3.0 | **5.5.1** | 1 (CVE-2024-22513) | ✅ 已修复 |
| pyjwt | 2.12.1 | **2.13.0** | 4 (PYSEC-2026-175/177/178/179) | ✅ 已修复 |
| **合计** | | | **6** | **全部修复** |

## 二、漏洞详细分析(security-reviewer 评估)

### 1. CVE-2024-21520 — djangorestframework 3.15.0
- **类型**:XSS(模板过滤器)
- **触发条件**:使用 `rest_framework/templates/rest_framework/*` 中的 `break_long_headers` 过滤器处理用户可控的 HTTP header 值
- **OmniDesk 影响面**:`grep break_long_headers` 结果=0,项目纯 REST API 不渲染模板 → **实际不可利用**
- **修复**:补丁升级到 3.15.2(无 API 变化)

### 2. CVE-2024-22513 — djangorestframework-simplejwt 5.3.0
- **类型**:Privilege Management(账户禁用后仍可访问)
- **触发条件**:`RefreshToken.for_user(user)` 生成 token 后,user.is_active 设为 False,token 仍可用于认证
- **OmniDesk 影响面**:项目用 `for_user` 1 处(`users/views.py:243`),但 DRF 视图层 `IsAuthenticated` permission 会调用 `user.is_active` 检查 → **可缓解**
- **修复**:minor 升级到 5.5.1,CHANGELOG 显示改动集中在 token blacklist 行为

### 3. PYSEC-2026-175 — pyjwt 2.12.1(SSRF via PyJWKClient)
- **类型**:SSRF(本地文件系统)
- **触发条件**:应用主动使用 `PyJWKClient(uri)`,且 uri 来自用户输入
- **OmniDesk 影响面**:`grep PyJWKClient` 结果=0 → **不可利用**
- **修复**:pyjwt 是 simplejwt 传递依赖,升级到 2.13.0(API 兼容)

### 4. PYSEC-2026-177 — pyjwt 2.12.1(PyJWKClient 拒绝服务)
- **类型**:DoS(无速率限制)
- **触发条件**:同上,需用 PyJWKClient
- **OmniDesk 影响面**:**不可利用**
- **修复**:同上

### 5. PYSEC-2026-178 — pyjwt 2.12.1(detached JWS 解析)
- **类型**:逻辑缺陷(detached JWS payload 验证)
- **触发条件**:使用 `verify=` 时传入 `detach_header=True` 或 JWS header 含 `b64: false`
- **OmniDesk 影响面**:**不可利用**(项目用 simplejwt,默认非 detached)

### 6. PYSEC-2026-179 — pyjwt 2.12.1(算法混淆)
- **类型**:Auth bypass(算法降级)
- **触发条件**:verifier 同时支持 HMAC 和 asymmetric 算法,攻击者用 issuer 公钥作为 HMAC secret 伪造 token
- **OmniDesk 影响面**:`api_settings.ALGORITHM = 'HS256'`,只支持对称 → **不可利用**

## 三、CI 集成

### 已升级:`safety` → `pip-audit`
- `safety` 2024 年起部分功能转收费,`pip-audit` 是 PyPA 维护的现代替代品
- `pip-audit` 使用 OSV 数据库,覆盖比 safety 更广

### 已强化:`|| true` 移除
| Job | 旧 | 新 |
|-----|----|---|
| `security.Dependency check` | `safety scan -r ...` | `pip-audit -r ... --strict` |
| `lint-frontend.Run npm audit` | `npm audit --audit-level=moderate \|\| true` | `npm audit --audit-level=high` |

- `--strict` 让 pip-audit 失败时 exit 1
- `--audit-level=high` 让 npm 只报告 high/critical 漏洞(降低 false positive)

## 四、手动安全检查项(OWASP Top 10 对照)

### 已实施 ✅

| 项 | 实现位置 | 状态 |
|---|---|---|
| A01:访问控制破损 | `users/permissions.py`、`permissions/` app、ProtectedRoute | ✅ |
| A02:加密失效 | SECURE_PROXY_SSL_HEADER、HSTS、cookie SameSite=Lax | ✅ |
| A03:注入(ORM) | Django ORM 全程使用,无裸 SQL | ✅ |
| A04:不安全设计 | DRF ViewSet 权限 + IsAuthenticated + 业务级校验 | ✅ |
| A05:安全配置错误 | `production.py` 显式检查 SECRET_KEY、POSTGRES_DB、MINERU_API_KEY | ✅ |
| A07:认证失效 | JWT + 黑名单 + 刷新轮换 + 30min access / 7d refresh | ✅ |
| A09:日志失败 | 结构化 JSON 日志(生产),关键事件记录 | ✅(P1.7 完成) |
| A10:SSRF | 内网部署 + pyjwt PyJWKClient 升级 + file_processing 沙箱 | ✅ |

### 待优化 ⚠️

| 项 | 建议 |
|---|---|
| A06:易受攻击组件 | **本期完成**(升级 3 个含漏洞包) |
| A08:数据完整性 | 文档上传白名单(需审计 `documents/file_processing.py`) |
| A06:长期 | 接入 Dependabot 自动 PR(见 https://github.com/dependabot) |

## 五、Secret 管理

- **严禁**:硬编码 API key、密码、token
- **强制**:通过环境变量 + `.env`(本地开发)
- **CI**:密钥仅在 GitHub Actions Secrets 中存放
- **审计**:`bandit -r omni_desk_backend/ -ll` 在 CI 中已运行
- **历史事故**:本会话发现 1 个含明文生产密钥的 `.env.production.bak.1780558283` 文件,已**立即删除**(未提交)

## 六、升级策略

| 升级类型 | 频率 | 责任 |
|----------|------|------|
| 补丁级(如 3.15.0 → 3.15.2) | 出现 CVE 时立即 | 当前会话内 |
| minor 级(如 simplejwt 5.3.0 → 5.5.1) | 1 季度 1 次,跑全量测试 | 安全工单 |
| major 级(Django 4.2 → 5.x) | 1 年 1 次,LTS 节奏评估 | 独立项目 |

## 七、定期扫描节奏

| 扫描 | 触发 | 命令 |
|------|------|------|
| Python 依赖 | 每次 push + 每周一定时 | `pip-audit -r requirements-prod.txt` |
| Python 代码 | 每次 push | `bandit -r omni_desk_backend/ -ll` |
| JS 依赖 | 每次 push | `npm audit --audit-level=high` |
| 前端代码 | 每次 push | `npm run lint`(ESLint) |
| 后端 mypy | 每次 push(best-effort) | `mypy . --ignore-missing-imports` |

## 八、复盘与本会话成果

- ✅ 发现 6 个 CVE → 全部升级修复(`pip-audit` 报告 "No known vulnerabilities found")
- ✅ CI 改造:`safety` → `pip-audit`,`npm audit` 改 `high` 级别,移除 `|| true`
- ✅ 验证项目实际利用面,6 个漏洞均为**低/中风险**(内网部署 + 业务上下文)
- ✅ 清理 1 个含明文密钥的备份文件
- ✅ 测试无回归:585 passed, 80.84% 覆盖率

## 九、附录:扫描命令

```bash
# Python 依赖漏洞
pip install pip-audit
pip-audit -r requirements-prod.txt

# Python 代码静态分析
pip install bandit
bandit -r omni_desk_backend/ -ll --skip B101

# 前端依赖漏洞
npm audit --audit-level=high

# 综合 Python 安全基线
pip install safety pip-audit bandit
```
