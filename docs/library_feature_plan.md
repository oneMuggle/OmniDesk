# 书库功能开发与重构计划

## 1. 项目目标

本次更新的目标是重构现有的书籍阅读功能，并创建一个全新的“书库”页面，以提供更丰富、更具吸引力的用户体验。

主要任务包括：
-   创建一个新的“书库”页面，以卡片形式展示所有书籍及其封面、简介和标签。
-   将现有的书籍阅读页面改造为动态页面，能够根据URL加载指定的书籍。
-   增强后端，支持书籍封面、作者、简介、出版日期和标签等详细信息。
-   在主导航栏中添加“书库”页面的入口。
-   **新增Web端书籍导入功能**：提供用户友好的Web界面来上传和导入Markdown书籍，支持ZIP文件导入和独立图片文件上传。
-   **新增Web端书籍编辑与发布功能**：允许用户通过Web界面修改已导入书籍的章节内容。
-   **新增Web端书籍导出功能**：允许用户将已导入的书籍导出为Markdown格式的文件。
-   **Markdown渲染优化**：确保Markdown中的图片和数学公式能正确、美观地显示。
-   **多级标题解析与展示**：在后端解析Markdown的多级标题结构，并在前端生成可导航的嵌套目录。
-   **图片信息结构化存储**：在导入时提取图片的详细信息并存储。
-   **精细化页面布局**：书籍阅读页面独立于主应用布局，而管理功能页面（导入、编辑、导出）则集成在主应用布局中。

---

## 2. 后端增强

### 2.1. 数据模型更新 (`models.py`)

1.  **`Tag` 模型 (新增)**: 创建一个独立的模型来管理标签。
    ```python
    class Tag(models.Model):
        name = models.CharField(max_length=50, unique=True, verbose_name="标签名")
    ```

2.  **`Book` 模型 (更新)**: 为 `Book` 模型添加更丰富的字段，并与 `Tag` 模型建立多对多关系。
    ```python
    class Book(models.Model):
        title = models.CharField(max_length=200, verbose_name="书名")
        author = models.CharField(max_length=100, blank=True, verbose_name="作者")
        description = models.TextField(blank=True, verbose_name="简介")
        cover_image = models.ImageField(upload_to='covers/', blank=True, null=True, verbose_name="封面图片")
        publication_date = models.DateField(blank=True, null=True, verbose_name="出版日期")
        tags = models.ManyToManyField(Tag, blank=True, related_name='books', verbose_name="标签")
        created_at = models.DateTimeField(auto_now_add=True, verbose_name="添加时间")
    ```

3.  **`Chapter` 模型 (更新)**:
    *   添加 `image_metadata = models.JSONField(default=list, blank=True, verbose_name="图片元数据")` 字段，用于存储章节中图片的信息（URL, alt text）。
    *   添加 `heading_structure = models.JSONField(default=list, blank=True, verbose_name="章节标题结构")` 字段，用于存储章节内部的多级标题层级信息（标题文本、ID、层级）。

### 2.2. 数据库迁移

执行 `python manage.py makemigrations` 和 `python manage.py migrate` 来应用模型更改。

### 2.3. 序列化器调整 (`serializers.py`)

1.  **`TagSerializer` (新增)**: 为 `Tag` 模型创建序列化器。
2.  **`BookSerializer` (更新)**: 更新 `BookSerializer` 以包含所有新字段，并嵌套 `TagSerializer` 来显示标签信息。

### 2.4. 媒体文件配置 (`settings.py` & `urls.py`)

-   在 `settings.py` 中配置 `MEDIA_URL` 和 `MEDIA_ROOT`。
-   在主 `urls.py` 中添加媒体文件的URL路由，以便在开发环境中提供服务。

### 2.5. API Endpoint 扩展 (新增Web导入、编辑、导出)

