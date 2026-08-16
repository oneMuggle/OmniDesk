/**
 * 上传文件公共校验(R4-B5)。
 *
 * 统一文件大小上限与错误文案,消除 FileAttachmentInput / FileUploadSection
 * 各自内联 `10 * 1024 * 1024` 的重复。
 */

/** 附件/上传文件大小上限(10MB) */
export const MAX_UPLOAD_SIZE = 10 * 1024 * 1024;

/** 超限统一提示文案 */
export const FILE_TOO_LARGE_MESSAGE = '文件超过 10MB 上限';

/**
 * 校验文件大小是否超限。
 * @param {{name?: string, size?: number}|File} [file]
 * @param {number} [maxSize] 自定义上限,默认 10MB
 * @returns {{ok: boolean, reason?: string}}
 */
export function validateFileSize(file, maxSize = MAX_UPLOAD_SIZE) {
  if ((file?.size ?? 0) > maxSize) {
    return { ok: false, reason: FILE_TOO_LARGE_MESSAGE };
  }
  return { ok: true };
}