/**
 * 剪贴板工具(R5-C2:替代 react-copy-to-clipboard 依赖)。
 *
 * 优先使用异步 Clipboard API(Chrome 66+,Chrome 109 完整支持);
 * 在非安全上下文(http 内网部署)下 navigator.clipboard 可能不可用,
 * 回退到 document.execCommand('copy')(Chrome 109 仍支持,未废弃移除)。
 *
 * @param {string} text 要复制的文本
 * @returns {Promise<boolean>} 是否复制成功
 */
export async function copyToClipboard(text) {
  // 首选:异步 Clipboard API(仅安全上下文 https/localhost 暴露)
  if (typeof navigator !== 'undefined' && navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (err) {
      // 权限被拒或写入失败时降级到 execCommand
    }
  }

  // 回退:隐藏 textarea + execCommand(兼容 http 内网环境)
  try {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    // 避免滚动跳动:固定在视口内但不可见
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    textarea.setAttribute('readonly', '');
    document.body.appendChild(textarea);
    textarea.select();
    const ok = document.execCommand('copy');
    document.body.removeChild(textarea);
    return ok;
  } catch (err) {
    return false;
  }
}

export default copyToClipboard;
