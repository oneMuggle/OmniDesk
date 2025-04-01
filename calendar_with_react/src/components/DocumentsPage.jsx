import React, { useState, useEffect } from 'react';
import { Input } from 'antd';
import { Upload, Button, message, Form, Table } from 'antd';
import { InboxOutlined, FileAddOutlined } from '@ant-design/icons';
import mammoth from 'mammoth';
import Docxtemplater from 'docxtemplater';
import { 
  getDocumentTemplates, 
  generateDocument as generateDeepseekDoc,
  uploadTemplate 
} from '../api/deepseek';
import ChatInterface from './ChatInterface';
import './DocumentsPage.css';

const { Dragger } = Upload;

const DocumentsPage = () => {
  const [form] = Form.useForm();
  const [htmlContent, setHtmlContent] = useState('');
  const [uploading, setUploading] = useState(false);
  const [templates, setTemplates] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState(null);

  // 初始化加载模板列表
  useEffect(() => {
    const loadTemplates = async () => {
      try {
        const templates = await getDocumentTemplates();
        setTemplates(templates);
      } catch (error) {
        message.error('加载模板失败');
      }
    };
    loadTemplates();
  }, []);

  // 处理模板上传
  const handleUpload = async (file) => {
    try {
      const formData = new FormData();
      formData.append('template', file);
      await uploadTemplate(formData);
      message.success('模板上传成功');
    } catch (error) {
      message.error('上传失败');
    }
  };

  // 生成文档
  const generateDocument = async (values) => {
    try {
      const { content } = await generateDeepseekDoc(
        selectedTemplate.id,
        values
      );
      const blob = new Blob([content], { type: 'text/markdown' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${selectedTemplate.name}_generated.md`;
      a.click();
    } catch (error) {
      message.error('文档生成失败');
    }
  };

  return (
    <div className="documents-container">
      <ChatInterface />
      
      {/* 模板管理区域 */}
      <div className="template-section">
        <Upload
          accept=".docx"
          beforeUpload={handleUpload}
          showUploadList={false}
        >
          <Button icon={<FileAddOutlined />}>上传新模板</Button>
        </Upload>

        <Table
          dataSource={templates}
          columns={[
            { title: '模板名称', dataIndex: 'name' },
            { title: '最后更新', dataIndex: 'updatedAt' },
            {
              title: '操作',
              render: (_, record) => (
                <Button onClick={() => setSelectedTemplate(record)}>使用此模板</Button>
              )
            }
          ]}
          rowKey="id"
        />
      </div>

      {/* 文档生成表单 */}
      {selectedTemplate && (
        <div className="generation-section">
          <Form form={form} onFinish={generateDocument} layout="vertical">
            <Form.Item label="文档标题" name="title" rules={[{ required: true }]}>
              <Input placeholder="请输入文档标题" />
            </Form.Item>
            
            {/* 动态字段可以根据模板配置添加 */}

            <Button type="primary" htmlType="submit">生成文档</Button>
          </Form>
        </div>
      )}
    </div>
  );
};

export default DocumentsPage;