1.  **Web端书籍导入** (`BookImportView` 或 `action` on `BookViewSet`):
    -   **依赖**: 需要安装 `zipfile` 库（Python标准库，无需额外安装）来处理ZIP文件。
    -   Endpoint: `POST /api/documents/import_book/`
    -   Input: `multipart/form-data` (包含 `zip_file` 或 `markdown_file`，以及可选的 `image_files` 数组，和书籍元数据)。
    -   Logic:
        *   **ZIP文件处理**: 如果接收到 `zip_file`：
            *   将ZIP文件保存到临时目录。
            *   解压ZIP文件。
            *   在解压后的文件中查找主要的Markdown文件（例如，`README.md` 或根据文件名约定）。
            *   解析该Markdown文件，并处理其中包含的相对路径图片（将图片从解压目录复制到 `MEDIA_ROOT`）。
        *   **Markdown文件处理**: 如果只接收到 `markdown_file`，则继续按现有逻辑处理。
        *   **独立图片文件处理**: 如果接收到 `image_files` 数组：
            *   将这些图片文件保存到 `MEDIA_ROOT` 的特定子目录（例如 `media/uploaded_images/`）。
            *   **重要**: 在Markdown内容中，用户需要使用这些图片文件的相对URL（例如 `/media/uploaded_images/my_image.jpg`）来引用它们。我们不会自动修改Markdown内容中的图片路径，而是假定用户已经知道如何引用这些已上传的图片。
        *   **元数据**: 无论哪种方式，都将书籍元数据（标题、作者、简介、封面图片、标签）与Markdown内容一起处理。
        *   **Markdown解析库配置**: 确保 `markdown.markdown` 使用 `toc` (Table of Contents) 和 `attr_list` (Attribute Lists) 等扩展。`pymdownx.extra` 和 `pymdownx.header` 扩展将用于自动生成标题ID和提供更丰富的Markdown支持。
        *   **图片信息提取**: 在 `replace_image_path` 函数中，不仅替换URL，还要提取 `alt` 文本、原始路径等信息，并将其结构化后添加到 `Chapter` 对象的 `image_metadata` 字段中。
        *   **标题结构提取**: 解析Markdown内容，识别H1, H2, H3等标题，并构建一个嵌套的标题结构（列表），存储到 `heading_structure` 字段。可以使用 `markdown.Markdown` 结合 `toc` 扩展来获取其生成的目录数据。
        *   **章节内容保留原始Markdown**: `content_md` 字段将存储原始的Markdown文本，`content_html` 存储已处理图片路径和公式的HTML。
    -   Permissions: 确保只有授权用户（如管理员）可以访问。

2.  **Web端书籍编辑** (扩展 `ChapterViewSet`):
    -   `PUT /api/documents/chapters/<int:pk>/`：允许更新章节的 `content_md`。
    -   On Save: 在更新 `content_md` 后，自动将其转换为 `content_html` 并保存。
    -   Logic: 重新执行Markdown解析逻辑，以更新 `image_metadata` 和 `heading_structure`。
    -   Permissions: 确保只有授权用户可以修改。

3.  **Web端书籍导出** (新增 `action` on `BookViewSet`):
    -   Endpoint: `GET /api/documents/books/<int:pk>/export_markdown/`
    -   Logic: 从数据库中获取 `Book` 和所有 `Chapter` 的 `content_md`。由于我们现在将 `content_md` 存储为原始Markdown，所以直接拼接即可。
    -   **图片引用**: 在拼接Markdown时，确保图片路径（如果原始Markdown中使用的是相对路径）被转换回适合导出的相对路径，或者保持为可访问的绝对URL。
    -   **ZIP导出 (可选)**: 考虑增加一个选项，将书籍内容（Markdown和图片）打包成ZIP文件导出。
    -   Permissions: 确保只有授权用户可以访问。

---

## 3. 前端重构与开发

### 3.1. 页面与组件

1.  **`LibraryPage.jsx` (新增)**:
    -   功能：作为书库主页面。
    -   实现：调用 `/api/documents/books/` 接口，获取所有书籍数据，并以网格布局展示。

2.  **`BookCard.jsx` (新增)**:
    -   功能：展示单本书籍的卡片。
    -   实现：显示书籍封面、标题、作者和标签。整个卡片是一个链接，指向该书的阅读页面。

3.  **`BookPage.jsx` (重构)**:
    -   功能：作为书籍阅读页面。
    -   实现：使用 React Router 的 `useParams` 钩子从URL (`/books/:bookId`) 中获取 `bookId`，并动态加载相应的书籍数据。

4.  **`BookImportPage.jsx` (新增)**:
    -   功能：Web端书籍导入界面。
    -   实现：包含文件选择器（支持md和zip）、书籍元数据输入表单（标题、作者、简介、封面上传、标签选择等）。支持独立图片上传字段。

5.  **`ChapterEditorPage.jsx` (新增)**:
    -   功能：Web端章节编辑界面。
    -   实现：显示当前章节的Markdown内容在一个可编辑的文本区域，提供实时预览功能，并支持保存修改。

### 3.2. 路由更新 (`routes/index.js`)

-   **书籍阅读页面路由**: 将 `/books/:bookId` 路由从 `App` 组件的子路由中移出，提升为顶级路由。
-   **管理页面路由**: `App` 组件的子路由中包含 `/library`、`/import-book` 和 `/books/:bookId/:chapterId/edit` 路由。

