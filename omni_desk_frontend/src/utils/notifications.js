import { message } from 'antd';

export const notifications = {
  showError: (content, duration = 5) => {
    message.error({
      content,
      duration,
      style: { marginTop: '50vh' },
    });
  },
  showSuccess: (content, duration = 3) => {
    message.success({
      content,
      duration,
      style: { marginTop: '50vh' },
    });
  },
};