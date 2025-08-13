# DocumentsPage 使用示例

## 场景说明
实现合同文档模板管理及自动化生成

## 模板配置
1. 准备合同模板文件 contract_template.docx
2. 上传模板：
```jsx
// 在组件外进行模板上传的示例
const handleContractUpload = async (file) => {
  const formData = new FormData();
  formData.append('template', file);
  try {
    await documentAPI.uploadTemplate(formData);
    message.success('合同模板上传成功');
  } catch (error) {
    message.error('上传失败: ' + error.message);
  }
};

// 在组件中使用
<Upload beforeUpload={handleContractUpload}>
  <Button>上传合同模板</Button>
</Upload>
```

## 动态字段配置
在模板文件中使用占位符（例如：{{clientName}}），组件会自动生成对应表单字段：
```jsx
// 扩展生成表单字段
const generateDocument = async (values) => {
  // 生成逻辑...
};

// 在Form.Item中添加自定义字段
<Form form={form} onFinish={generateDocument}>
  <Form.Item label="客户名称" name="clientName" rules={[{ required: true }]}>
    <Input placeholder="输入客户名称" />
  </Form.Item>
  <Form.Item label="合同金额" name="amount" rules={[{ pattern: /^\d+$/ }]}>
    <InputNumber style={{ width: '100%' }} />
  </Form.Item>
</Form>
```

## 完整使用示例
```jsx
import { DocumentPage } from './DocumentsPage';
import { message } from 'antd';

function ContractManagement() {
  return (
    <div>
      <h2>合同管理系统</h2>
      <DocumentPage />
    </div>
  );
}

// API配置示例（src/api/documents.js）
export const documentAPI = {
  getTemplates: async () => {
    const response = await fetch('/api/templates');
    return response.json();
  },
  generateDocument: async (templateId, data) => {
    const response = await fetch(`/api/generate/${templateId}`, {
      method: 'POST',
      body: JSON.stringify(data)
    });
    return response.blob();
  }
};
```

## 典型应用场景
1. 合同文档自动化生成
2. 标准化报告创建
3. 法律文书模板管理
4. 财务单据批量生成

## 注意事项
1. 确保后端API已正确配置CORS
2. 文档生成需要处理可能的网络延迟（建议添加加载状态）
3. 模板文件应符合docxtemplater格式要求
4. 生产环境需要添加错误边界处理
