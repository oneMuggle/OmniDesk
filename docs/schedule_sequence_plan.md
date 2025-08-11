# 排班顺序管理功能开发计划

## 1. 核心目标

实现一个可以预先定义、保存和调用“值班人员”和“值班领导”顺序的功能，以简化和加速排班流程。

## 2. 后端开发计划 (Django REST Framework)

### 2.1. 新建数据模型 (`models.py`)

创建两个新的模型来分别存储人员和领导的顺序：

*   **`PersonnelSequence`**: 用于存储值班人员的排序列表。
*   **`LeaderSequence`**: 用于存储值班领导的排序列表。

每个模型将包含以下字段：
*   `name`: 顺序的名称（例如，“日常轮班组”、“周末领导组”），方便用户识别和选择。
*   `sequence`: 一个 `JSONField`，用于存储一个有序的人员ID列表 (e.g., `[3, 1, 4, 2]`)。

### 2.2. 创建序列化器 (`serializers.py`)

为 `PersonnelSequence` 和 `LeaderSequence` 模型创建对应的序列化器，以便在API中进行数据转换。

### 2.3. 创建新的API视图 (`views.py`)

创建一个新的 `ViewSet`，提供对 `PersonnelSequence` 和 `LeaderSequence` 模型的增删改查（CRUD）功能。这将允许前端管理这些预设的顺序。

### 2.4. 修改排班生成逻辑 (`ScheduleViewSet` in `views.py`)

改造现有的 `generate_schedules` 方法：
*   它将接受 `personnel_sequence_id` 和 `leader_sequence_id` 作为新的参数。
*   后端逻辑会根据传入的ID，查找对应的顺序，并使用其中预设的人员列表来生成排班。
*   保留旧的 `personnel_order` 逻辑作为备用方案，以保持向后兼容性。

## 3. 前端开发计划 (React)

### 3.1. 开发顺序管理界面

创建一个新的管理页面或弹窗，用户可以在这里：
*   查看所有已保存的人员和领导顺序。
*   创建新的顺序：为顺序命名，并从人员列表中选择人员，通过拖拽等方式进行排序。
*   编辑或删除已有的顺序。

### 3.2. 优化排班生成界面

在现有的“生成排班”功能中，将手动选择和排序人员的复杂操作替换为两个简单的下拉菜单：
*   一个下拉菜单用于选择“值班人员顺序”。
*   另一个下拉菜单用于选择“值班领导顺序”。
*   用户选择好顺序后，点击“生成”按钮，前端将调用新的API，并传递所选顺序的ID。

## 4. 计划示意图

```mermaid
graph TD
    subgraph Backend (DRF)
        A[1. 定义新模型: PersonnelSequence, LeaderSequence] --> B[2. 创建序列化器];
        B --> C[3. 创建用于管理顺序的ViewSet];
        C --> D[4. 修改 generate_schedules 视图以使用Sequence ID];
    end

    subgraph Frontend (React)
        E[5. 创建顺序管理UI] --> F[6. 实现对顺序的增删改查];
        F --> G[7. 修改排班生成UI];
        G --> H[8. 使用下拉菜单选择顺序];
        H --> D;
    end

    subgraph User Interaction
        I[用户预先定义并保存顺序] --> E;
        J[用户选择预设顺序以生成排班] --> G;
    end

    D --> K[成功生成并保存排班];

    style A fill:#f9f,stroke:#333,stroke-width:2px
    style B fill:#f9f,stroke:#333,stroke-width:2px
    style C fill:#f9f,stroke:#333,stroke-width:2px
    style D fill:#f9f,stroke:#333,stroke-width:2px

    style E fill:#ccf,stroke:#333,stroke-width:2px
    style F fill:#ccf,stroke:#333,stroke-width:2px
    style G fill:#ccf,stroke:#333,stroke-width:2px
    style H fill:#ccf,stroke:#333,stroke-width:2px