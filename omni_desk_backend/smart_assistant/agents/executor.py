"""MultiAgentExecutor 多 Agent 协作执行器

实现 Pipeline 模式的完整执行流程:
1. 加载 TaskPacket
2. 创建 SharedContext
3. 按拓扑顺序遍历 subtask
4. 对每个 subtask:
   - 等待依赖完成
   - 解析 inputs 中的引用
   - 构造上下文(to_context_for)
   - 调用 LLM(LLMRouter)
   - 解析 LLM 输出(假设是 JSON 或纯文本)
   - 存储到 artifacts
   - 记录 AgentEvent
   - 触发 hooks
   - 处理失败(按 failure_mode)
5. 最终合成(如果 final_synthesis 存在)
6. 保存结果到 AgentTask 模型

当前版本仅实现 Pipeline 模式,后续 milestone 添加 Fan-out / Hierarchical。
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from observability import get_logger

from .dataclasses import (
    Event as Event,
    EventBus as EventBus,
    SubTaskResult as SubTaskResult,
    TaskResult as TaskResult,
)  # re-export(兼容 agents.executor 路径,勿删)
from .roles import RoleProfile
from .shared_context import SharedContext
from .subtask_runner import SubTaskRunner
from .task_packet import ExecutionMode, FailureMode, SubTask, TaskPacket

logger = get_logger(__name__, "smart_assistant")

# 延迟导入,避免循环依赖
# from llm_service.router import LLMRouter
# from tools.registry import ToolRegistry
# from hooks.base import HookRegistry


# ---------------------------------------------------------------------------
# MultiAgentExecutor 主类
# ---------------------------------------------------------------------------


class MultiAgentExecutor:
    """多 Agent 协作执行器

    根据 TaskPacket 驱动任务执行,支持 Pipeline / Fan-out / Hierarchical 三种模式。
    当前版本仅实现 Pipeline 模式。

    Example:
        task_packet = TaskPacket.from_dict(supervisor_output)
        executor = MultiAgentExecutor(
            task_packet=task_packet,
            llm_router=LLMRouter(),
            tool_registry=ToolRegistry,
        )
        result = executor.execute()
        if result.status == "success":
            print(result.final_output)
    """

    MAX_RETRIES = 3  # 默认最大重试次数

    def __init__(
        self,
        task_packet: TaskPacket,
        llm_router: Any,  # LLMRouter 实例
        tool_registry: Any,  # ToolRegistry 类
        hook_registry: Any | None = None,  # HookRegistry 实例(可选)
        event_bus: EventBus | None = None,
        agent_task_id: str | None = None,  # Plan 3: DB 持久化 + 断点恢复用
    ):
        self.task_packet = task_packet
        self.llm_router = llm_router
        self.tool_registry = tool_registry
        self.hook_registry = hook_registry
        self.event_bus = event_bus or EventBus()
        self.agent_task_id = agent_task_id  # Plan 3: DB 持久化用
        self.subtask_runner = SubTaskRunner(llm_router, self.event_bus, self.MAX_RETRIES)
        self._paused = False  # Plan 3: 暂停标志
        self.context = SharedContext(
            original_query=task_packet.objective,
            user_context=task_packet.user_context,
            global_budget=task_packet.global_budget,
        )

    def execute(self) -> TaskResult:
        """执行主任务

        Returns:
            TaskResult 包含所有 subtask 的执行结果和最终产出物
        """
        start_time = time.time()
        self.event_bus.emit("task.started", {"task_id": self.task_packet.task_id})

        try:
            if self.task_packet.execution_mode == ExecutionMode.PIPELINE:
                subtask_results = self._execute_pipeline()
            elif self.task_packet.execution_mode == ExecutionMode.FANOUT:
                # P0-J:未实现模式显式拒绝(rejected 与真实执行失败 failed 区分),
                # 不再抛 NotImplementedError 混入异常路径
                return TaskResult(
                    task_id=self.task_packet.task_id,
                    status="rejected",
                    error_message="fanout 模式尚未实现,请使用 pipeline 模式",
                )
            elif self.task_packet.execution_mode == ExecutionMode.HIERARCHICAL:
                return TaskResult(
                    task_id=self.task_packet.task_id,
                    status="rejected",
                    error_message="hierarchical 模式尚未实现,请使用 pipeline 模式",
                )
            else:
                raise ValueError(f"未知的执行模式: {self.task_packet.execution_mode}")

            # 最终合成(如果有)
            final_output = None
            if self.task_packet.final_synthesis:
                synth_result = self._run_subtask_with_retry(self.task_packet.final_synthesis, self.context)
                subtask_results.append(synth_result)
                if synth_result.status == "success":
                    final_output = synth_result.output
                # Plan 3: 持久化 final_synthesis 到 DB
                self._persist_subtask_result(self.task_packet.final_synthesis, synth_result)

            # 判断任务状态
            failed_count = sum(1 for r in subtask_results if r.status == "failed")
            if failed_count == 0:
                status = "success"
            elif failed_count == len(subtask_results):
                status = "failed"
            else:
                status = "partial"

            total_tokens = sum(r.tokens_used for r in subtask_results)
            total_duration = int((time.time() - start_time) * 1000)

            result = TaskResult(
                task_id=self.task_packet.task_id,
                status=status,
                final_output=final_output,
                subtask_results=subtask_results,
                total_tokens_used=total_tokens,
                total_duration_ms=total_duration,
            )

            self.event_bus.emit(
                "task.completed",
                {
                    "task_id": self.task_packet.task_id,
                    "status": status,
                    "total_tokens": total_tokens,
                    "total_duration_ms": total_duration,
                },
            )

            return result

        except Exception as e:
            total_duration = int((time.time() - start_time) * 1000)
            self.event_bus.emit(
                "task.failed",
                {
                    "task_id": self.task_packet.task_id,
                    "error": str(e),
                },
            )
            return TaskResult(
                task_id=self.task_packet.task_id,
                status="failed",
                total_duration_ms=total_duration,
                error_message=str(e),
            )

    def _execute_pipeline(self, resume_mode: bool = False) -> list[SubTaskResult]:
        """Pipeline 模式执行(顺序执行,前一个输出是后一个输入)

        Args:
            resume_mode: 如果为 True,跳过已完成的 subtask(断点恢复用)

        Returns:
            所有 subtask 的执行结果列表
        """
        results: list[SubTaskResult] = []

        # 获取拓扑排序后的执行顺序
        execution_order = self.task_packet.get_execution_order()

        for subtask in execution_order:
            # Plan 3: 检查暂停标志
            if self._paused:
                self.event_bus.emit(
                    "subtask.skipped",
                    {
                        "subtask_id": subtask.id,
                        "reason": "task_paused",
                    },
                )
                results.append(
                    SubTaskResult(
                        subtask_id=subtask.id,
                        role=subtask.role,
                        output={},
                        status="skipped",
                        error_message="任务已暂停",
                    )
                )
                continue

            # Plan 3: resume 模式下跳过已完成的 subtask
            if resume_mode and self.context.has_artifact(subtask.id):
                self.event_bus.emit(
                    "subtask.skipped",
                    {
                        "subtask_id": subtask.id,
                        "reason": "already_completed_in_checkpoint",
                    },
                )
                # 构造一个"虚拟"的 SubTaskResult 表示已完成
                completed_artifact = self.context.get_artifact(subtask.id)
                results.append(
                    SubTaskResult(
                        subtask_id=subtask.id,
                        role=subtask.role,
                        output=completed_artifact or {},
                        artifacts=completed_artifact or {},
                        status="success",
                    )
                )
                continue

            # 检查 Token 预算
            if self.context.is_budget_exhausted():
                self.event_bus.emit(
                    "subtask.skipped",
                    {
                        "subtask_id": subtask.id,
                        "reason": "token_budget_exhausted",
                    },
                )
                results.append(
                    SubTaskResult(
                        subtask_id=subtask.id,
                        role=subtask.role,
                        output={},
                        status="skipped",
                        error_message="Token 预算已耗尽",
                    )
                )
                continue

            # 检查依赖 subtask 是否成功
            deps_failed = False
            for dep_id in subtask.depends_on:
                dep_result = next((r for r in results if r.subtask_id == dep_id), None)
                if dep_result is None or dep_result.status != "success":
                    deps_failed = True
                    break

            if deps_failed:
                # 依赖失败,根据 failure_mode 决定行为
                if subtask.failure_mode == FailureMode.ABORT:
                    self.event_bus.emit(
                        "task.aborted",
                        {
                            "subtask_id": subtask.id,
                            "reason": "dependency_failed",
                        },
                    )
                    raise RuntimeError(f"Subtask '{subtask.id}' 的依赖失败,任务终止")
                elif subtask.failure_mode == FailureMode.SKIP:
                    self.event_bus.emit(
                        "subtask.skipped",
                        {
                            "subtask_id": subtask.id,
                            "reason": "dependency_failed",
                        },
                    )
                    results.append(
                        SubTaskResult(
                            subtask_id=subtask.id,
                            role=subtask.role,
                            output={},
                            status="skipped",
                            error_message="依赖的 subtask 失败",
                        )
                    )
                    continue
                # FALLBACK / RETRY: 继续执行,让 subtask 自己处理

            # 执行 subtask
            result = self._run_subtask_with_retry(subtask, self.context)
            results.append(result)

            # 存储产物
            if result.status == "success" and result.artifacts:
                self.context.add_artifact(subtask.id, result.artifacts)

            # Plan 3: 持久化到 DB(如果启用)
            self._persist_subtask_result(subtask, result)

        return results

    def _run_subtask_with_retry(self, subtask: SubTask, ctx: SharedContext) -> SubTaskResult:
        """运行单个 subtask,支持重试(委托 SubTaskRunner)"""
        return self.subtask_runner.run_with_retry(subtask, ctx)

    def _run_subtask(self, subtask: SubTask, ctx: SharedContext) -> SubTaskResult:
        """运行单个 subtask(无重试,委托 SubTaskRunner)"""
        return self.subtask_runner.run(subtask, ctx)

    def _invoke_llm_for_subtask(
        self,
        subtask: SubTask,
        profile: RoleProfile,
        messages: list[dict],
    ) -> tuple[str, dict]:
        """调用 LLM 生成 subtask 的输出(委托 SubTaskRunner)"""
        return self.subtask_runner.invoke_llm(subtask, profile, messages)

    def _parse_llm_output(self, content: str, subtask: SubTask) -> tuple[dict | str, dict]:
        """解析 LLM 输出(委托 SubTaskRunner)"""
        return self.subtask_runner.parse_output(content, subtask)

    # ------------------------------------------------------------------
    # Plan 3: DB 持久化 + 断点恢复
    # ------------------------------------------------------------------

    def _persist_subtask_result(self, subtask: SubTask, result: SubTaskResult) -> None:
        """将 subtask 结果持久化到 AgentSubTask DB(如果 agent_task_id 已设置)

        Args:
            subtask: 当前 subtask
            result: 执行结果
        """
        if not self.agent_task_id:
            return  # 未启用 DB 持久化

        # 映射 SubTaskResult.status → AgentSubTask.status
        # SubTaskResult 用 "success/failed/skipped"
        # AgentSubTask 用 "completed/failed/skipped/pending/running"
        status_map = {
            "success": "completed",
            "failed": "failed",
            "skipped": "skipped",
        }
        db_status = status_map.get(result.status, result.status)

        try:
            from django.db import DatabaseError, IntegrityError
            from smart_assistant.models import AgentSubTask, AgentTask

            # 获取 AgentTask
            agent_task = AgentTask.objects.get(task_id=self.agent_task_id)

            # 创建或更新 AgentSubTask
            agent_subtask, created = AgentSubTask.objects.update_or_create(
                task=agent_task,
                subtask_id=subtask.id,
                defaults={
                    "role": subtask.role.value,
                    "objective": subtask.objective,
                    "status": db_status,
                    "depends_on": subtask.depends_on,
                    "inputs": subtask.inputs,
                    "output": result.artifacts if db_status == "completed" else None,
                    "tokens_used": result.tokens_used,
                    "retry_count": result.retry_count,
                    "error_message": result.error_message,
                    "started_at": None,  # 简化:不记录 started_at
                    "completed_at": datetime.now() if db_status == "completed" else None,
                },
            )

            logger.debug(f"Executor: 持久化 SubTask {subtask.id} → DB (status={db_status}, created={created})")

        except (DatabaseError, IntegrityError) as e:
            # 关键 DB 错误(连接断开/约束违反)→ ERROR 级别
            # 注意: 这种情况下 subtask 结果未持久化, resume 时会重新执行
            logger.error(
                f"Executor._persist_subtask_result DB 关键错误(subtask={subtask.id}, status={db_status}): {e}",
                exc_info=True,
            )
        except Exception as e:
            # 非关键错误(字段校验等)→ WARNING,不影响主流程
            logger.warning(f"Executor._persist_subtask_result 出错: {e}", exc_info=True)

    def pause(self) -> None:
        """暂停任务执行(设置暂停标志)

        下一个 subtask 开始前会检查此标志,如果为 True 则停止执行。
        用于实现"优雅暂停",避免中断正在执行的 subtask。
        """
        self._paused = True
        self.event_bus.emit("task.paused", {"task_id": self.task_packet.task_id})
        logger.info(f"Executor: 任务 {self.task_packet.task_id} 已暂停")

        # 更新 DB 状态(如果启用)
        if self.agent_task_id:
            try:
                from django.db import transaction
                from smart_assistant.models import AgentTask

                # 事务保护:确保 status 更新原子性,避免中间状态
                with transaction.atomic():
                    AgentTask.objects.filter(task_id=self.agent_task_id).update(status="paused")
                logger.debug(f"Executor: AgentTask {self.agent_task_id} status → paused (事务提交)")
            except Exception as e:
                logger.warning(f"Executor.pause 更新 DB 出错: {e}", exc_info=True)

    @classmethod
    def resume_from_checkpoint(
        cls,
        task_id: str,
        llm_router: Any,
        tool_registry: Any,
        hook_registry: Any | None = None,
    ) -> TaskResult:
        """从 DB checkpoint 恢复任务执行

        根据 task_id 加载 AgentTask + AgentSubTask,重建 SharedContext,
        从第一个 pending/running 的 subtask 继续执行。

        Args:
            task_id: AgentTask 的 UUID
            llm_router: LLMRouter 实例
            tool_registry: ToolRegistry 类
            hook_registry: HookRegistry 实例(可选)

        Returns:
            TaskResult
        """
        from smart_assistant.models import AgentTask, AgentSubTask
        from .task_packet import TaskPacket
        from django.db import transaction

        # 加载 AgentTask(使用 select_for_update 防并发恢复竞争)
        try:
            with transaction.atomic():
                agent_task = AgentTask.objects.select_for_update().get(task_id=task_id)
                # 防并发: 如果任务已在运行中, 拒绝重复恢复
                if agent_task.status == "running":
                    return TaskResult(
                        task_id=task_id,
                        status="failed",
                        error_message=f"AgentTask {task_id} 已在运行中,拒绝并发恢复",
                    )
        except AgentTask.DoesNotExist:
            return TaskResult(
                task_id=task_id,
                status="failed",
                error_message=f"AgentTask {task_id} 不存在",
            )

        # 反序列化 TaskPacket
        try:
            task_packet = TaskPacket.from_dict(agent_task.task_packet)
        except Exception as e:
            return TaskResult(
                task_id=task_id,
                status="failed",
                error_message=f"TaskPacket 反序列化失败: {e}",
            )

        # 创建 executor
        executor = cls(
            task_packet=task_packet,
            llm_router=llm_router,
            tool_registry=tool_registry,
            hook_registry=hook_registry,
            agent_task_id=task_id,
        )

        # 加载已完成的 subtask,重建 SharedContext
        completed_subtasks = AgentSubTask.objects.filter(
            task=agent_task,
            status="completed",
        )

        for agent_subtask in completed_subtasks:
            if agent_subtask.output:
                executor.context.add_artifact(agent_subtask.subtask_id, agent_subtask.output)
                executor.context.consume_tokens(agent_subtask.tokens_used)

        logger.info(
            f"Executor.resume: 从 checkpoint 恢复任务 {task_id}, "
            f"已重建 {len(completed_subtasks)} 个 completed subtask 的 artifacts"
        )

        # 更新任务状态为 running(事务保护)
        from django.db import transaction

        with transaction.atomic():
            agent_task.status = "running"
            agent_task.save()
        logger.debug(f"Executor.resume: AgentTask {task_id} status → running (事务提交)")

        # 继续执行(跳过已完成的 subtask)
        return executor._execute_resume()

    def _execute_resume(self) -> TaskResult:
        """从 checkpoint 恢复执行(跳过已完成的 subtask)

        与 execute() 类似,但会检查 self.context.artifacts 判断哪些 subtask 已完成。

        Returns:
            TaskResult
        """
        start_time = time.time()
        self.event_bus.emit("task.resumed", {"task_id": self.task_packet.task_id})

        try:
            # 只执行 PIPELINE 模式(resume 暂不支持其他模式)
            if self.task_packet.execution_mode != ExecutionMode.PIPELINE:
                raise ValueError(f"resume 仅支持 PIPELINE 模式,当前: {self.task_packet.execution_mode}")

            # 执行 pipeline,自动跳过已完成的 subtask
            subtask_results = self._execute_pipeline(resume_mode=True)

            # 最终合成
            final_output = None
            if self.task_packet.final_synthesis:
                # 检查 final_synthesis 是否已完成
                if not self.context.has_artifact(self.task_packet.final_synthesis.id):
                    synth_result = self._run_subtask_with_retry(self.task_packet.final_synthesis, self.context)
                    subtask_results.append(synth_result)
                    if synth_result.status == "success":
                        final_output = synth_result.output
                else:
                    # 已完成,从 context 中取
                    final_output = self.context.get_artifact(self.task_packet.final_synthesis.id)

            # 判断状态
            failed_count = sum(1 for r in subtask_results if r.status == "failed")
            if failed_count == 0:
                status = "success"
            elif failed_count == len(subtask_results):
                status = "failed"
            else:
                status = "partial"

            total_tokens = sum(r.tokens_used for r in subtask_results)
            total_duration = int((time.time() - start_time) * 1000)

            result = TaskResult(
                task_id=self.task_packet.task_id,
                status=status,
                final_output=final_output,
                subtask_results=subtask_results,
                total_tokens_used=total_tokens,
                total_duration_ms=total_duration,
            )

            self.event_bus.emit(
                "task.completed",
                {
                    "task_id": self.task_packet.task_id,
                    "status": status,
                    "total_tokens": total_tokens,
                    "total_duration_ms": total_duration,
                    "resumed": True,
                },
            )

            return result

        except Exception as e:
            total_duration = int((time.time() - start_time) * 1000)
            self.event_bus.emit(
                "task.failed",
                {
                    "task_id": self.task_packet.task_id,
                    "error": str(e),
                    "resumed": True,
                },
            )
            return TaskResult(
                task_id=self.task_packet.task_id,
                status="failed",
                total_duration_ms=total_duration,
                error_message=str(e),
            )
