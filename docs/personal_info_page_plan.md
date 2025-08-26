# 个人信息页面开发计划

## 概述

本计划旨在为“个人信息”页面添加新功能，包括查看和编辑个人资料（用户名、联系电话、邮箱）、上传头像以及修改密码。

## 详细步骤

### 后端修改

1.  **更新 `CustomUser` 模型:**
    *   在 `omni_desk_backend/users/models.py` 的 `CustomUser` 模型中添加一个 `avatar` 字段 (`ImageField`)，用于存储用户头像。

2.  **更新 `UserDetailSerializer`:**
    *   在 `omni_desk_backend/users/serializers.py` 的 `UserDetailSerializer` 中添加 `phone` 和 `avatar` 字段。

3.  **创建 `UserProfileUpdateView`:**
    *   在 `omni_desk_backend/users/views.py` 中，创建一个新的视图 `UserProfileUpdateView`，继承自 `generics.RetrieveUpdateAPIView`。
    *   该视图将使用 `UserDetailSerializer` 并配置为支持文件（头像）上传。

4.  **创建密码修改功能:**
    *   在 `serializers.py` 中创建 `ChangePasswordSerializer`，用于验证旧密码和新密码。
    *   在 `views.py` 中创建 `ChangePasswordView`，处理密码修改的逻辑。

5.  **更新 URL 配置:**
    *   在 `omni_desk_backend/users/urls.py` 中，为 `UserProfileUpdateView` 和 `ChangePasswordView` 添加新的 URL 路由。

6.  **配置媒体文件服务:**
    *   在 Django 的 `settings.py` 中配置 `MEDIA_URL` 和 `MEDIA_ROOT`，以确保在开发环境中可以正确处理和提供上传的图片。

### 前端修改

1.  **更新 `ProfilePage.jsx` 组件:**
    *   在 `omni_desk_frontend/src/components/ProfilePage.jsx` 中，添加头像显示和上传控件。
    *   添加一个表单，用于显示和编辑用户的个人信息（用户名、邮箱、联系电话）。
    *   添加一个独立的“修改密码”区域或模态框，包含旧密码、新密码和确认新密码的输入框。
    *   实现个人信息保存、密码修改和头像上传的逻辑，分别调用后端的相应接口。
    *   在操作成功或失败时，向用户提供清晰的反馈。

## 计划图

```mermaid
graph TD
    A[开始] --> B{后端修改};
    B --> B1[更新 CustomUser 模型 (添加 avatar)];
    B1 --> B2[更新 UserDetailSerializer (添加 phone, avatar)];
    B2 --> B3[创建 UserProfileUpdateView (支持文件上传)];
    B3 --> B4[创建密码修改功能 (Serializer/View)];
    B4 --> B5[更新 URL 配置];
    B5 --> B6[配置媒体文件服务];
    B6 --> C{前端修改};
    C --> C1[更新 ProfilePage.jsx];
    C1 --> C2[添加头像上传/显示];
    C2 --> C3[添加个人信息编辑表单];
    C3 --> C4[添加修改密码表单];
    C4 --> C5[实现所有更新逻辑];
    C5 --> D[完成];

    subgraph 后端
        B1;
        B2;
        B3;
        B4;
        B5;
        B6;
    end

    subgraph 前端
        C1;
        C2;
        C3;
        C4;
        C5;
    end