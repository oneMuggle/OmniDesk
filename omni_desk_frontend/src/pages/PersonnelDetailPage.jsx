import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getPersonnelDetails } from '../api/personnelApi';
import { Descriptions, Table, Spin, message, Button, Card } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import { ProfessionalQualificationTable, FamilyMemberTable } from '../components/Personnel';

const PersonnelDetailPage = () => {
    const { id } = useParams();
    const [personnel, setPersonnel] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchDetails = async () => {
            try {
                setLoading(true);
                const personnelRes = await getPersonnelDetails(id);
                setPersonnel(personnelRes.data);
            } catch (error) {
                message.error('获取人员详细信息失败');
            } finally {
                setLoading(false);
            }
        };
        fetchDetails();
    }, [id]);

    const contractColumns = [
        { title: '合同编号', dataIndex: 'contract_number', key: 'contract_number' },
        { title: '合同类型', dataIndex: 'contract_type', key: 'contract_type' },
        { title: '开始日期', dataIndex: 'start_date', key: 'start_date' },
        { title: '结束日期', dataIndex: 'end_date', key: 'end_date' },
    ];

    const educationColumns = [
        { title: '毕业院校', dataIndex: 'school', key: 'school' },
        { title: '学历', dataIndex: 'degree', key: 'degree' },
        { title: '专业', dataIndex: 'major', key: 'major' },
        { title: '开始日期', dataIndex: 'start_date', key: 'start_date' },
        { title: '结束日期', dataIndex: 'end_date', key: 'end_date' },
    ];

    const workExperienceColumns = [
        { title: '公司名称', dataIndex: 'company', key: 'company' },
        { title: '职位', dataIndex: 'position', key: 'position' },
        { title: '开始日期', dataIndex: 'start_date', key: 'start_date' },
        { title: '结束日期', dataIndex: 'end_date', key: 'end_date' },
        { title: '工作描述', dataIndex: 'description', key: 'description' },
    ];

    if (loading) {
        return <div className="flex justify-center items-center h-screen"><Spin size="large" data-testid="loading-spinner" /></div>;
    }

    if (!personnel) {
        return <div className="text-center mt-10">未找到人员信息。</div>;
    }

    return (
        <div className="p-8 bg-gray-100 min-h-screen">
            <Card>
                <div className="flex justify-between items-center mb-6">
                    <h1 className="text-2xl font-bold">人员信息详情</h1>
                    <Link to="/control-panel/personnel">
                        <Button icon={<ArrowLeftOutlined />}>返回列表</Button>
                    </Link>
                </div>

                <Descriptions title="基本信息" bordered column={2}>
                    <Descriptions.Item label="姓名">{personnel.name}</Descriptions.Item>
                    <Descriptions.Item label="身份证号">{personnel.id_card_number}</Descriptions.Item>
                    <Descriptions.Item label="出生年月">{personnel.date_of_birth}</Descriptions.Item>
                    <Descriptions.Item label="联系电话">{personnel.phone_number}</Descriptions.Item>
                    <Descriptions.Item label="家庭住址" span={2}>{personnel.address}</Descriptions.Item>
                    <Descriptions.Item label="部门">{personnel.department}</Descriptions.Item>
                    <Descriptions.Item label="职位">{personnel.position ? personnel.position.name : '未分配'}</Descriptions.Item>
                    <Descriptions.Item label="入职日期">{personnel.hire_date}</Descriptions.Item>
                    <Descriptions.Item label="员工状态">{personnel.status}</Descriptions.Item>
                </Descriptions>

                <h2 className="text-xl font-semibold mt-8 mb-4">合同信息</h2>
                <Table dataSource={personnel.contracts || []} columns={contractColumns} rowKey="id" pagination={false} bordered />

                <h2 className="text-xl font-semibold mt-8 mb-4">教育背景</h2>
                <Table dataSource={personnel.educations || []} columns={educationColumns} rowKey="id" pagination={false} bordered />

                <h2 className="text-xl font-semibold mt-8 mb-4">工作经历</h2>
                <Table dataSource={personnel.work_experiences || []} columns={workExperienceColumns} rowKey="id" pagination={false} bordered />

                <h2 className="text-xl font-semibold mt-8 mb-4">职业资质</h2>
                <ProfessionalQualificationTable personnelId={parseInt(id, 10)} />

                <h2 className="text-xl font-semibold mt-8 mb-4">家庭成员</h2>
                <FamilyMemberTable personnelId={parseInt(id, 10)} />
            </Card>
        </div>
    );
};

export default PersonnelDetailPage;