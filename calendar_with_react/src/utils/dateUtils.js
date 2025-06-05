import dayjs from 'dayjs';
import utc from 'dayjs-plugin-utc';

dayjs.extend(utc);

// 确保所有日期都是 dayjs 实例
const ensureDayjs = (date) => {
  if (!date) return dayjs(); // 处理 null/undefined
  
  if (typeof date === 'string' || date instanceof Date) {
    return dayjs(date);
  }
  
  // 已经是 dayjs 实例
  if (date && typeof date.isValid === 'function') {
    return date;
  }
  
  // 其他情况尝试转换
  return dayjs(date);
};

// 1. 日期解析 - 处理多种输入类型
export const parseDate = (input) => {
  try {
    const parsed = ensureDayjs(input);
    return isValidDate(parsed) ? parsed : null;
  } catch {
    return null;
 }
};

// 2. 日期格式化
export const formatDate = (date, format = 'YYYY-MM-DD') => {
  const parsed = parseDate(date);
  return parsed ? parsed.format(format) : '';
};

// 3. 日期验证
export const isValidDate = (date) => {
  try {
    const parsed = ensureDayjs(date);
    return parsed && typeof parsed.isValid === 'function' && parsed.isValid();
  } catch {
    return false;
  }
};

// 4. 转换为后端格式 (ISO 8601 with timezone)
export const toServerFormat = (date) => {
  const parsed = parseDate(date);
  return parsed ? parsed.format() : null; // 使用本地时间格式
};

// 5. 从后端格式解析 (支持带时区和数组输入)
export const fromServerFormat = (dateInput) => {
  if (!dateInput) return null;
  
  // 处理数组输入
  if (Array.isArray(dateInput)) {
    return dateInput.map(d => {
      try {
        return dayjs(d).utc().local();
      } catch (e) {
        console.error('Invalid date format in array:', d);
        return null;
      }
    });
  }
  
  // 处理单个日期输入
  try {
    return dayjs(dateInput).utc().local();
  } catch (e) {
    console.error('Invalid date format:', dateInput);
    return null;
  }
};

// 6. 日期比较
export const isBefore = (date, compareDate) => {
  const d1 = parseDate(date);
  const d2 = parseDate(compareDate);
  return d1 && d2 ? d1.isBefore(d2) : false;
};

// 7. 日期加减
export const addDays = (date, days) => {
  const parsed = parseDate(date);
  return parsed ? parsed.add(days, 'days') : null;
};

export const validateEndDate = (date) => {
  return isValidDate(date) ? date : null;
};

export const validateStartDate = (date) => {
  return isValidDate(date) ? date : null;
};
