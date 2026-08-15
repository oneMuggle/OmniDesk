import React, { useState, useEffect } from 'react';
import { message, Row, Col } from 'antd';
import {
  getPersonnelSequences, createPersonnelSequence, updatePersonnelSequence, deletePersonnelSequence,
  getLeaderSequences, createLeaderSequence, updateLeaderSequence, deleteLeaderSequence
} from '../api/sequenceApi';
import { getAllPersonnel, getPositions } from '../../features/personnel/api/personnelApi';
import { DragDropContext } from '@hello-pangea/dnd';
import { logger } from '../utils/logger';
import SequenceForm from './sequence/SequenceForm';
import SequenceList from './sequence/SequenceList';
import { buildSequencePayload } from './sequence/sequenceUtils';

const SequenceManager = () => {
  const [personnelSequences, setPersonnelSequences] = useState([]);
  const [leaderSequences, setLeaderSequences] = useState([]);
  const [allPersonnel, setAllPersonnel] = useState([]);
  const [positions, setPositions] = useState([]);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [editingSequence, setEditingSequence] = useState(null);
  const [isEditingLeader, setIsEditingLeader] = useState(false);
  const [selectedPersonnelInModal, setSelectedPersonnelInModal] = useState([]);

  const fetchData = React.useCallback(async () => {
    try {
      const [personnelRes, leaderRes, personnelListRes, positionsRes] = await Promise.all([
        getPersonnelSequences(),
        getLeaderSequences(),
        getAllPersonnel(),
        getPositions()
      ]);
      setPersonnelSequences(Array.isArray(personnelRes?.data?.results) ? personnelRes.data.results : []);
      setLeaderSequences(Array.isArray(leaderRes?.data?.results) ? leaderRes.data.results : []);
      setAllPersonnel(personnelListRes?.data?.results || []);
      setPositions(positionsRes?.data?.results || []);
    } catch (error) {
      message.error("数据加载失败，请刷新页面重试。");
      logger.error("Failed to fetch data", error);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchData();
  }, [fetchData]);

  const handleAdd = (isLeader) => {
    setEditingSequence(null);
    setIsEditingLeader(isLeader);
    setIsModalVisible(true);
  };

  const handleEdit = (sequence, isLeader) => {
    setEditingSequence(sequence);
    setIsEditingLeader(isLeader);
    setIsModalVisible(true);
  };

  const handleDelete = async (id, isLeader) => {
    const apiCall = isLeader ? deleteLeaderSequence : deletePersonnelSequence;
    try {
      await apiCall(id);
      message.success('删除成功');
      fetchData();
    } catch (error) {
      message.error('删除失败');
      logger.error("Failed to delete sequence", error);
    }
  };

  const handleSave = async (values) => {
    const isUpdate = !!values.id;
    const apiCall = isEditingLeader
      ? (isUpdate ? updateLeaderSequence : createLeaderSequence)
      : (isUpdate ? updatePersonnelSequence : createPersonnelSequence);

    try {
      const payload = buildSequencePayload(values, isEditingLeader);

      if (isUpdate) {
        await apiCall(values.id, payload);
      } else {
        await apiCall(payload);
      }

      message.success('保存成功');
      setIsModalVisible(false);
      fetchData();
    } catch (error) {
      message.error('保存失败');
      logger.error("Failed to save sequence", error);
    }
  };

  const onDragEnd = (result) => {
    if (!result.destination) return;
    const items = Array.from(selectedPersonnelInModal);
    const [reorderedItem] = items.splice(result.source.index, 1);
    items.splice(result.destination.index, 0, reorderedItem);
    setSelectedPersonnelInModal(items);
  };

  const handleCancel = () => {
    setIsModalVisible(false);
    setEditingSequence(null);
  };

  return (
    <>
      <Row gutter={16}>
        <Col span={12}>
          <SequenceList
            title="人员顺序"
            sequences={personnelSequences}
            personnelList={allPersonnel}
            onAdd={handleAdd}
            onEdit={handleEdit}
            onDelete={handleDelete}
            isLeader={false}
          />
        </Col>
        <Col span={12}>
          <SequenceList
            title="领导顺序"
            sequences={leaderSequences}
            personnelList={allPersonnel}
            onAdd={handleAdd}
            onEdit={handleEdit}
            onDelete={handleDelete}
            isLeader={true}
          />
        </Col>
      </Row>

      <DragDropContext onDragEnd={onDragEnd}>
        {isModalVisible && (
          <SequenceForm
            open={isModalVisible}
            onCancel={handleCancel}
            onSave={handleSave}
            sequence={editingSequence}
            personnelList={allPersonnel}
            isLeader={isEditingLeader}
            positions={positions}
            selectedPersonnel={selectedPersonnelInModal}
            setSelectedPersonnel={setSelectedPersonnelInModal}
          />
        )}
      </DragDropContext>
    </>
  );
};

export default SequenceManager;
