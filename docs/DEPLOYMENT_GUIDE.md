# Docker 镜像自动化构建和部署指南

## 配置说明

### 文件结构
```
.
├── build.sh            # 镜像构建脚本
├── .env                # 环境变量配置
├── docker-compose.yml  # 服务编排配置
└── DEPLOYMENT_GUIDE.md # 本指南
```

### 环境变量配置 (.env)
```bash
# Docker镜像配置
DOCKER_USER=oneMuggle           # Docker Hub用户名
FRONTEND_VERSION=1.0.0          # 前端镜像版本 
BACKEND_VERSION=1.0.0           # 后端镜像版本
```

## 使用流程

### 1. 初始设置
```bash
# 添加执行权限
chmod +x build.sh

# 登录Docker Hub
docker login
```

### 2. 构建和推送镜像
```bash
# 构建并推送镜像到Docker Hub
./build.sh [版本号] oneMuggle

# 示例: 构建v1.1.0版本
./build.sh 1.1.0 oneMuggle
```

### 3. 更新部署
```bash
# 更新.env文件中的版本号
vim .env  # 修改FRONTEND_VERSION和BACKEND_VERSION

# 启动/更新服务
docker-compose up -d
```

## 维护说明

### 版本更新流程
1. 开发并测试新功能
2. 确定新版本号(遵循语义化版本)
3. 执行构建脚本推送新镜像
4. 更新.env文件版本号
5. 重新部署服务

### 回滚操作
```bash
# 修改.env文件回退到旧版本
vim .env

# 重新部署
docker-compose up -d
```

## 注意事项
1. 确保构建前已提交所有代码变更
2. 版本号变更后务必更新.env文件
3. 生产环境建议使用特定版本号而非latest
