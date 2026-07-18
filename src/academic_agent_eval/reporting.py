"""Self-contained HTML reporting for completed experiments."""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from pathlib import Path

from academic_agent_eval.evaluator import EvaluationSummary, QueryEvaluation


class HtmlReporter:
    """Render a portable report with no external CSS, JavaScript, or font assets."""

    def write(
        self,
        path: Path,
        *,
        run_id: str,
        experiment_name: str,
        agent_name: str,
        agent_version: str,
        dataset_name: str,
        summary: EvaluationSummary,
        evaluations: list[QueryEvaluation],
        query_texts: dict[str, str],
    ) -> None:
        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        success_rate = summary.successful_queries / summary.query_count
        rows = "".join(
            self._query_row(item, query_texts.get(item.query_id, "")) for item in evaluations
        )
        html = _TEMPLATE
        replacements = {
            "{{TITLE}}": escape(f"{experiment_name} · AcademicAgentEval"),
            "{{EXPERIMENT}}": escape(experiment_name),
            "{{RUN_ID}}": escape(run_id),
            "{{AGENT}}": escape(agent_name),
            "{{AGENT_VERSION}}": escape(agent_version),
            "{{DATASET}}": escape(dataset_name),
            "{{PROTOCOL}}": escape(summary.matching_protocol),
            "{{GENERATED_AT}}": escape(generated_at),
            "{{QUERY_COUNT}}": str(summary.query_count),
            "{{SUCCESSFUL_QUERIES}}": str(summary.successful_queries),
            "{{FAILED_QUERIES}}": str(summary.failed_queries),
            "{{SUCCESS_RATE}}": self._percent(success_rate),
            "{{MACRO_PRECISION}}": self._percent(summary.macro_precision),
            "{{MACRO_RECALL}}": self._percent(summary.macro_recall),
            "{{MACRO_F1}}": self._percent(summary.macro_f1),
            "{{MACRO_F1_VALUE}}": self._safe_width(summary.macro_f1),
            "{{MICRO_PRECISION}}": self._percent(summary.micro_precision),
            "{{MICRO_RECALL}}": self._percent(summary.micro_recall),
            "{{MICRO_F1}}": self._percent(summary.micro_f1),
            "{{MICRO_F1_VALUE}}": self._safe_width(summary.micro_f1),
            "{{TRUE_POSITIVES}}": str(summary.true_positives),
            "{{FALSE_POSITIVES}}": str(summary.false_positives),
            "{{FALSE_NEGATIVES}}": str(summary.false_negatives),
            "{{MEAN_LATENCY}}": self._duration(summary.mean_latency_ms),
            "{{P50_LATENCY}}": self._duration(summary.p50_latency_ms),
            "{{P95_LATENCY}}": self._duration(summary.p95_latency_ms),
            "{{LLM_CALLS}}": f"{summary.total_llm_calls:,}",
            "{{API_CALLS}}": f"{summary.total_api_calls:,}",
            "{{TOKENS}}": f"{summary.total_tokens:,}",
            "{{COST}}": self._cost(summary.total_estimated_cost_usd),
            "{{QUERY_ROWS}}": rows,
        }
        for placeholder, value in replacements.items():
            html = html.replace(placeholder, value)
        path.write_text(html, encoding="utf-8")

    def _query_row(self, item: QueryEvaluation, query_text: str) -> str:
        status_class = "success" if item.status == "success" else "failed"
        status_text = "成功" if item.status == "success" else "失败"
        search_text = escape(f"{item.query_id} {query_text}", quote=True).casefold()
        matches = "".join(
            '<li><span class="match-title">'
            f"{escape(match.predicted_title)}"
            '</span><span class="arrow">→</span>'
            f"{escape(match.ground_truth_title)}"
            f"<code>{escape(match.method)}</code></li>"
            for match in item.matches
        )
        if not matches:
            matches = '<li class="muted">没有成功匹配的论文</li>'
        error = ""
        if item.error:
            error = (
                '<div class="error-box"><strong>错误详情</strong><pre>'
                f"{escape(item.error)}</pre></div>"
            )
        details = (
            "<details><summary>查看匹配明细 "
            f'<span>{len(item.matches)}</span></summary><ul class="matches">{matches}</ul>'
            f"{error}</details>"
        )
        return f"""
        <tr data-search="{search_text}" data-status="{status_class}">
          <td>
            <div class="query-id">{escape(item.query_id)}</div>
            <div class="query-text">{escape(query_text) or '<span class="muted">无查询文本</span>'}</div>
            {details}
          </td>
          <td><span class="status {status_class}"><i></i>{status_text}</span></td>
          <td>{self._score_cell(item.precision)}</td>
          <td>{self._score_cell(item.recall)}</td>
          <td>{self._score_cell(item.f1, emphasized=True)}</td>
          <td><div class="counts"><span class="tp">{item.true_positives} TP</span><span class="fp">{item.false_positives} FP</span><span class="fn">{item.false_negatives} FN</span></div></td>
          <td><strong>{item.prediction_count}</strong><span class="subvalue">GT {item.ground_truth_count}</span></td>
          <td><strong>{self._duration(item.usage.latency_ms)}</strong><span class="subvalue">{item.usage.total_tokens:,} tokens</span></td>
        </tr>"""

    def _score_cell(self, value: float, *, emphasized: bool = False) -> str:
        color_class = "high" if value >= 0.7 else "mid" if value >= 0.4 else "low"
        emphasis = " strong" if emphasized else ""
        return (
            f'<div class="table-score {color_class}{emphasis}">'
            f"<span>{self._percent(value)}</span>"
            f'<i><b style="width:{self._safe_width(value)}%"></b></i></div>'
        )

    @staticmethod
    def _safe_width(value: float) -> str:
        return f"{min(1.0, max(0.0, value)) * 100:.1f}"

    @staticmethod
    def _percent(value: float) -> str:
        return f"{value * 100:.2f}%"

    @staticmethod
    def _duration(milliseconds: float) -> str:
        if milliseconds >= 1000:
            return f"{milliseconds / 1000:.2f} s"
        return f"{milliseconds:.2f} ms"

    @staticmethod
    def _cost(value: float | None) -> str:
        return "未提供" if value is None else f"${value:,.4f}"


