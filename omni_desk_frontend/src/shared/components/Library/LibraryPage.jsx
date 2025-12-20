import React, { useState, useEffect } from 'react';
import { Layout, Spin, Select } from 'antd'; // 导入 Select
import axios from 'axios';

import TableOfContents from './TableOfContents';
import ChapterContent from './ChapterContent';
import projectsApi from '../../api/projects'; // 导入 projectsApi
import { useLocation } from 'react-router-dom'; // 导入 useLocation

const { Sider, Content } = Layout;
const { Option } = Select; // 解构 Option

const LibraryPage = () => {
    const [books, setBooks] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [projects, setProjects] = useState([]); // 新增 projects 状态
    const [selectedProject, setSelectedProject] = useState(null); // 新增 selectedProject 状态
    const location = useLocation(); // 获取 location 对象

    // 统一的数据加载函数
    const fetchBooks = async (projectId) => {
        setLoading(true);
        try {
            let url = '/api/documents/books/';
            if (projectId) {
                url += `?project_id=${projectId}`;
            }
            const response = await axios.get(url);
            setBooks(response.data); // 假设后端返回的是书籍列表
        } catch (err) {
            setError('Failed to load books.');
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    // 初始化加载项目列表，并根据 URL 参数加载书籍
    useEffect(() => {
        const loadInitialData = async () => {
            try {
                const projectsResponse = await projectsApi.getAllProjects();
                setProjects(projectsResponse.data.results || []);

                const queryParams = new URLSearchParams(location.search);
                const projectIdFromUrl = queryParams.get('project_id');
                if (projectIdFromUrl) {
                    setSelectedProject(parseInt(projectIdFromUrl));
                    fetchBooks(projectIdFromUrl); // 加载特定项目的书籍
                } else {
                    fetchBooks(); // 加载所有书籍
                }
            } catch (error) {
                setError('Failed to load project data.');
                console.error('Error loading projects:', error);
            }
        };
        loadInitialData();
    }, [location.search]); // 依赖 location.search 以响应 URL 参数变化

    // 当选择的项目变化时，重新加载书籍
    useEffect(() => {
        // 只有当 selectedProject 真正变化时才触发
        if (selectedProject === null) {
            fetchBooks(); // 如果清空选择，加载所有书籍
        } else {
            fetchBooks(selectedProject);
        }
    }, [selectedProject]); // 依赖 selectedProject

    if (loading) {
        return <Spin size="large" />;
    }

    if (error) {
        return <div style={{ color: 'red' }}>{error}</div>;
    }

    return (
        <Layout style={{ minHeight: '100vh' }}>
            <Sider width={300} theme="light">
                <h2>Library</h2>
                {/* 项目选择器 */}
                <div className="project-selector" style={{ padding: '10px' }}>
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
                <TableOfContents books={books} />
            </Sider>
            <Layout>
                <Content style={{ padding: '24px', margin: 0, backgroundColor: '#fff' }}>
                    <ChapterContent />
                </Content>
            </Layout>
        </Layout>
    );
};

export default LibraryPage;