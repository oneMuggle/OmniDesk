/**
 * 日历工具函数
 */
import { logger } from '../../../shared/utils/logger';

// 基于trialId生成HSL颜色 (改进版)
export const getTrialColor = (trialId) => {
  // djb2哈希算法
  let hash = 5381;
  for (let i = 0; i < String(trialId).length; i++) {
    hash = (hash * 33) ^ String(trialId).charCodeAt(i);
  }
  
  // 使用黄金角度分布色相 (137.5°)
  const hue = (hash * 137.5) % 360;
  // 使用正常饱和度和亮度
  const saturation = 85; // 正常饱和度
  const lightness = 55; // 正常亮度
  
  return `hsl(${hue}, ${saturation}%, ${lightness}%)`;
};

// 状态配置对象
export const trialStatusConfig = {
  planned: {
    color: '#1890ff', // 蓝色
    text: '已计划', 
    icon: '🗓️',
    badgeStyle: { backgroundColor: '#1890ff' }
  },
  in_progress: {
    color: '#52c41a', // 绿色
    text: '进行中',
    icon: '🔄',
    badgeStyle: { backgroundColor: '#52c41a' }
  },
  completed: {
    color: '#888', // 灰色
    text: '已完成',
    icon: '✅',
    badgeStyle: { backgroundColor: '#888' }
  },
  cancelled: {
    color: '#ff4d4f', // 红色
    text: '已取消',
    icon: '❌',
    badgeStyle: { backgroundColor: '#ff4d4f' }
  }
};

export const getStatusConfig = (status) =>
  trialStatusConfig[status] || {
    color: '#d3d3d3',
    text: '未知状态',
    icon: '❓',
    badgeStyle: { backgroundColor: '#d3d3d3' }
  };

export const extractSlotId = (compositeId) => {
  
  // 处理 'trial-1-0' 格式 (提取 slotId)
  if (typeof compositeId === 'string' && compositeId.startsWith('trial-')) {
    const match = compositeId.match(/trial-(\d+)-(\d+)/);
    if (match) {
      const trialId = parseInt(match[1]);
      const slotIndex = parseInt(match[2]);
      return { trialId, slotIndex };
    }
    return null;
  }
  
  // 处理 'slot_1' 格式 (提取 slotId)
  if (typeof compositeId === 'string' && compositeId.startsWith('slot_')) {
    const id = parseInt(compositeId.replace('slot_', ''));
    return { slotId: id };
  }
  
  // 处理 '1-0' 格式 (提取 trialId 和 slotIndex)
  if (typeof compositeId === 'string' && /^\d+-\d+$/.test(compositeId)) {
    const [trialId, slotIndex] = compositeId.split('-').map(Number);
    return { trialId, slotIndex };
  }
  
  // 处理直接数字ID
  if (!isNaN(parseInt(compositeId))) {
    const id = parseInt(compositeId);
    return { slotId: id };
  }
  
  logger.error('[ERROR] 无法解析ID:', compositeId);
  throw new Error(`无效的时间段ID格式: ${compositeId}`);
};
