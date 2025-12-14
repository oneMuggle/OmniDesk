import React, { useState, useEffect } from 'react';
import projectsApi from '../api/projects';
import { Container, Typography, Button, TextField, Dialog, DialogActions, DialogContent, DialogTitle, Table, TableBody, TableCell, TableHead, TableRow, Paper, IconButton } from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import UploadFileIcon from '@mui/icons-material/UploadFile'; // 导入上传图标
import { useNavigate } from 'react-router-dom'; // 导入 useNavigate

const ProjectsPage = () => {
    const [projects, setProjects] = useState([]);
    const [openDialog, setOpenDialog] = useState(false);
    const [currentProject, setCurrentProject] = useState(null);
    const [formValues, setFormValues] = useState({
        name: '',
        description: '',
        start_date: '',
        end_date: '',
        status: '进行中', // Default status
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
        fetchProjects();
    }, [fetchProjects]);

    const handleOpenDialog = (project = null) => {
        setCurrentProject(project);
        if (project) {
            setFormValues({
                name: project.name,
                description: project.description,
                start_date: project.start_date || '',
                end_date: project.end_date || '',
                status: project.status,
            });
        } else {
            setFormValues({
                name: '',
                description: '',
                start_date: '',
                end_date: '',
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
            start_date: '',
            end_date: '',
            status: '进行中',
        });
    };

    const handleChange = (e) => {
        const { name, value } = e.target;
        setFormValues({ ...formValues, [name]: value });
    };

    const handleSubmit = async () => {
        try {
            if (currentProject) {
                await projectsApi.updateProject(currentProject.id, formValues);
            } else {
                await projectsApi.createProject(formValues);
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

    return (
        <Container>
            <Typography variant="h4" component="h1" gutterBottom>
                项目管理
            </Typography>
            <Button variant="contained" color="primary" onClick={() => handleOpenDialog()}>
                创建新项目
            </Button>

            <Paper style={{ marginTop: '20px' }}>
                <Table>
                    <TableHead>
                        <TableRow>
                            <TableCell>项目名称</TableCell>
                            <TableCell>描述</TableCell>
                            <TableCell>开始日期</TableCell>
                            <TableCell>结束日期</TableCell>
                            <TableCell>状态</TableCell>
                            <TableCell>操作</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {projects.map((project) => (
                            <TableRow key={project.id}>
                                <TableCell>{project.name}</TableCell>
                                <TableCell>{project.description}</TableCell>
                                <TableCell>{project.start_date}</TableCell>
                                <TableCell>{project.end_date}</TableCell>
                                <TableCell>{project.status}</TableCell>
                                <TableCell>
                                    <IconButton onClick={() => handleOpenDialog(project)}>
                                        <EditIcon />
                                    </IconButton>
                                    <IconButton onClick={() => handleDelete(project.id)}>
                                        <DeleteIcon />
                                    </IconButton>
                                    <IconButton onClick={() => navigate(`/documents?project_id=${project.id}`)}>
                                        <UploadFileIcon />
                                    </IconButton>
                                </TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </Paper>

            <Dialog open={openDialog} onClose={handleCloseDialog}>
                <DialogTitle>{currentProject ? '编辑项目' : '创建新项目'}</DialogTitle>
                <DialogContent>
                    <TextField
                        autoFocus
                        margin="dense"
                        name="name"
                        label="项目名称"
                        type="text"
                        fullWidth
                        value={formValues.name}
                        onChange={handleChange}
                    />
                    <TextField
                        margin="dense"
                        name="description"
                        label="项目描述"
                        type="text"
                        fullWidth
                        multiline
                        rows={4}
                        value={formValues.description}
                        onChange={handleChange}
                    />
                    <TextField
                        margin="dense"
                        name="start_date"
                        label="开始日期"
                        type="date"
                        fullWidth
                        InputLabelProps={{
                            shrink: true,
                        }}
                        value={formValues.start_date}
                        onChange={handleChange}
                    />
                    <TextField
                        margin="dense"
                        name="end_date"
                        label="结束日期"
                        type="date"
                        fullWidth
                        InputLabelProps={{
                            shrink: true,
                        }}
                        value={formValues.end_date}
                        onChange={handleChange}
                    />
                    <TextField
                        margin="dense"
                        name="status"
                        label="状态"
                        select
                        fullWidth
                        SelectProps={{
                            native: true,
                        }}
                        value={formValues.status}
                        onChange={handleChange}
                    >
                        {['进行中', '已完成', '已暂停', '已取消'].map((option) => (
                            <option key={option} value={option}>
                                {option}
                            </option>
                        ))}
                    </TextField>
                </DialogContent>
                <DialogActions>
                    <Button onClick={handleCloseDialog} color="primary">
                        取消
                    </Button>
                    <Button onClick={handleSubmit} color="primary">
                        保存
                    </Button>
                </DialogActions>
            </Dialog>
        </Container>
    );
};

export default ProjectsPage;