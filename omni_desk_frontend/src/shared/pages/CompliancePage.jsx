import React, { useState, useEffect, useMemo } from 'react';
import { Table, Tag, Select, Typography, Space } from 'antd';
import { useLocation, useNavigate } from 'react-router-dom';
import complianceApi from '../api/compliance';
import projectsApi from '../api/projects';

const { Title } = Typography;
const { Option } = Select;

const CompliancePage = () => {
    const [complianceIssues, setComplianceIssues] = useState([]);
    const [projects, setProjects] = useState([]);
    const location = useLocation();
    const navigate = useNavigate();

    const queryParams = useMemo(() => new URLSearchParams(location.search), [location.search]);
    const selectedProject = queryParams.get('project_id') || '';

    useEffect(() => {
        const fetchProjects = async () => {
            try {
                const response = await projectsApi.getAllProjects();
                setProjects(response.data.results || []);
            } catch (error) {
                console.error('Error fetching projects:', error);
            }
        };
        fetchProjects();
    }, []);

    useEffect(() => {
        const fetchComplianceIssues = async () => {
            const params = {};
            const projectId = queryParams.get('project_id');
            const documentTemplateId = queryParams.get('document_template_id');

            if (projectId) {
                params.project = projectId;
            }
            if (documentTemplateId) {
                params.document_template = documentTemplateId;
            }
            
            try {
                const response = await complianceApi.getAllComplianceIssues(params);
                setComplianceIssues(response.data.results || []);
            } catch (error) {
                console.error('Error fetching compliance issues:', error);
            }
        };
        
        fetchComplianceIssues();
    }, [queryParams]);


    const handleProjectChange = (value) => {
        const newQueryParams = new URLSearchParams();
        if (value) {
            newQueryParams.set('project_id', value);
        }
        navigate({ search: newQueryParams.toString() });
    };

    const getSeverityColor = (severity) => {
        switch (severity) {
            case '紧急': return 'red';
            case '高': return 'orange';
            case '中': return 'blue';
            case '低': return 'green';
            default: return 'default';
        }
    };

    const columns = [
        { title: '项目', dataIndex: ['project_details', 'name'], key: 'project', render: (name) => name || 'N/A' },
        { title: '问题类型', dataIndex: 'issue_type', key: 'issue_type' },
        { title: '问题描述', dataIndex: 'description', key: 'description' },
        { title: '位置', dataIndex: 'location', key: 'location' },
        { title: '状态', dataIndex: 'status', key: 'status' },
        { title: '严重程度', dataIndex: 'severity', key: 'severity', render: (severity) => <Tag color={getSeverityColor(severity)}>{severity}</Tag> },
        { title: '截止日期', dataIndex: 'due_date', key: 'due_date', render: (date) => date || '无' },
        { title: '创建时间', dataIndex: 'created_at', key: 'created_at', render: (date) => new Date(date).toLocaleString() },
    ];

    return (
        <div style={{ padding: '24px' }}>
            <Title level={2}>合规问题管理</Title>

            <Space direction="vertical" size="middle" style={{ width: '100%', marginBottom: '16px' }}>
                <Select
                    style={{ width: 300 }}
                    value={selectedProject}
                    onChange={handleProjectChange}
                    placeholder="选择项目"
                    allowClear
                >
                    <Option value="">所有项目</Option>
                    {projects.map((project) => (
                        <Option key={project.id} value={project.id}>
                            {project.name}
                        </Option>
                    ))}
                </Select>

                <Table
                    columns={columns}
                    dataSource={complianceIssues.map(i => ({ ...i, key: i.id }))}
                    pagination={{ pageSize: 10 }}
                    locale={{ emptyText: '没有找到合规问题' }}
                />
            </Space>
        </div>
    );
};

export default CompliancePage;
