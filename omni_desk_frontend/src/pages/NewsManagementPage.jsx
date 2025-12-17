import React, { useState, useEffect } from 'react';
import {
  Table,
  Button,
  Modal,
  Form,
  Input,
  DatePicker,
  Select,
  message,
  Row,
  Col,
  Typography,
  Popconfirm,
} from 'antd';
import {
  getNewsArticles,
  createNewsArticle,
  updateNewsArticle,
  deleteNewsArticle,
  getNewsTypes,
  createNewsType,
  updateNewsType,
  deleteNewsType,
} from '../api/newsApi';
import userManagementApi from '../api/userManagementApi';
import moment from 'moment';

const { Title } = Typography;
const { Option } = Select;

const NewsManagementPage = () => {
  const [articles, setArticles] = useState([]);
  const [newsTypes, setNewsTypes] = useState([]);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [articleModalVisible, setArticleModalVisible] = useState(false);
  const [typeModalVisible, setTypeModalVisible] = useState(false);
  const [editingArticle, setEditingArticle] = useState(null);
  const [editingType, setEditingType] = useState(null);
  const [form] = Form.useForm();
  const [typeForm] = Form.useForm();

  const fetchAllData = async () => {
    try {
      setLoading(true);
      const [articlesRes, typesRes, usersRes] = await Promise.all([
        getNewsArticles(),
        getNewsTypes(),
        userManagementApi.getAllUsers(),
      ]);
      setArticles(articlesRes?.data?.results || []);
      setNewsTypes(typesRes?.data?.results || []);
      setUsers(usersRes?.data?.results || []);
    } catch (error) {
      message.error('数据加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAllData();
  }, []);

  // Article Modal Handlers
  const handleAddArticle = () => {
    setEditingArticle(null);
    form.resetFields();
    setArticleModalVisible(true);
  };

  const handleEditArticle = (record) => {
    setEditingArticle(record);
    form.setFieldsValue({
      ...record,
      publication_date: moment(record.publication_date),
      personnel_id: record.personnel.id,
      news_type_id: record.news_type.id,
    });
    setArticleModalVisible(true);
  };

  const handleDeleteArticle = async (id) => {
    try {
      await deleteNewsArticle(id);
      message.success('文章删除成功');
      fetchAllData();
    } catch (error) {
      message.error('文章删除失败');
    }
  };

  const handleArticleModalOk = async () => {
    try {
      const values = await form.validateFields();
      const data = {
        ...values,
        publication_date: values.publication_date.format('YYYY-MM-DD'),
      };
      if (editingArticle) {
        await updateNewsArticle(editingArticle.id, data);
        message.success('文章更新成功');
      } else {
        await createNewsArticle(data);
        message.success('文章创建成功');
      }
      setArticleModalVisible(false);
      fetchAllData();
    } catch (error) {
      message.error('操作失败');
    }
  };

  // Type Modal Handlers
  const handleAddType = () => {
    setEditingType(null);
    typeForm.resetFields();
    setTypeModalVisible(true);
  };

  const handleEditType = (record) => {
    setEditingType(record);
    typeForm.setFieldsValue(record);
    setTypeModalVisible(true);
  };

  const handleDeleteType = async (id) => {
    try {
      await deleteNewsType(id);
      message.success('类型删除成功');
      fetchAllData();
    } catch (error) {
      message.error('类型删除失败');
    }
  };

  const handleTypeModalOk = async () => {
    try {
      const values = await typeForm.validateFields();
      if (editingType) {
        await updateNewsType(editingType.id, values);
        message.success('类型更新成功');
      } else {
        await createNewsType(values);
        message.success('类型创建成功');
      }
      setTypeModalVisible(false);
      fetchAllData();
    } catch (error) {
      message.error('操作失败');
    }
  };

  const articleColumns = [
    { title: '标题', dataIndex: 'title', key: 'title' },
    { title: '链接', dataIndex: 'link', key: 'link', render: (link) => <a href={link} target="_blank" rel="noopener noreferrer">{link}</a> },
    { title: '发布日期', dataIndex: 'publication_date', key: 'publication_date' },
    { title: '关联人员', dataIndex: ['personnel', 'name'], key: 'personnel' },
    { title: '新闻类型', dataIndex: ['news_type', 'name'], key: 'news_type' },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <span>
          <Button type="link" onClick={() => handleEditArticle(record)}>编辑</Button>
          <Popconfirm title="确定删除吗?" onConfirm={() => handleDeleteArticle(record.id)}>
            <Button type="link" danger>删除</Button>
          </Popconfirm>
        </span>
      ),
    },
  ];

  const typeColumns = [
    { title: '类型名称', dataIndex: 'name', key: 'name' },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <span>
          <Button type="link" onClick={() => handleEditType(record)}>编辑</Button>
          <Popconfirm title="确定删除吗?" onConfirm={() => handleDeleteType(record.id)}>
            <Button type="link" danger>删除</Button>
          </Popconfirm>
        </span>
      ),
    },
  ];

  return (
    <div style={{ padding: '20px' }}>
      <Title level={2}>新闻管理</Title>
      
      <Row gutter={16}>
        <Col span={16}>
          <Title level={3}>新闻文章</Title>
          <Button onClick={handleAddArticle} type="primary" style={{ marginBottom: 16 }}>
            添加文章
          </Button>
          <Table
            columns={articleColumns}
            dataSource={articles}
            rowKey="id"
            loading={loading}
          />
        </Col>
        <Col span={8}>
          <Title level={3}>新闻类型</Title>
          <Button onClick={handleAddType} type="primary" style={{ marginBottom: 16 }}>
            添加类型
          </Button>
          <Table
            columns={typeColumns}
            dataSource={newsTypes}
            rowKey="id"
            loading={loading}
          />
        </Col>
      </Row>

      <Modal
        title={editingArticle ? '编辑文章' : '添加文章'}
        open={articleModalVisible}
        onOk={handleArticleModalOk}
        onCancel={() => setArticleModalVisible(false)}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="title" label="标题" rules={[{ required: true, message: '请输入标题' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="link" label="链接" rules={[{ required: true, message: '请输入链接' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="publication_date" label="发布日期" rules={[{ required: true, message: '请选择发布日期' }]}>
            <DatePicker />
          </Form.Item>
          <Form.Item name="personnel_id" label="关联人员" rules={[{ required: true, message: '请选择关联人员' }]}>
            <Select>
              {users.map(user => <Option key={user.id} value={user.id}>{user.username}</Option>)}
            </Select>
          </Form.Item>
          <Form.Item name="news_type_id" label="新闻类型" rules={[{ required: true, message: '请选择新闻类型' }]}>
            <Select>
              {newsTypes.map(type => <Option key={type.id} value={type.id}>{type.name}</Option>)}
            </Select>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={editingType ? '编辑类型' : '添加类型'}
        open={typeModalVisible}
        onOk={handleTypeModalOk}
        onCancel={() => setTypeModalVisible(false)}
      >
        <Form form={typeForm} layout="vertical">
          <Form.Item name="name" label="类型名称" rules={[{ required: true, message: '请输入类型名称' }]}>
            <Input />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default NewsManagementPage;