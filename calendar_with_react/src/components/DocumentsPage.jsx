import React, { useState, useEffect } from 'react';
import { Input, Select, Upload, Button, message, Form, Table } from 'antd';
import { InboxOutlined, FileAddOutlined } from '@ant-design/icons';
import mammoth from 'mammoth';
import Docxtemplater from 'docxtemplater';
import {
  getDocumentTemplates,
  generateDocument as generateDeepseekDoc,
  uploadTemplate
} from '../api/deepseek';
import ChatInterface from './ChatInterface';
import projectsApi from '../api/projects'; // Add projectsApi
import './DocumentsPage.css';
import { useLocation } from 'react-router-dom'; // 导入 useLocation

const { Option } = Select;
const { Dragger } = Upload;

const DocumentsPage = () => {
  const [form] = Form.useForm();
  const [htmlContent, setHtmlContent] = useState('');
  const [uploading, setUploading] = useState(false);
  const [templates, setTemplates] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [projects, setProjects] = useState([]); // Add projects state
  const [selectedProject, setSelectedProject] = useState(null); // Add selectedProject state
  const location = useLocation(); // 获取 location 对象

  // 初始化加载模板列表和项目列表
  useEffect(() => {
    const loadData = async () => {
      try {
        const queryParams = new URLSearchParams(location.search);
        const projectIdFromUrl = queryParams.get('project_id');

        const [templatesResponse, projectsResponse] = await Promise.all([
          getDocumentTemplates(projectIdFromUrl), // 初始加载所有模板，或根据URL参数过滤
          projectsApi.getAllProjects() // Fetch all projects
        ]);
        setTemplates(templatesResponse);
        setProjects(projectsResponse.data);
        if (projectIdFromUrl) {
          setSelectedProject(parseInt(projectIdFromUrl)); // 设置选中的项目
        }
      } catch (error) {
        message.error('加载数据失败');
        console.error('Error loading data:', error);
      }
    };
    loadData();
  }, [location.search]); // 依赖 location.search

  // 当选择项目时，重新加载模板
  useEffect(() => {
    const loadTemplatesByProject = async () => {
      try {
        // 根据 selectedProject 过滤模板
        const filteredTemplates = await getDocumentTemplates(selectedProject);
        setTemplates(filteredTemplates);
      } catch (error) {
        message.error('加载模板失败');
        console.error('Error loading filtered templates:', error);
      }
    };
    // 当 selectedProject 变化时，如果 selectedProject 为 null，则加载所有模板；否则加载指定项目的模板
    if (selectedProject !== null) { // 只有当 selectedProject 明确被设置或取消时才重新加载
        loadTemplatesByProject();
    }
  }, [selectedProject]); // 依赖 selectedProject

  // 处理模板上传
  const handleUpload = async (file) => {
    try {
      const formData = new FormData();
      formData.append('template', file);
      if (selectedProject) {
        formData.append('project', selectedProject); // 将选中的项目ID添加到 FormData
      }
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
        
        {/* 项目选择器 */}
        <div className="project-selector">
          <label htmlFor="project-select">选择项目：</label>
          <Select
            id="project-select"
            style={{ width: 200 }}
            placeholder="请选择项目"
            onChange={(value) => setSelectedProject(value)}
            value={selectedProject}
            allowClear
          >
            {projects.map(project => (
              <Option key={project.id} value={project.id}>{project.name}</Option>
            ))}
          </Select>
        </div>

        <Table
          dataSource={templates}
          columns={[
            { title: '模板名称', dataIndex: 'name' },
            {
              title: '所属项目',
              dataIndex: 'project_name', // 假设后端返回的模板数据中包含 project_name
              render: (text, record) => record.project_name || 'N/A' // 如果没有项目，显示 N/A
            },
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
