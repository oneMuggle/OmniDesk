import { useState, useEffect } from 'react';
import { Input, Select, Upload, Button, message, Form, Table } from 'antd';
import { FileAddOutlined } from '@ant-design/icons';
import documentsApi from '../api/documents'; // 统一使用 documentsApi
import ChatInterface from '../../../shared/components/ChatInterface';
import projectsApi from '../../projects/api/projects'; // Add projectsApi
import '../../../shared/pages/DocumentsPage.css';
import { useLocation, useNavigate } from 'react-router-dom'; // 导入 useLocation 和 useNavigate

const { Option } = Select;

const DocumentsPage = () => {
  const [form] = Form.useForm();
  const [templates, setTemplates] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [projects, setProjects] = useState([]); // Add projects state
  const [selectedProject, setSelectedProject] = useState(null); // Add selectedProject state
  const location = useLocation(); // 获取 location 对象
  const navigate = useNavigate(); // 初始化 navigate

  // 统一的数据加载函数
  const loadTemplates = async (projectId) => {
    try {
      const response = await documentsApi.getDocumentTemplates(projectId);
      setTemplates(response.data.results || []); // 确保返回的是数组
    } catch (error) {
      message.error('加载模板列表失败');
      console.error('Error loading templates:', error);
    }
  };

  // 初始化加载项目列表，并根据 URL 参数加载模板
  useEffect(() => {
    const loadInitialData = async () => {
      try {
        const projectsResponse = await projectsApi.getAllProjects();
        setProjects(projectsResponse.data.results || []);

        const queryParams = new URLSearchParams(location.search);
        const projectIdFromUrl = queryParams.get('project_id');
        if (projectIdFromUrl) {
          setSelectedProject(parseInt(projectIdFromUrl));
          loadTemplates(projectIdFromUrl); // 加载特定项目的模板
        } else {
          loadTemplates(); // 加载所有模板
        }
      } catch (error) {
        message.error('加载项目数据失败');
        console.error('Error loading projects:', error);
      }
    };
    loadInitialData();
  }, [location.search]);


  // 处理模板上传
  const handleUpload = async (file) => {
    try {
      const formData = new FormData();
      formData.append('template', file);
      if (selectedProject) {
        formData.append('project', selectedProject);
      }
      await documentsApi.uploadTemplate(formData);
      message.success('模板上传成功');
      loadTemplates(selectedProject); // 重新加载模板列表
    } catch (error) {
      message.error('上传失败');
      console.error('Upload error:', error);
    }
  };

  // 触发智能分析
  const handleAnalyze = async (templateId) => {
    try {
      message.loading({ content: '正在分析中，请稍候...', key: 'analyzing' });
      const response = await documentsApi.analyzeDocumentTemplate(templateId);
      message.success({ content: `分析完成！发现 ${response.data.issues.length} 个问题。`, key: 'analyzing' });
      // 跳转到合规性页面查看结果
      const template = templates.find(t => t.id === templateId);
      if (template && template.project) {
        navigate(`/control-panel/compliance?project_id=${template.project}&document_template_id=${templateId}`);
      } else {
        navigate(`/control-panel/compliance?document_template_id=${templateId}`);
      }
    } catch (error) {
      message.error({ content: '分析失败，请检查后端服务。', key: 'analyzing' });
      console.error('Analysis error:', error);
    }
  };

  // 生成文档 (保留旧功能)
  const generateDocument = async (values) => {
    try {
      const response = await documentsApi.generateDocument(selectedTemplate.id, values);
      const blob = new Blob([response.data], { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${selectedTemplate.name}_generated.docx`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      a.remove();
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
                <>
                  <Button style={{ marginRight: 8 }} onClick={() => setSelectedTemplate(record)}>生成文档</Button>
                  <Button type="primary" onClick={() => handleAnalyze(record.id)}>智能分析</Button>
                </>
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