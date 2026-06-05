/**
 * 共享 API 类型定义(TypeScript 试点)
 *
 * 这是一个**纯类型声明文件**,不参与运行时,仅供 IDE / tsc 类型检查使用。
 * 后续 .ts / .tsx 新文件可 import 这些类型,获得 IntelliSense 与编译期检查。
 *
 * **当前是试点**(2026-06),核心约束:
 * - 不动现有 .js / .jsx 文件
 * - 不强制团队写 TS(渐进式)
 * - 不引入 TypeScript 编译到生产构建(Vite 默认会处理 .ts,但本项目不主动开启)
 */

/** 统一 API 响应格式(对应后端 DRF 的常见 envelope) */
export interface ApiResponse<T> {
  data: T;
  status?: number;
  statusText?: string;
}

/** 列表 API 通用分页响应 */
export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

/** 分页查询参数 */
export interface PaginationParams {
  page?: number;
  page_size?: number;
  search?: string;
  ordering?: string;
}

/** 通用错误响应 */
export interface ApiError {
  status: number;
  statusText: string;
  data?: unknown;
  message: string;
}

/** 时间段选择器值(常见于排班/试验场景) */
export interface TimeRange {
  start: string; // ISO 8601
  end: string;   // ISO 8601
}

/** 通用 ID 关联 */
export interface IdRef {
  id: number;
  label?: string;
}