_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>{{TITLE}}</title>
  <style>
    :root {
      --ink: #172033; --muted: #68758d; --line: #e4e9f1; --paper: #fff;
      --canvas: #f3f6fa; --navy: #10253f; --blue: #2878ff; --cyan: #18b6bd;
      --green: #189a72; --amber: #d98816; --red: #dc5264;
      --shadow: 0 16px 42px rgba(20, 37, 63, .08);
    }
    * { box-sizing: border-box; }
    body { margin: 0; color: var(--ink); background: var(--canvas); font: 14px/1.55 Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    .hero { color: #fff; background: radial-gradient(circle at 85% 0, rgba(24,182,189,.34), transparent 34%), linear-gradient(125deg, #0c1d34 5%, #143b63 65%, #165e76); padding: 48px 0 94px; }
    .wrap { width: min(1200px, calc(100% - 40px)); margin: 0 auto; }
    .brand { display: flex; align-items: center; gap: 10px; color: #b8cee6; font-size: 12px; font-weight: 750; letter-spacing: .13em; text-transform: uppercase; }
    .brand-mark { display: grid; place-items: center; width: 31px; height: 31px; color: #fff; background: linear-gradient(145deg, var(--blue), var(--cyan)); border-radius: 9px; box-shadow: 0 8px 20px rgba(25,160,215,.3); font-size: 15px; }
    h1 { max-width: 800px; margin: 28px 0 12px; font-size: clamp(30px, 5vw, 52px); line-height: 1.08; letter-spacing: -.04em; }
    .subtitle { margin: 0; color: #c7d7e7; font-size: 16px; }
    .meta { display: flex; flex-wrap: wrap; gap: 9px; margin-top: 28px; }
    .meta span { padding: 7px 11px; border: 1px solid rgba(255,255,255,.13); background: rgba(255,255,255,.08); border-radius: 8px; color: #deebf7; font-size: 12px; }
    main { margin-top: -56px; padding-bottom: 56px; }
    .overview { display: grid; grid-template-columns: 1.45fr 1fr 1fr; gap: 18px; }
    .card { background: var(--paper); border: 1px solid rgba(224,230,239,.9); border-radius: 18px; box-shadow: var(--shadow); }
    .score-card { display: flex; align-items: center; gap: 22px; padding: 26px; }
    .donut { --score: {{MACRO_F1_VALUE}}; position: relative; flex: 0 0 122px; width: 122px; height: 122px; display: grid; place-items: center; border-radius: 50%; background: conic-gradient(var(--blue) calc(var(--score) * 1%), #e9eef6 0); }
    .donut:after { content: ""; position: absolute; inset: 10px; background: #fff; border-radius: 50%; }
    .donut div { position: relative; z-index: 1; text-align: center; }
    .donut strong { display: block; font-size: 25px; letter-spacing: -.04em; }
    .donut span { color: var(--muted); font-size: 11px; font-weight: 700; text-transform: uppercase; }
    .score-copy h2 { margin: 0 0 7px; font-size: 19px; }
    .score-copy p { margin: 0; color: var(--muted); }
    .mini-metrics { display: flex; gap: 18px; margin-top: 15px; }
    .mini-metrics strong { display: block; font-size: 17px; }
    .mini-metrics span { color: var(--muted); font-size: 11px; }
    .stat-card { padding: 23px; }
    .eyebrow { color: var(--muted); font-size: 11px; font-weight: 800; letter-spacing: .09em; text-transform: uppercase; }
    .big-stat { margin-top: 8px; font-size: 31px; font-weight: 780; letter-spacing: -.04em; }
    .stat-note { margin-top: 5px; color: var(--muted); font-size: 12px; }
    .status-strip { display: flex; gap: 8px; margin-top: 16px; }
    .status-strip span { height: 6px; border-radius: 20px; }
    .status-strip .ok { flex: {{SUCCESSFUL_QUERIES}}; background: var(--green); }
    .status-strip .bad { flex: {{FAILED_QUERIES}}; background: var(--red); }
    section { margin-top: 24px; }
    .section-head { display: flex; align-items: end; justify-content: space-between; gap: 20px; margin-bottom: 12px; }
    .section-head h2 { margin: 0; font-size: 20px; letter-spacing: -.02em; }
    .section-head p { margin: 2px 0 0; color: var(--muted); font-size: 12px; }
    .metric-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
    .metric-card { padding: 20px; box-shadow: none; }
    .metric-card .value { margin: 7px 0 13px; font-size: 27px; font-weight: 780; }
    .track { height: 7px; overflow: hidden; background: #e9eef5; border-radius: 20px; }
    .track i { display: block; height: 100%; background: linear-gradient(90deg, var(--blue), var(--cyan)); border-radius: inherit; }
    .micro { margin-top: 10px; display: flex; justify-content: space-between; color: var(--muted); font-size: 11px; }
    .micro strong { color: var(--ink); }
    .counts-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-top: 14px; }
    .count-card { display: flex; align-items: center; gap: 14px; padding: 17px 20px; box-shadow: none; }
    .count-card i { width: 10px; height: 42px; border-radius: 10px; }
    .count-card strong { display: block; font-size: 23px; }
    .count-card span { color: var(--muted); font-size: 11px; }
    .efficiency-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
    .eff-card { padding: 20px; box-shadow: none; }
    .eff-card strong { display: block; margin-top: 7px; font-size: 22px; }
    .eff-card small { color: var(--muted); }
    .toolbar { display: flex; gap: 10px; }
    input, select { min-height: 38px; border: 1px solid #dbe2ec; border-radius: 9px; background: #fff; padding: 0 11px; color: var(--ink); font: inherit; outline: none; }
    input { width: min(280px, 42vw); }
    input:focus, select:focus { border-color: var(--blue); box-shadow: 0 0 0 3px rgba(40,120,255,.1); }
    .table-card { overflow: hidden; box-shadow: none; }
    .table-wrap { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; min-width: 980px; }
    th { padding: 12px 14px; color: var(--muted); background: #f8fafc; border-bottom: 1px solid var(--line); font-size: 10px; letter-spacing: .07em; text-align: left; text-transform: uppercase; }
    td { padding: 16px 14px; border-bottom: 1px solid var(--line); vertical-align: top; }
    tbody tr:last-child td { border-bottom: 0; }
    tbody tr:hover { background: #fbfcfe; }
    .query-id { font-weight: 750; }
    .query-text { max-width: 430px; margin-top: 3px; color: var(--muted); font-size: 12px; }
    .status { display: inline-flex; align-items: center; gap: 6px; padding: 4px 8px; border-radius: 20px; font-size: 11px; font-weight: 700; }
    .status i { width: 6px; height: 6px; border-radius: 50%; }
    .status.success { color: #087856; background: #e9f8f2; } .status.success i { background: var(--green); }
    .status.failed { color: #b72d43; background: #fff0f2; } .status.failed i { background: var(--red); }
    .table-score { min-width: 74px; }
    .table-score span { font-size: 12px; font-weight: 650; }
    .table-score.strong span { font-weight: 800; }
    .table-score i { display: block; width: 62px; height: 4px; margin-top: 6px; background: #ebeff5; border-radius: 5px; overflow: hidden; }
    .table-score b { display: block; height: 100%; border-radius: 5px; }
    .table-score.high b { background: var(--green); } .table-score.mid b { background: var(--amber); } .table-score.low b { background: var(--red); }
    .counts { display: flex; flex-wrap: wrap; gap: 4px; width: 100px; }
    .counts span { padding: 2px 5px; border-radius: 5px; font-size: 10px; font-weight: 750; }
    .tp { color: #087856; background: #e9f8f2; } .fp { color: #aa6410; background: #fff5e6; } .fn { color: #b72d43; background: #fff0f2; }
    .subvalue { display: block; margin-top: 3px; color: var(--muted); font-size: 10px; white-space: nowrap; }
    details { margin-top: 7px; }
    summary { width: max-content; color: var(--blue); cursor: pointer; font-size: 11px; }
    summary span { display: inline-grid; place-items: center; min-width: 17px; height: 17px; margin-left: 3px; color: #fff; background: var(--blue); border-radius: 9px; font-size: 9px; }
    .matches { max-width: 570px; margin: 9px 0 0; padding: 10px 10px 10px 27px; background: #f7f9fc; border-radius: 8px; font-size: 11px; }
    .matches li + li { margin-top: 6px; }
    .matches .arrow { margin: 0 7px; color: #96a1b2; }
    .matches code { margin-left: 7px; padding: 2px 4px; color: #345; background: #e7ecf3; border-radius: 4px; font-size: 9px; }
    .error-box { max-width: 570px; margin-top: 8px; padding: 10px; color: #9e2638; background: #fff3f4; border: 1px solid #ffdce1; border-radius: 8px; font-size: 11px; }
    pre { max-height: 180px; overflow: auto; white-space: pre-wrap; word-break: break-word; font-size: 10px; }
    .muted { color: var(--muted); }
    .empty { padding: 35px; text-align: center; color: var(--muted); }
    footer { padding: 10px 0 38px; color: #8792a3; text-align: center; font-size: 11px; }
    @media (max-width: 850px) { .overview { grid-template-columns: 1fr 1fr; } .score-card { grid-column: 1 / -1; } .metric-grid, .counts-grid { grid-template-columns: 1fr; } .efficiency-grid { grid-template-columns: 1fr 1fr; } .section-head { align-items: start; flex-direction: column; } }
    @media (max-width: 520px) { .wrap { width: min(100% - 24px, 1200px); } .hero { padding-top: 30px; } .overview { grid-template-columns: 1fr; } .score-card { align-items: flex-start; flex-direction: column; } .efficiency-grid { grid-template-columns: 1fr; } .toolbar { width: 100%; } input { flex: 1; width: 100%; } }
    @media print { body { background: #fff; } .hero { padding: 25px 0 70px; print-color-adjust: exact; -webkit-print-color-adjust: exact; } .card { box-shadow: none; } .toolbar, details { display: none; } main { margin-top: -45px; } }
  </style>
</head>
<body>
  <header class="hero">
    <div class="wrap">
      <div class="brand"><span class="brand-mark">A</span> AcademicAgentEval</div>
      <h1>{{EXPERIMENT}}</h1>
      <p class="subtitle">学术论文搜索 Agent · 实验评测报告</p>
      <div class="meta">
        <span>Run · {{RUN_ID}}</span><span>Agent · {{AGENT}} {{AGENT_VERSION}}</span>
        <span>Dataset · {{DATASET}}</span><span>Protocol · {{PROTOCOL}}</span>
      </div>
    </div>
  </header>
  <main class="wrap">
    <div class="overview">
      <article class="card score-card">
        <div class="donut"><div><strong>{{MACRO_F1}}</strong><span>Macro F1</span></div></div>
        <div class="score-copy"><h2>总体检索质量</h2><p>以每个查询等权聚合的论文集合匹配表现。</p>
          <div class="mini-metrics"><div><strong>{{MACRO_PRECISION}}</strong><span>Precision</span></div><div><strong>{{MACRO_RECALL}}</strong><span>Recall</span></div></div>
        </div>
      </article>
      <article class="card stat-card"><div class="eyebrow">实验可靠性</div><div class="big-stat">{{SUCCESS_RATE}}</div><div class="stat-note">{{SUCCESSFUL_QUERIES}} / {{QUERY_COUNT}} 查询成功 · {{FAILED_QUERIES}} 失败</div><div class="status-strip"><span class="ok"></span><span class="bad"></span></div></article>
      <article class="card stat-card"><div class="eyebrow">平均端到端延迟</div><div class="big-stat">{{MEAN_LATENCY}}</div><div class="stat-note">P50 {{P50_LATENCY}} · P95 {{P95_LATENCY}}</div></article>
    </div>

    <section>
      <div class="section-head"><div><h2>检索质量</h2><p>Macro 对查询等权，Micro 对全部论文判断等权。</p></div></div>
      <div class="metric-grid">
        <article class="card metric-card"><div class="eyebrow">Precision</div><div class="value">{{MACRO_PRECISION}}</div><div class="track"><i style="width:{{MACRO_PRECISION}}"></i></div><div class="micro"><span>Micro</span><strong>{{MICRO_PRECISION}}</strong></div></article>
        <article class="card metric-card"><div class="eyebrow">Recall</div><div class="value">{{MACRO_RECALL}}</div><div class="track"><i style="width:{{MACRO_RECALL}}"></i></div><div class="micro"><span>Micro</span><strong>{{MICRO_RECALL}}</strong></div></article>
        <article class="card metric-card"><div class="eyebrow">F1 Score</div><div class="value">{{MACRO_F1}}</div><div class="track"><i style="width:{{MACRO_F1}}"></i></div><div class="micro"><span>Micro</span><strong>{{MICRO_F1}}</strong></div></article>
      </div>
      <div class="counts-grid">
        <article class="card count-card"><i style="background:var(--green)"></i><div><strong>{{TRUE_POSITIVES}}</strong><span>True Positives · 正确检索</span></div></article>
        <article class="card count-card"><i style="background:var(--amber)"></i><div><strong>{{FALSE_POSITIVES}}</strong><span>False Positives · 错误检索</span></div></article>
        <article class="card count-card"><i style="background:var(--red)"></i><div><strong>{{FALSE_NEGATIVES}}</strong><span>False Negatives · 遗漏论文</span></div></article>
      </div>
    </section>

    <section>
      <div class="section-head"><div><h2>运行效率</h2><p>由 Experiment Runner 和 Agent Tracker 共同采集。</p></div></div>
      <div class="efficiency-grid">
        <article class="card eff-card"><div class="eyebrow">LLM Calls</div><strong>{{LLM_CALLS}}</strong><small>模型调用总数</small></article>
        <article class="card eff-card"><div class="eyebrow">Retrieval API</div><strong>{{API_CALLS}}</strong><small>检索服务调用总数</small></article>
        <article class="card eff-card"><div class="eyebrow">Tokens</div><strong>{{TOKENS}}</strong><small>Prompt + Completion</small></article>
        <article class="card eff-card"><div class="eyebrow">Estimated Cost</div><strong>{{COST}}</strong><small>Agent 上报的估算成本</small></article>
      </div>
    </section>

    <section>
      <div class="section-head">
        <div><h2>逐查询结果</h2><p>展开每行可检查匹配论文、匹配方法和错误信息。</p></div>
        <div class="toolbar"><input id="search" type="search" placeholder="搜索 Query ID 或查询文本"><select id="status"><option value="all">全部状态</option><option value="success">仅成功</option><option value="failed">仅失败</option></select></div>
      </div>
      <div class="card table-card"><div class="table-wrap"><table>
        <thead><tr><th>查询</th><th>状态</th><th>Precision</th><th>Recall</th><th>F1</th><th>判断</th><th>论文数</th><th>效率</th></tr></thead>
        <tbody id="queryRows">{{QUERY_ROWS}}</tbody>
      </table></div><div class="empty" id="empty" hidden>没有符合筛选条件的查询</div></div>
    </section>
  </main>
  <footer class="wrap">AcademicAgentEval · Generated {{GENERATED_AT}} · Self-contained report</footer>
  <script>
    const search = document.getElementById('search');
    const status = document.getElementById('status');
    const rows = [...document.querySelectorAll('#queryRows tr')];
    const empty = document.getElementById('empty');
    function filterRows() {
      const term = search.value.trim().toLocaleLowerCase();
      let visible = 0;
      rows.forEach(row => {
        const matchText = !term || row.dataset.search.includes(term);
        const matchStatus = status.value === 'all' || row.dataset.status === status.value;
        row.hidden = !(matchText && matchStatus);
        if (!row.hidden) visible += 1;
      });
      empty.hidden = visible !== 0;
    }
    search.addEventListener('input', filterRows);
    status.addEventListener('change', filterRows);
  </script>
</body>
</html>
"""
