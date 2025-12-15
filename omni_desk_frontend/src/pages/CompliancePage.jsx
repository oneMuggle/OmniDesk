import React, { useState, useEffect } from 'react';
import { Container, Typography, Table, TableBody, TableCell, TableHead, TableRow, Paper, Chip, Box, Select, MenuItem, FormControl, InputLabel } from '@mui/material';
import complianceApi from '../api/compliance'; // Assuming you'll create this API service
import projectsApi from '../api/projects'; // Import projectsApi

import { useLocation, useNavigate } from 'react-router-dom';

const CompliancePage = () => {
    const [complianceIssues, setComplianceIssues] = useState([]);
    const [projects, setProjects] = useState([]);
    const location = useLocation();
    const navigate = useNavigate();

    // Derive selectedProject from URL's query parameters
    const queryParams = new URLSearchParams(location.search);
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

    }, [location.search, queryParams]);


    const handleProjectChange = (event) => {
        const projectId = event.target.value;
        const newQueryParams = new URLSearchParams();
        if (projectId) {
            newQueryParams.set('project_id', projectId);
        }
        navigate({ search: newQueryParams.toString() });
    };

    const getSeverityColor = (severity) => {
        switch (severity) {
            case '紧急': return 'error';
            case '高': return 'warning';
            case '中': return 'info';
            case '低': return 'success';
            default: return 'default';
        }
    };

    return (
        <Container>
            <Typography variant="h4" component="h1" gutterBottom>
                合规问题管理
            </Typography>

            <Box sx={{ minWidth: 120, mb: 3 }}>
                <FormControl fullWidth>
                    <InputLabel id="project-select-label">选择项目</InputLabel>
                    <Select
                        labelId="project-select-label"
                        id="project-select"
                        value={selectedProject}
                        label="选择项目"
                        onChange={handleProjectChange}
                    >
                        <MenuItem value="">
                            <em>所有项目</em>
                        </MenuItem>
                        {projects.map((project) => (
                            <MenuItem key={project.id} value={project.id}>
                                {project.name}
                            </MenuItem>
                        ))}
                    </Select>
                </FormControl>
            </Box>

            <Paper>
                <Table>
                    <TableHead>
                        <TableRow>
                            <TableCell>项目</TableCell>
                            <TableCell>问题类型</TableCell>
                            <TableCell>问题描述</TableCell>
                            <TableCell>位置</TableCell>
                            <TableCell>状态</TableCell>
                            <TableCell>严重程度</TableCell>
                            <TableCell>截止日期</TableCell>
                            <TableCell>创建时间</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {complianceIssues.length > 0 ? (
                            complianceIssues.map((issue) => (
                                <TableRow key={issue.id}>
                                    <TableCell>{issue.project_details?.name || 'N/A'}</TableCell>
                                    <TableCell>{issue.issue_type}</TableCell>
                                    <TableCell>{issue.description}</TableCell>
                                    <TableCell>{issue.location}</TableCell>
                                    <TableCell>{issue.status}</TableCell>
                                    <TableCell>
                                        <Chip label={issue.severity} color={getSeverityColor(issue.severity)} size="small" />
                                    </TableCell>
                                    <TableCell>{issue.due_date || '无'}</TableCell>
                                    <TableCell>{new Date(issue.created_at).toLocaleString()}</TableCell>
                                </TableRow>
                            ))
                        ) : (
                            <TableRow>
                                <TableCell colSpan={8} align="center">
                                    没有找到合规问题。
                                </TableCell>
                            </TableRow>
                        )}
                    </TableBody>
                </Table>
            </Paper>
        </Container>
    );
};

export default CompliancePage;