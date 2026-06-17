# 29. 性能 Profiling(django-silk)

> 适用版本:OmniDesk v0.7+
> 关联: PR-3 feat/django-silk-dev

## 一、概述

django-silk 是 Django 官方推荐的 SQL profiling 工具,记录每个 HTTP 请求的 SQL 数量、耗时、慢查询。

**仅 dev/local 模式启用**,生产环境永不接入。

## 二、启用

```bash
export ENABLE_SILK=1
DJANGO_SETTINGS_MODULE=omni_desk_backend.settings.local python manage.py runserver
```

访问 `http://127.0.0.1:8000/silk/` 即可看到 profiling 面板。

## 三、典型使用场景

### 3.1 找慢查询

1. 触发慢 API(如列表端点)
2. 打开 silk 主页,按 "Time" 降序
3. 点击进入详情,看 SQL 列表与 EXPLAIN
4. 加 `select_related` / `prefetch_related` / 索引

### 3.2 找 N+1

1. 触发列表 API(如 `/api/documents/generated/`)
2. silk 详情看 SQL 数量:正常 ≤ 5,N+1 时 = N
3. 在对应 viewset 加 `select_related` / `prefetch_related`

### 3.3 找端点慢但 SQL 快的请求

1. silk 看 SQL 耗时占比
2. 若 SQL 占 < 30%,看 Python 代码侧(profile with silk)

## 四、配置项

见 `settings/local.py` 的 `SILKY_*` 配置:

| 配置 | 默认 | 说明 |
|------|------|------|
| `SILKY_PYTHON_PROFILER` | False | 是否启用 Python 代码级 profiling |
| `SILKY_MAX_REQUEST_BODY_SIZE` | 1024 | 请求体最大记录字节 |
| `SILKY_MAX_RESPONSE_BODY_SIZE` | 1024 | 响应体最大记录字节 |
| `SILKY_EXCLUDE_PATHS` | `["/health/", "/ready/"]` | 不记录的路径 |

## 五、生产禁用

- prod 设置文件(`settings/production.py`)不 import silk
- `requirements-prod.txt` 不含 django-silk
- 即使 `ENABLE_SILK=1` 在 prod 也无效(因为 `DEBUG=False` 短路)
