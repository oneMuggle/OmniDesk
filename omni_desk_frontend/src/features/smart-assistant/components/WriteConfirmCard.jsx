import { useState } from 'react';
import PropTypes from 'prop-types';
import { Alert, Button, Card, Space, Tag, Typography } from 'antd';
import { SafetyCertificateOutlined } from '@ant-design/icons';
import { approveConfirmation, rejectConfirmation, revertWriteLog } from '../api/smartAssistantApi';
import ToolResult from './ToolResult';

const { Text } = Typography;

/** 按钮进行中的状态 */
const BUSY = new Set(['approving', 'rejecting', 'reverting']);

/** 服务端错误码 → 用户可读文案（服务端 detail 优先） */
const FALLBACK_ERRORS = {
  confirmation_expired: '确认已过期，请重新发起',
  confirmation_already_used: '该操作已确认执行，请勿重复提交',
  confirmation_already_rejected: '该操作已取消，请重新发起',
  confirmation_user_mismatch: '只能由发起人确认',
};

function errorText(error, fallback) {
  const data = error?.response?.data || {};
  return data.detail || FALLBACK_ERRORS[data.code] || error?.message || fallback;
}

function showValue(value) {
  if (value === null || value === undefined || value === '') return '—';
  return String(value);
}

/**
 * 写操作确认卡（S3-1）。
 *
 * 展示服务端生成的预览（对象、改动前后、影响范围、权限依据、能否撤销），
 * 只有点「确认执行」才会凭一次性 token 调用确认接口；在对话里说“确认”不会执行。
 * 执行成功且可撤销时提供「撤销」按钮。卡片自带状态，历史消息重新渲染不会重复提交。
 */
