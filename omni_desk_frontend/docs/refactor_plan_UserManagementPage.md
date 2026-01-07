# 重构计划：`UserManagementPage.jsx`

## 1. 目标文件

- **路径:** `omni_desk_frontend/src/features/user/pages/UserManagementPage.jsx`

## 2. 重构原因

该文件使用了 Ant Design (antd) 中已弃用的 `Tabs.TabPane` 组件。为了遵循最新的 antd API 规范、消除浏览器控制台的警告并提高代码的可维护性，需要将其重构为使用 `Tabs` 组件的 `items` 属性。

## 3. 详细重构步骤

### 步骤一：移除废弃的 `TabPane` 引入

在文件顶部，找到并删除对 `TabPane` 的解构赋值。

**原始代码 (第 11 行):**
```javascript
const { TabPane } = Tabs;
```

**操作:**
直接删除此行代码。

### 步骤二：创建 `items` 属性来定义选项卡

在 `UserManagementPage` 组件内部，`return` 语句之前，创建一个 `tabItems` 数组。这个数组将包含每个选项卡的配置信息。

### 步骤三：迁移 `TabPane` 的内容到 `items` 数组

将现有的两个 `TabPane` 组件转换为 `tabItems` 数组中的两个对象。每个对象都应包含 `key`、`label` 和 `children` 属性。

**原始代码 (第 449-461 行):**
```jsx
<Tabs defaultActiveKey="1">
    <TabPane tab="用户列表" key="1">
        <Table
            columns={userColumns}
            dataSource={users}
            rowKey="id"
            pagination={{ pageSize: 10 }}
        />
    </TabPane>
    <TabPane tab="用户组与权限" key="2">
        <GroupPermissionManager groups={groups} fetchGroups={fetchGroups} />
    </TabPane>
</Tabs>
```

**修改后的 `tabItems` 数组定义:**
```javascript
const tabItems = [
  {
    key: '1',
    label: '用户列表',
    children: (
      <Table
        columns={userColumns}
        dataSource={users}
        rowKey="id"
        pagination={{ pageSize: 10 }}
      />
    ),
  },
  {
    key: '2',
    label: '用户组与权限',
    children: <GroupPermissionManager groups={groups} fetchGroups={fetchGroups} />,
  },
];
```

### 步骤四：更新 `Tabs` 组件的用法

使用新的 `items` 属性来渲染 `Tabs` 组件。

**修改后的 `Tabs` 组件:**
```jsx
<Tabs defaultActiveKey="1" items={tabItems} />
```

## 4. 最终代码预览

重构完成后，`UserManagementPage` 组件的 `return` 部分将如下所示：

```jsx
const UserManagementPage = () => {
    // ... (组件现有 hooks 和逻辑)

    const tabItems = [
      {
        key: '1',
        label: '用户列表',
        children: (
          <Table
            columns={userColumns}
            dataSource={users}
            rowKey="id"
            pagination={{ pageSize: 10 }}
          />
        ),
      },
      {
        key: '2',
        label: '用户组与权限',
        children: <GroupPermissionManager groups={groups} fetchGroups={fetchGroups} />,
      },
    ];

    if (loading) {
        // ... (loading 状态)
    }

    return (
        <div style={{ padding: '24px' }}>
            <h1>管理员面板</h1>
            <Card>
                <Tabs defaultActiveKey="1" items={tabItems} />
            </Card>
        </div>
    );
};