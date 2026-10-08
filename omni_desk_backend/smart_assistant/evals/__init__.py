"""智能助手评估集与发布门禁（方案 5.6 / S0）。

- ``cases``：评估用例（YAML）的加载与校验；
- ``seed``：独立测试库里的种子数据与「不该被看到」的标记字符串；
- ``llm``：LLM 拦截点（剧本模式的模拟 LLM / 真模型模式的记录转发）；
- ``harness``：逐条用例经真实视图执行，记录工具执行、LLM 请求与响应；
- ``scoring``：安全门禁（越权数必须为 0）与质量、性能指标；
- ``report``：JSON / Markdown 报告与基线对比。

入口：``python manage.py ai_eval``（见 docs/plans/2026-09-28_ai-eval-s0.md）。
"""