const WriteConfirmCard = ({ confirmation }) => {
  const [status, setStatus] = useState('pending');
  const [resultText, setResultText] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const [approved, setApproved] = useState(null);

  if (!confirmation || !confirmation.token) return null;
  const preview = confirmation.preview || null;
  const destructive = preview?.risk === 'destructive';
  const busy = BUSY.has(status);

  const handleApprove = async () => {
    setStatus('approving');
    setErrorMessage('');
    try {
      const { data } = await approveConfirmation(confirmation.token);
      setApproved(data || {});
      setResultText(data?.answer || '操作已完成');
      setStatus('approved');
    } catch (error) {
      setErrorMessage(errorText(error, '执行失败，请稍后重试'));
      // 请求没到服务端（断网等）时允许重试；服务端已处理过的 token 不能再用
      setStatus(error?.response ? 'failed' : 'pending');
    }
  };

  const handleReject = async () => {
    setStatus('rejecting');
    setErrorMessage('');
    try {
      await rejectConfirmation(confirmation.token);
      setStatus('rejected');
    } catch (error) {
      setErrorMessage(errorText(error, '取消失败，请稍后重试'));
      setStatus(error?.response ? 'failed' : 'pending');
    }
  };

  const handleRevert = async () => {
    setStatus('reverting');
    setErrorMessage('');
    try {
      await revertWriteLog(approved.write_log_id);
      setStatus('reverted');
    } catch (error) {
      setErrorMessage(errorText(error, '撤销失败，请稍后重试'));
      setStatus('approved');
    }
  };

  const changes = Array.isArray(preview?.changes) ? preview.changes : [];
  const items = Array.isArray(preview?.items) ? preview.items : [];
  const warnings = Array.isArray(preview?.warnings) ? preview.warnings.filter(Boolean) : [];
  const affected = preview?.affected_label
    || (preview?.affected_count > 1 ? `共 ${preview.affected_count} 项` : '');
  const canRevert = approved?.reversible && approved?.write_log_id
    && (status === 'approved' || status === 'reverting');
  const fileResult = approved?.tool_result?.file_download ? approved.tool_result : null;

  return (
    <Card
      size="small"
      className="write-confirm-card"
      data-testid="write-confirm-card"
      title={(
        <Space size={6} wrap>
          <SafetyCertificateOutlined />
          <span>{preview?.action || '请确认操作'}</span>
          {preview && (
            <Tag color={destructive ? 'red' : 'orange'}>{destructive ? '删除' : '写入'}</Tag>
          )}
          {preview && (
            preview.reversible
              ? <Tag color="green">可撤销</Tag>
              : <Tag>不可撤销</Tag>
          )}
        </Space>
      )}
      style={{ marginTop: 8, maxWidth: 520 }}
    >
      {preview?.target?.label ? (
        <div style={{ marginBottom: 6 }}>
          <Text type="secondary">{preview.target.type || '对象'}：</Text>
          <Text strong>{preview.target.label}</Text>
        </div>
      ) : (
        <div style={{ marginBottom: 6 }}>{confirmation.summary || confirmation.answer || '确认执行该操作吗？'}</div>
      )}

      {changes.length > 0 && (
        <ul className="write-confirm-changes" style={{ margin: '0 0 6px', paddingLeft: 18 }}>
          {changes.map((item) => (
            <li key={item.field || item.label}>
              <Text type="secondary">{item.label || item.field}：</Text>
              <Text delete={item.before !== null && item.before !== undefined}>{showValue(item.before)}</Text>
              <Text> → </Text>
              <Text strong>{showValue(item.after)}</Text>
            </li>
          ))}
        </ul>
      )}

      {affected && <div style={{ marginBottom: 4 }}><Text type="secondary">影响范围：</Text>{affected}</div>}
      {items.length > 0 && (
        <ul style={{ margin: '0 0 6px', paddingLeft: 18 }}>
          {items.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}
        </ul>
      )}
      {warnings.length > 0 && (
        <Alert
          type="warning"
          showIcon
          data-testid="write-confirm-warnings"
          style={{ marginBottom: 6 }}
          message={warnings.length === 1 ? warnings[0] : (
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {warnings.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}
            </ul>
          )}
        />
      )}
      {preview?.permission_source && (
        <div style={{ marginBottom: 6 }}>
          <Text type="secondary">权限依据：{preview.permission_source}</Text>
        </div>
      )}

      {(status === 'pending' || status === 'approving' || status === 'rejecting') && (
        <Space wrap style={{ marginTop: 4 }}>
          <Button
            type="primary"
            danger={destructive}
            size="small"
            loading={status === 'approving'}
            disabled={busy}
            onClick={handleApprove}
          >
            确认执行
          </Button>
          <Button size="small" loading={status === 'rejecting'} disabled={busy} onClick={handleReject}>
            取消
          </Button>
        </Space>
      )}

      {(status === 'approved' || status === 'reverting' || status === 'reverted') && (
        <div data-testid="write-confirm-result" style={{ marginTop: 4 }}>
          <Text type="success">{resultText}</Text>
          {fileResult && <ToolResult intent={approved.tool_used} result={fileResult} />}
        </div>
      )}
      {canRevert && (
        <Button size="small" style={{ marginTop: 6 }} loading={status === 'reverting'} onClick={handleRevert}>
          撤销
        </Button>
      )}

      {status === 'rejected' && (
        <Text type="secondary" data-testid="write-confirm-status">已取消，未做任何修改</Text>
      )}
      {status === 'reverted' && (
        <Text type="secondary" data-testid="write-confirm-status" style={{ display: 'block' }}>已撤销</Text>
      )}
      {errorMessage && (
        <Text type="danger" data-testid="write-confirm-error" style={{ display: 'block', marginTop: 4 }}>
          {errorMessage}
        </Text>
      )}
    </Card>
  );
};

WriteConfirmCard.propTypes = {
  confirmation: PropTypes.shape({
    token: PropTypes.string,
    summary: PropTypes.string,
    answer: PropTypes.string,
    toolUsed: PropTypes.string,
    preview: PropTypes.shape({
      action: PropTypes.string,
      target: PropTypes.shape({ type: PropTypes.string, label: PropTypes.string }),
      changes: PropTypes.arrayOf(PropTypes.shape({
        field: PropTypes.string,
        label: PropTypes.string,
        before: PropTypes.any,
        after: PropTypes.any,
      })),
      affected_count: PropTypes.number,
      affected_label: PropTypes.string,
      permission_source: PropTypes.string,
      reversible: PropTypes.bool,
      risk: PropTypes.string,
      items: PropTypes.arrayOf(PropTypes.string),
      warnings: PropTypes.arrayOf(PropTypes.string),
    }),
  }),
};

/**
 * 把 SSE confirmation 事件转成消息列表里的确认卡消息；没有 token 时返回 null。
 * @param {object} event confirmation 事件
 * @param {string} [toolUsed] meta 事件里的 tool_used
 */
export function toConfirmMessage(event, toolUsed) {
  if (!event || !event.confirmation_token) return null;
  const draft = event.draft || {};
  return {
    id: `confirm-${event.confirmation_token}`,
    type: 'write_confirm',
    role: 'assistant',
    confirmation: {
      token: event.confirmation_token,
      summary: draft.summary,
      answer: event.answer,
      preview: draft.preview || null,
      toolUsed,
    },
  };
}

export default WriteConfirmCard;
