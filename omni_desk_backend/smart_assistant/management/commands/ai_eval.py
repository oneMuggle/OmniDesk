"""AI 助手评估集与发布门禁（方案 5.6 / S0）。

在**独立的临时测试库**里造种子数据（5 个角色、带标记的受保护数据、注入载体），逐条用例以
对应角色经真实接口 ``/api/smart-assistant/chat/`` 执行，统计越权与质量指标。不读写生产数据；
评估从不点「确认」，任何真实写入都算违规。

用法:
    # 剧本模式（模拟 LLM，CI 门禁）：越权或用例自检失败时退出码 1
    python manage.py ai_eval --fail-on-violation

    # 真模型：对当前配置的端点跑，两条路径（原生 / 旧 JSON）都跑，报告与仓库基线对比
    python manage.py ai_eval --mode live --from-config

    # 多端点 / 多模型对比；密钥从环境变量读
    python manage.py ai_eval --mode live \\
        --target name=qwen72b,url=https://llm.example.com,model=qwen2.5-72b,key_env=QWEN_KEY \\
        --target name=glm4,url=https://llm2.example.com,model=glm-4,key_env=GLM_KEY \\
        --repeat 3 --out ai-eval-reports/2026-10

    # 只跑部分用例（id 或类别，支持通配符）
    python manage.py ai_eval --cases privilege,inj-*

    # 把本次结果写成新基线（人工确认后提交）
    python manage.py ai_eval --mode live --from-config --write-baseline --note "Qwen2.5-72B 上线版"
"""

from __future__ import annotations

import sys
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from smart_assistant.evals.cases import CaseError
from smart_assistant.evals.harness import PATH_LABELS, PATHS
from smart_assistant.evals.report import (
    BASELINE_PATH,
    compare_to_baseline,
    gate_passed,
    load_baseline,
    make_baseline,
    write_report,
)


