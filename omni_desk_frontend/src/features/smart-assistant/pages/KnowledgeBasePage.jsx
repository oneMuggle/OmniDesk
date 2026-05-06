import { useState, useEffect } from 'react';
import { Card, Table, Tag, Button, Upload, Space, Popconfirm, message, Typography } from 'antd';
import { UploadOutlined, DeleteOutlined, ReloadOutlined } from '@ant-design/icons';
import { getKnowledgeDocs, deleteKnowledgeDoc, uploadKnowledgeDoc } from '../api/smartAssistantApi';
import './KnowledgeBasePage.css';

const { Title } = Typography;

const STATUS_MAP = {
  pending: { color: 'default', text: '等待中' },
  processing: { color: 'processing', text: '处理中' },
  completed: { color: 'success', text: '已完成' },
  failed: { color: 'error', text: '失败' },
};

const KnowledgeBasePage = () => {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);

  const fetchDocuments = async () => {
    setLoading(true);
    try {
      const response = await getKnowledgeDocs();
      setDocuments(response.data.results || response.data || []);
    } catch {
      message.error('获取文档列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, []);

  // 自动刷新处理中的文档状态
  useEffect(() => {
    const hasProcessing = documents.some(d => d.embedding_status === 'processing');
    if (!hasProcessing) return;

    const timer = setInterval(fetchDocuments, 5000);
    return () => clearInterval(timer);
  }, [documents]);

  const handleDelete = async (docId) => {
    try {
      await deleteKnowledgeDoc(docId);
      message.success('文档已删除');
      fetchDocuments();
    } catch {
      message.error('删除文档失败');
    }
  };

  const handleUpload = async (file) => {
    setUploading(true);
    try {
      await uploadKnowledgeDoc(file, file.name);
      message.success(`"${file.name}" 上传成功，正在处理中`);
      fetchDocuments();
    } catch {
      message.error(`"${file.name}" 上传失败`);
    } finally {
      setUploading(false);
    }
    return false;
  };

  const columns = [
    {
      title: '文件名',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
    },
    {
      title: '状态',
      dataIndex: 'embedding_status',
      key: 'embedding_status',
      width: 120,
      render: (status) => {
        const { color, text } = STATUS_MAP[status] || STATUS_MAP.pending;
        return <Tag color={color}>{text}</Tag>;
      },
    },
    {
      title: '上传时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 200,
      render: (val) => val ? new Date(val).toLocaleString('zh-CN') : '-',
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_, record) => (
        <Popconfirm
          title="确认删除"
          description="确定要删除此文档吗？"
          onConfirm={() => handleDelete(record.id)}
          okText="确定"
          cancelText="取消"
        >
          <Button type="link" danger icon={<DeleteOutlined />} size="small">
            删除
          </Button>
        </Popconfirm>
      ),
    },
  ];

  return (
    <div className="knowledge-base-page">
      <div className="knowledge-base-header">
        <Title level={3}>知识库管理</Title>
        <Space>
          <Button
            icon={<ReloadOutlined />}
            onClick={fetchDocuments}
            loading={loading}
          >
            刷新
          </Button>
          <Upload
            beforeUpload={handleUpload}
            showUploadList={false}
            accept=".pdf,.doc,.docx,.txt,.md,.xlsx,.xls,.csv"
            disabled={uploading}
          >
            <Button
              type="primary"
              icon={<UploadOutlined />}
              loading={uploading}
            >
              上传文档
            </Button>
          </Upload>
        </Space>
      </div>

      <Card className="knowledge-base-table">
        <Table
          columns={columns}
          dataSource={documents}
          rowKey="id"
          loading={loading}
          locale={{ emptyText: '暂无文档，请上传文件开始构建知识库' }}
          pagination={{ pageSize: 20, showSizeChanger: false }}
        />
      </Card>
    </div>
  );
};

export default KnowledgeBasePage;