### 3.3. 导航栏更新

-   在主导航栏组件（如 `Sidebar.jsx`）中，添加指向 `/library` 和 `/import-book` 的新导航链接。

### 3.4. Markdown渲染优化 (前端)

-   **图片显示**: 确保 `ChapterView` 组件正确处理 `<img>` 标签的 `src` 属性，指向Django提供的媒体文件URL。
-   **公式渲染**: 在 `ChapterView` 中使用手动 MathJax 渲染方法，确保公式正确显示。

---

## 4. 系统架构图 (Mermaid)

```mermaid
graph TD
    subgraph "用户界面"
        A[Sidebar]
        B[LibraryPage]
        C[BookPage]
        D[ChapterView]
        E[BookImportPage]
        F[ChapterEditorPage]
    end

    subgraph "后端 API (Django REST Framework)"
        G[BookViewSet]
        H[ChapterViewSet]
        I[BookImportView]
        J[BookExportView]
        K[ImageUploadView]
    end

    subgraph "数据库"
        L[Book Model]
        M[Chapter Model]
        N[Tag Model]
    end

    subgraph "文件存储"
        O[Media Storage (Covers, Images)]
        P[临时ZIP解压目录]
        Q[上传图片目录]
    end

    A -- "点击 '书库'" --> B
    B -- "GET /api/documents/books/" --> G
    G -- "查询书籍" --> L
    L -- "包含 Tags" --> N
    G -- "返回书籍列表" --> B
    B -- "用户点击书籍卡片" --> C_Standalone[独立渲染的 BookPage]
    C_Standalone -- "GET /api/books/:bookId/" --> G
    G -- "查询书籍详情" --> L
    L -- "包含 Chapters" --> M
    G -- "返回书籍详情" --> C_Standalone
    C_Standalone -- "选择章节" --> D
    D -- "渲染 HTML + 公式" --> R[MathJax/KaTeX]

    A -- "点击 '导入书籍'" --> E_Integrated[集成导航栏的 BookImportPage]
    E_Integrated -- "POST /api/documents/import_book/" + ZIP/Markdown/Metadata --> I
    E_Integrated -- "POST /api/documents/upload_image/" + Image Files --> K
    I -- "处理 ZIP 文件" --> P
    P -- "解析 Markdown & 复制图片" --> O
    K -- "保存图片" --> Q
    I -- "保存 Book/Chapter (含图片/标题元数据)" --> L & M

    D -- "点击 '编辑章节'" --> F_Integrated[集成导航栏的 ChapterEditorPage]
    F_Integrated -- "GET /api/documents/chapters/:chapterId/" --> H
    H -- "返回 Markdown 内容" --> F_Integrated
    F_Integrated -- "用户修改内容" --> F_Integrated
    F_Integrated -- "PUT /api/documents/chapters/:chapterId/" + Updated Markdown --> H
    H -- "Markdown to HTML Conversion (更新图片/标题元数据)" --> M
    H -- "保存更新" --> M

    C_Standalone -- "点击 '导出Markdown'" --> J
    J -- "GET /api/documents/books/:bookId/export_markdown/" --> L & M
    J -- "拼接原始Markdown & 返回文件" --> C_Standalone

    style A fill:#f9f,stroke:#333,stroke-width:2px
    style B fill:#bbf,stroke:#333,stroke-width:2px
    style C_Standalone fill:#bbf,stroke:#333,stroke-width:2px
    style D fill:#bbf,stroke:#333,stroke-width:2px
    style E_Integrated fill:#bfb,stroke:#333,stroke-width:2px
    style F_Integrated fill:#bfb,stroke:#333,stroke-width:2px
    style G fill:#fbb,stroke:#333,stroke-width:2px
    style H fill:#fbb,stroke:#333,stroke-width:2px
    style I fill:#fbb,stroke:#333,stroke-width:2px
    style J fill:#fbb,stroke:#333,stroke-width:2px
    style K fill:#fbb,stroke:#333,stroke-width:2px
    style L fill:#ddf,stroke:#333,stroke-width:2px
    style M fill:#ddf,stroke:#333,stroke-width:2px
    style N fill:#ddf,stroke:#333,stroke-width:2px
    style O fill:#ffd,stroke:#333,stroke-width:2px
    style P fill:#ffc,stroke:#333,stroke-width:2px
    style Q fill:#ffc,stroke:#333,stroke-width:2px
    style R fill:#ccf,stroke:#333,stroke-width:2px