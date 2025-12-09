# 修正计划：开放 PostgreSQL 外部访问

## 1. 问题分析

*   `docker-compose.yml` 文件中的 `db` 服务（PostgreSQL）当前默认只监听 `localhost` 地址。
*   这导致从外部网络（例如您使用 Navicat 的电脑）通过服务器 IP 和映射的 `5433` 端口发起的连接被拒绝。

## 2. 解决方案

*   修改 `deployment/docker/docker-compose.yml` 文件。
*   为 `db` 服务添加一个 `command` 指令，强制 PostgreSQL 启动时监听所有网络接口（即 `0.0.0.0`）。

## 3. 实施步骤

*   在 `db` 服务的配置中，添加一行 `command: postgres -c listen_addresses='*'`。
*   修改后，需要通过 SSH 登录到您的服务器，在 `deployment/docker` 目录下，执行 `docker-compose down` 和 `docker-compose up -d` 来重新创建并启动服务，以使配置生效。

## 4. 可视化流程

```mermaid
graph TD
    A[开始: Navicat 连接失败] --> B{诊断: PG 监听 localhost};
    B --> C[解决方案: 修改配置, 监听所有 IP];
    C --> D[实施: 修改 `docker-compose.yml`];
    D --> E{在 `db` 服务中添加 `command: postgres -c listen_addresses='*'`};
    E --> F[应用: 在服务器上 `docker-compose down && docker-compose up -d`];
    F --> G[验证: 重新使用 Navicat 连接];
    G --> H[连接成功];