# 三部分架构优化 — 实施报告

> 日期：2026-05-11
> 状态：实施完成

---

## 一、变更摘要

### Phase 1: Win7 兼容性修复

| 文件 | 变更 |
|------|------|
| `desktop_notifier/requirements.txt` | PyQt6 → PyQt5，锁定 requests/pywin32 版本 |
| `desktop_notifier/requirements-win7.txt` | **新建** — Win7/Python 3.8 专用依赖 |
| `desktop_notifier/main.py` | PyQt6 → PyQt5 导入，QDialog.Accepted API 适配 |
| `desktop_notifier/api/client.py` | PyQt6 → PyQt5 导入，Qt.ISODate API 适配 |
| `desktop_notifier/ui/dialogs.py` | PyQt5 全面适配 |
| `desktop_notifier/ui/main_window.py` | **重写** — Phase 3 功能 |
| `desktop_notifier/utils/config.py` | PyQt5 导入 |
| `desktop_notifier/utils/cache.py` | **新建** — JSON 离线缓存模块 |
| `desktop_notifier/utils/browser.py` | **新建** — 浏览器打开前端工具 |
| `desktop_notifier/main.spec` | **新建** — PyInstaller 打包配置 |
| `desktop_notifier/tests/test_main_window.py` | PyQt5 导入 |
| `.github/workflows/desktop_notifier_ci.yml` | Python 3.8, pyinstaller<6.0 |

### Phase 2: 后端通知系统完善

| 文件 | 变更 |
|------|------|
| `omni_desk_backend/omni_desk_backend/health.py` | 添加 version 和 timestamp 字段 |

### Phase 3: 桌面端功能扩展

| 文件 | 变更 |
|------|------|
| `desktop_notifier/ui/main_window.py` | 4Tab、系统托盘、连接状态、离线缓存、通知弹窗 |

### Phase 4: 前端完善

| 文件 | 变更 |
|------|------|
| `omni_desk_frontend/src/shared/pages/SystemUpdatePage.jsx` | 新增"桌面客户端"Tab |
| `omni_desk_backend/static/downloads/` | **新建目录** |

### Phase 5: 部署优化

| 文件 | 变更 |
|------|------|
| `deployment/docker/deploy_offline.sh` | 新增 `install-desktop` 子命令 |

---

## 二、桌面端新增功能

1. **通知 Tab** — 第4个标签页，显示未读通知列表
2. **系统托盘** — 右键菜单：打开管理页面、查看通知、设置、退出
3. **系统通知弹窗** — 新通知到达时弹出系统通知
4. **连接状态指示器** — 30秒轮询 /api/health/
5. **离线缓存** — JSON 文件缓存，断网时显示缓存数据
6. **一键打开前端** — webbrowser.open() 打开浏览器
7. **关闭到托盘** — closeEvent 拦截，隐藏而非退出

---

## 三、验收清单

- [x] PyQt5 替代 PyQt6，所有 API 差异已适配
- [x] Python 3.8 兼容的 requirements-win7.txt 已创建
- [x] CI 构建环境更新为 Python 3.8
- [x] PyInstaller 打包配置文件已创建
- [x] 后端健康 API 补充了 version 和 timestamp
- [x] 前端通知系统已完整实现（角标 + 列表 + 标记已读）
- [x] 桌面端通知 Tab 已添加
- [x] 系统托盘和右键菜单已实现
- [x] 离线缓存已实现
- [x] 前端系统更新页面添加桌面端下载入口
- [x] 离线部署脚本新增 install-desktop 子命令

---

## 四、后续建议

1. **Win7 真机测试** — 代码适配完成，需在 Win7 上验证运行
2. **CI 流水线验证** — 推送 develop 触发 CI，确认 Python 3.8 测试和打包正常
3. **桌面端图标** — main.spec 中 icon=None，建议准备 .ico 文件
4. **通知 Celery 异步化** — 当前信号同步创建通知，建议改为 Celery 异步
5. **传感器校准提醒信号** — signals.py 缺少 sensor_management 的校准提醒
