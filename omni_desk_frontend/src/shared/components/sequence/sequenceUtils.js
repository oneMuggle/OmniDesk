// 序列 payload 构建纯函数:create/update × personnel/leader 4 分支
// 从 SequenceManager.jsx handleSave 提取,行为逐字保留(纯拆分,零变化)

export const buildSequencePayload = (values, isEditingLeader) => {
  if (!isEditingLeader && values.id) {
    // 人员顺序 UPDATE:合并 sequence + holiday_sequence 去重为 personnel
    const personnelIds = [...new Set([
      ...(values.sequence || []),
      ...(values.holiday_sequence || [])
    ])];
    return { ...values, personnel: personnelIds };
  }
  if (isEditingLeader) {
    // 领导顺序(create/update 一致):补 personnel 字段
    return { ...values, personnel: values.sequence };
  }
  // 人员顺序 CREATE:rename sequence → personnel
  const { sequence, ...rest } = values;
  return { ...rest, personnel: sequence };
};
