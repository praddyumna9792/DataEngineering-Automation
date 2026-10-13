"""
Modern, polished UI styling and CSS helpers for LegacyLift.
Clean enterprise aesthetic with restrained palette and accessible contrast.
"""

CUSTOM_CSS = """
<style>
    /* Main container and font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    code, pre, .stCode {
        font-family: 'JetBrains Mono', monospace !important;
    }

    /* Metric Cards */
    .metric-card {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 18px 22px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        margin-bottom: 12px;
    }
    .metric-title {
        font-size: 0.82rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #64748b;
        margin-bottom: 6px;
    }
    .metric-value {
        font-size: 1.85rem;
        font-weight: 700;
        color: #0f172a;
    }
    .metric-subtitle {
        font-size: 0.8rem;
        color: #94a3b8;
        margin-top: 4px;
    }

    /* Badges & Status Pills */
    .status-pill {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.02em;
    }
    .status-completed, .status-pass, .status-exact-match {
        background-color: #dcfce7;
        color: #15803d;
    }
    .status-running, .status-in-progress {
        background-color: #e0f2fe;
        color: #0369a1;
    }
    .status-pending, .status-draft {
        background-color: #f1f5f9;
        color: #475569;
    }
    .status-warn, .status-partial {
        background-color: #fef9c3;
        color: #a16207;
    }
    .status-failed, .status-incompatible, .status-error {
        background-color: #fee2e2;
        color: #b91c1c;
    }

    /* Info Callouts */
    .callout-box {
        border-left: 4px solid #3b82f6;
        background-color: #f0f7ff;
        padding: 14px 18px;
        border-radius: 0 8px 8px 0;
        margin-bottom: 16px;
    }
    .callout-title {
        font-weight: 600;
        color: #1e3a8a;
        margin-bottom: 4px;
    }
    .callout-body {
        font-size: 0.9rem;
        color: #1e40af;
    }

    /* Brand Header */
    .brand-container {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 20px;
    }
    .brand-title {
        font-size: 1.6rem;
        font-weight: 800;
        color: #0f172a;
        letter-spacing: -0.02em;
        margin: 0;
    }
    .brand-tagline {
        font-size: 0.85rem;
        color: #64748b;
        margin: 0;
    }
</style>
"""


def render_metric_card(title: str, value: str, subtitle: str = "") -> str:
    sub_html = f'<div class="metric-subtitle">{subtitle}</div>' if subtitle else ""
    return f"""
    <div class="metric-card">
        <div class="metric-title">{title}</div>
        <div class="metric-value">{value}</div>
        {sub_html}
    </div>
    """


def render_status_pill(status: str) -> str:
    clean = status.lower().replace("_", "-")
    cls_map = {
        "completed": "status-completed",
        "running": "status-running",
        "in-progress": "status-in-progress",
        "pending": "status-pending",
        "failed": "status-failed",
        "exact-match": "status-exact-match",
        "compatible": "status-completed",
        "incompatible": "status-incompatible",
        "partially-completed": "status-partial",
        "pass": "status-pass",
        "warn": "status-warn",
    }
    css_class = cls_map.get(clean, "status-pending")
    return f'<span class="status-pill {css_class}">{status.upper()}</span>'
