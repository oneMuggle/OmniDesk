# DocumentsPage 组件文档

## 功能说明
本组件提供企业级文档模板管理和自动化文档生成功能，主要包含以下特性：

### 1. 模板管理
- 支持上传新的 Word 模板文件(.docx)
- 展示现有模板列表（名称、更新时间）
- 模板选择功能

#### 模板格式要求
1. **文件规范**
   - 必须使用 Microsoft Word 97/2007+ 格式 (.docx)
   - 文件命名格式：`[类型]_模板名称.docx`（例：`contract_服务协议模板.docx`）

2. **变量语法**
   ```text
   {{variableName}}        // 普通变量
   {{#section}}...{{/section}}  // 循环区块
   {{?condition}}...{{/condition}} // 条件区块
   ```

3. **元数据要求**
   - 必须在文档属性中包含：
     - 标题：模板显示名称
     - 作者：模板创建者
     - 备注：模板用途说明

4. **内容规范**
   - 保留样式应使用 Word 内置样式（标题1、正文等）
   - 禁止使用复杂表格嵌套
   - 图片需要嵌入文档中

### 2. 文档生成
- 基于选定模板生成新文档
- 动态表单字段支持（需配合模板配置）
- 自动下载生成的文档

### 3. 集成功能
- 内置聊天交互界面（ChatInterface）
- 基于 Ant Design 的 UI 组件
- 与后端 API 集成（通过 documentAPI）

## 使用说明

### 依赖要求
```bash
antd @ant-design/icons mammoth docxtemplater
```

### 组件引入
```jsx
import DocumentsPage from './DocumentsPage';
```

### 基本使用
```jsx
function App() {
  return (
    <div className="App">
      <DocumentsPage />
    </div>
  );
}
```

### API 配置
需确保已正确配置 documentAPI 的以下方法：
- `getTemplates()` 获取模板列表
- `uploadTemplate(formData)` 上传新模板
- `generateDocument(templateId, formData)` 生成文档

## 数据结构
### 模板对象
```javascript
{
  id: string,         // 唯一标识
  name: string,       // 模板名称
  updatedAt: string,  // 更新时间戳
  // 其他扩展字段...
}
```

## 样式定制
通过 DocumentsPage.css 可自定义以下样式类：
- `.documents-container` 主容器
- `.template-section` 模板管理区域
- `.generation-section` 文档生成区域
