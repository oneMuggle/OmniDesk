# OmniDesk 开发规范

## 依赖管理
- 🔴 后端Python依赖必须通过`requirements.txt`文件管理，禁止使用`pip install`手动添加。
- 🔴 前端React版本必须严格使用`package.json`中定义的`latest`，禁止手动指定版本号。
- 🟡 必须定期运行`npm audit`和`pip-audit`来检查并修复已知的安全漏洞。

## 代码组织
- 🔴 新增的Django App必须在`omni_desk_backend/omni_desk_backend/settings/base.py`的`INSTALLED_APPS`列表中注册。
- 🔴 所有新的API路由必须在对应App的`urls.py`中定义，并统一包含在根`urls.py`的`/api/`路径下。
- 🟡 业务逻辑必须写在`views.py`中，数据验证和转换逻辑必须在`serializers.py`中实现。

## 数据库操作
- 🔴 禁止在代码中编写原生SQL查询，必须使用Django ORM进行所有数据库交互。
- 🔴 涉及多个写操作的视图函数，必须使用`@transaction.atomic()`装饰器或上下文管理器保证事务原子性。
- 🟡 复杂的数据库查询必须使用`select_related`和`prefetch_related`进行优化，以避免N+1问题。

## API开发
- 🔴 所有API端点必须通过DRF的权限类进行保护，禁止出现无任何权限控制的视图。
- 🔴 API的认证方式必须使用`rest_framework_simplejwt.authentication.JWTAuthentication`。
- 🟡 API分页大小必须通过`REST_FRAMEWORK`配置中的`PAGE_SIZE`（当前为10）进行全局管理。

## 错误处理与日志
- 🔴 业务逻辑错误必须通过引发`serializers.ValidationError`或`exceptions.APIException`来处理。
- 🟡 日志级别必须遵循`settings/base.py`中`LOGGING`的配置，开发中禁止使用`print()`。

## 测试要求
- 🔴 后端测试必须使用`pytest`框架，测试文件必须遵循`pytest.ini`中`test_*.py`或`*_tests.py`的命名规则。
- 🔴 前端测试必须使用`Jest`和`@testing-library/react`，测试命令为`npm test`。
- 🟡 提交代码前，必须确保所有测试用例通过。

## 环境配置
- 🔴 生产环境的敏感配置（如`SECRET_KEY`, 数据库密码）必须通过环境变量注入，禁止硬编码在代码中。
- 🟡 前端开发时，必须使用`package.json`中定义的`proxy`（"http://127.0.0.1:8000"）来代理API请求。

## 部署与CI/CD
- 🔴 生产镜像的构建必须使用`deployment/docker/omni_desk_backend/Dockerfile`和`omni_desk_frontend/Dockerfile`。
- 🟡 任何对`main`分支的推送都将触发`.github/workflows/build-and-push-images.yml`工作流，自动构建并发布新镜像。