import React, { useState, useEffect } from 'react';
import { Table, Button, Modal, Form, Input, DatePicker, Select, Tag, Space, Typography } from 'antd';
import { EditOutlined, DeleteOutlined, UploadOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import dayjs from 'dayjs';
import projectsApi from '../api/projects';

const { Title } = Typography;
const { Option } = Select;

const ProjectsPage = () => {
    const [projects, setProjects] = useState([]);
    const [openDialog, setOpenDialog] = useState(false);
    const [currentProject, setCurrentProject] = useState(null);
    const [formValues, setFormValues] = useState({
        name: '',
        description: '',
        start_date: null,
        end_date: null,
        status: '进行中',
    });
    const navigate = useNavigate(); // 初始化 useNavigate

    const fetchProjects = React.useCallback(async () => {
        try {
            const response = await projectsApi.getAllProjects();
            setProjects(response.data.results || []); // Ensure projects is an array
        } catch (error) {
            console.error('Error fetching projects:', error);
        }
    }, []);

    useEffect(() => {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        fetchProjects();
    }, [fetchProjects]);

    const handleOpenDialog = (project = null) => {
        setCurrentProject(project);
        if (project) {
            setFormValues({
                name: project.name,
                description: project.description,
                start_date: project.start_date ? dayjs(project.start_date) : null,
                end_date: project.end_date ? dayjs(project.end_date) : null,
                status: project.status,
            });
        } else {
            setFormValues({
                name: '',
                description: '',
                start_date: null,
                end_date: null,
                status: '进行中',
            });
        }
        setOpenDialog(true);
    };

    const handleCloseDialog = () => {
        setOpenDialog(false);
        setCurrentProject(null);
        setFormValues({
            name: '',
            description: '',
            start_date: null,
            end_date: null,
            status: '进行中',
        });
    };

    const handleSubmit = async (values) => {
        try {
            const data = {
                ...values,
                start_date: values.start_date ? values.start_date.format('YYYY-MM-DD') : null,
                end_date: values.end_date ? values.end_date.format('YYYY-MM-DD') : null,
            };
            if (currentProject) {
                await projectsApi.updateProject(currentProject.id, data);
            } else {
                await projectsApi.createProject(data);
            }
            fetchProjects();
            handleCloseDialog();
        } catch (error) {
            console.error('Error saving project:', error);
        }
    };

    const handleDelete = async (id) => {
        try {
            await projectsApi.deleteProject(id);
            fetchProjects();
        } catch (error) {
            console.error('Error deleting project:', error);
        }
    };

    const columns = [
        { title: '项目名称', dataIndex: 'name', key: 'name' },
        { title: '描述', dataIndex: 'description', key: 'description' },
        { title: '开始日期', dataIndex: 'start_date', key: 'start_date' },
        { title: '结束日期', dataIndex: 'end_date', key: 'end_date' },
        { title: '状态', dataIndex: 'status', key: 'status', render: (status) => <Tag color="blue">{status}</Tag> },
        {
            title: '操作',
            key: 'action',
            render: (_, record) => (
                <Space>
                    <Button type="link" icon={<EditOutlined />} onClick={() => handleOpenDialog(record)} />
                    <Button type="link" danger icon={<DeleteOutlined />} onClick={() => handleDelete(record.id)} />
                    <Button type="link" icon={<UploadOutlined />} onClick={() => navigate(`/documents?project_id=${record.id}`)} />
                </Space>
            ),
        },
    ];

    return (
        <div style={{ padding: '24px' }}>
            <Title level={2}>项目管理</Title>
            <Button type="primary" onClick={() => handleOpenDialog()} style={{ marginBottom: '16px' }}>
                创建新项目
            </Button>

            <Table columns={columns} dataSource={projects.map(p => ({ ...p, key: p.id }))} pagination={{ pageSize: 10 }} />

            <Modal
                title={currentProject ? '编辑项目' : '创建新项目'}
                open={openDialog}
                onCancel={handleCloseDialog}
                footer={null}
            >
                <Form
                    layout="vertical"
                    initialValues={{
                        name: formValues.name,
                        description: formValues.description,
                        start_date: formValues.start_date,
                        end_date: formValues.end_date,
                        status: formValues.status,
                    }}
                    onFinish={handleSubmit}
                >
                    <Form.Item name="name" label="项目名称" rules={[{ required: true }]}>
                        <Input />
                    </Form.Item>
                    <Form.Item name="description" label="项目描述">
                        <Input.TextArea rows={4} />
                    </Form.Item>
                    <Form.Item name="start_date" label="开始日期">
                        <DatePicker style={{ width: '100%' }} />
                    </Form.Item>
                    <Form.Item name="end_date" label="结束日期">
                        <DatePicker style={{ width: '100%' }} />
                    </Form.Item>
                    <Form.Item name="status" label="状态">
                        <Select>
                            <Option value="进行中">进行中</Option>
                            <Option value="已完成">已完成</Option>
                            <Option value="已暂停">已暂停</Option>
                            <Option value="已取消">已取消</Option>
                        </Select>
                    </Form.Item>
                    <Form.Item>
                        <Space>
                            <Button onClick={handleCloseDialog}>取消</Button>
                            <Button type="primary" htmlType="submit">保存</Button>
                        </Space>
                    </Form.Item>
                </Form>
            </Modal>
        </div>
    );
};

export default ProjectsPage;