class Command(BaseCommand):
    help = "AI 助手评估：在临时测试库里跑评估用例，输出越权与质量报告（剧本 / 真模型两种模式）"

    def add_arguments(self, parser):
        parser.add_argument(
            "--mode",
            choices=("scripted", "live"),
            default="scripted",
            help="scripted=模拟 LLM（默认，CI 用）；live=调用真实端点",
        )
        parser.add_argument(
            "--target", action="append", default=[], help="真模型目标，可重复：name=…,url=…,model=…,key_env=…[,cost=…]"
        )
        parser.add_argument(
            "--from-config", action="store_true", help="真模型模式下把当前库里智能助手正在用的端点加入目标"
        )
        parser.add_argument(
            "--paths",
            default=",".join(PATHS),
            help="要跑的路径，逗号分隔：native（原生函数调用）、json（旧 JSON 路径）",
        )
        parser.add_argument("--cases", default="", help="只跑匹配的用例 id 或类别，逗号分隔，支持通配符")
        parser.add_argument("--repeat", type=int, default=1, help="每条用例重复次数（真模型看稳定性）")
        parser.add_argument("--out", default="", help="报告输出目录（默认 ai-eval-reports/<时间>）")
        parser.add_argument("--baseline", default="", help=f"基线文件（默认 {BASELINE_PATH.name}）")
        parser.add_argument(
            "--write-baseline", action="store_true", help="把本次结果写入基线（按「目标/路径」合并，其余目标保留）"
        )
        parser.add_argument("--note", default="", help="写基线时附带的说明")
        parser.add_argument(
            "--fail-on-violation", action="store_true", help="越权不为 0（剧本模式还包括用例自检失败）时退出码 1"
        )

    def handle(self, *args, **options):
        from smart_assistant.evals.suite import parse_target, run_suite, select_cases, target_from_config

        mode = options["mode"]
        paths = tuple(p.strip() for p in options["paths"].split(",") if p.strip())
        bad_paths = [p for p in paths if p not in PATHS]
        if not paths or bad_paths:
            raise CommandError(f"--paths 只能是 {', '.join(PATHS)}")
        if options["repeat"] < 1:
            raise CommandError("--repeat 至少为 1")

        targets = []
        if mode == "live":
            try:
                targets = [parse_target(spec) for spec in options["target"]]
            except ValueError as exc:
                raise CommandError(str(exc)) from exc
            if options["from_config"]:
                # 必须在切换到临时库之前读取
                current = target_from_config()
                if current is None:
                    raise CommandError("当前库里没有启用的智能助手端点配置")
                targets.insert(0, current)
            if not targets:
                raise CommandError("真模型模式需要 --target 或 --from-config")
        elif options["target"] or options["from_config"]:
            self.stderr.write("剧本模式忽略 --target / --from-config")

        try:
            cases = select_cases([p for p in options["cases"].split(",") if p.strip()])
        except CaseError as exc:
            raise CommandError(str(exc)) from exc
        if not cases:
            raise CommandError("没有匹配的用例")

        self.stdout.write(
            f"评估：{mode}，{len(cases)} 条用例 × 路径 {', '.join(paths)} × 目标 "
            f"{', '.join(t.name for t in targets) or 'scripted'} × 重复 {options['repeat']}"
        )

        def on_result(r):
            mark = "✗" if r.violations else ("·" if r.scripted_ok or mode == "live" else "?")
            self.stdout.write(mark, ending="")
            self.stdout.flush()

        suite = self._run_in_test_database(
            lambda: run_suite(
                cases, mode=mode, targets=targets, paths=paths, repeat=options["repeat"], on_result=on_result
            )
        )
        self.stdout.write("")
        report = suite.report

        baseline_path = Path(options["baseline"]) if options["baseline"] else BASELINE_PATH
        comparison = compare_to_baseline(report, load_baseline(baseline_path))
        out_dir = Path(options["out"] or Path("ai-eval-reports") / timezone.localtime().strftime("%Y%m%d-%H%M%S"))
        json_path, md_path = write_report(report, out_dir, comparison=comparison)

        self._print_summary(report, comparison)
        self.stdout.write(f"报告：{md_path}  {json_path}")

        if options["write_baseline"]:
            import json

            merged = make_baseline(report, note=options["note"], existing=load_baseline(baseline_path))
            baseline_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"已写入基线 {baseline_path}"))

        passed = gate_passed(report, require_scripted_ok=(mode == "scripted"))
        if passed:
            self.stdout.write(self.style.SUCCESS("门禁通过：越权 0"))
        else:
            self.stdout.write(
                self.style.ERROR(
                    f"门禁未通过：越权 {report['violation_total']} 条"
                    + ("，或有用例自检失败（见报告「未达预期的用例」）" if mode == "scripted" else "")
                )
            )
            if options["fail_on_violation"]:
                sys.exit(1)

    def _run_in_test_database(self, fn):
        """建临时测试库（与 pytest 相同的 test_ 前缀库），跑完即销毁；从不连接生产数据。"""
        from django.test.utils import (
            setup_databases,
            setup_test_environment,
            teardown_databases,
            teardown_test_environment,
        )

        setup_test_environment()
        old_config = setup_databases(verbosity=0, interactive=False)
        try:
            return fn()
        finally:
            teardown_databases(old_config, verbosity=0)
            teardown_test_environment()

    def _print_summary(self, report, comparison):
        for key, s in report["summary"].items():
            self.stdout.write(
                f"  {s['target']} / {PATH_LABELS.get(s['path'], s['path'])}：用例 {s['cases']}，越权 {s['violation_total']}，"
                f"工具选择 {s['tool_selection']}%，数据完整 {s['visible']}%，P95 {s['p95_ms']}ms"
            )
        worse = [r for r in comparison if r["worse"]]
        if worse:
            self.stdout.write(
                self.style.WARNING(
                    "  与基线相比变差："
                    + "；".join(f"{r['key']} {r['label']} {r['baseline']}→{r['current']}" for r in worse)
                )
            )
