# 替代部署方案

> ⚠️ **本章节自 v0.7.0 起仅作历史参考。**
>
> 原文中提及的 Railway 云部署方案已不再维护(详见 git 历史 `docs/user-manual/railway_deployment.md`,文件已删除)。OmniDesk 当前推荐的生产部署方式为 **离线 / 内网 Docker Compose 部署**,详见 [各发布渠道部署指引](12-deployment-channels.md)。
>
> 选 Railway 的两个核心理由(免费额度小、不需备案)在新策略下都已不重要:
>
> 1. 内网环境部署项目,本来就不需要公网域名 / 不需要绕开备案
> 2. 项目对 Windows 7 客户端的兼容性要求(`omni_desk_frontend/browserslist`)使得 Railway 默认分配的 `*.railway.app` 域名对 IE11 / Chrome 109 浏览器存在风险(详见 [Win7 兼容性](../technical/22-win7-compatibility.md))
>
> 如确有公网演示需求,可考虑自建 Nginx 反向代理 + 离线 Docker 镜像部署,不走 Railway。
