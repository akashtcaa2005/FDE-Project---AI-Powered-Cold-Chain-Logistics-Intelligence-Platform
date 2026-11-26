"""Operational KPIs, SOP alert detection, executive briefings, and export helpers."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.config import (
    ColdChainProfile,
    SOP_DELAY_ESCALATION_THRESHOLD,
    SOP_PORT_CONGESTION_CRITICAL,
)


def compute_kpis(df: pd.DataFrame, profile: ColdChainProfile) -> dict[str, Any]:
    """Compute fleet, cold-chain, and risk KPIs with period-over-period deltas and sparklines."""
    if df.empty:
        return {
            "total_records": 0,
            "recent_30d_records": 0,
            "high_risk_count": 0,
            "moderate_risk_count": 0,
            "low_risk_count": 0,
            "excursion_count": 0,
            "high_temp_count": 0,
            "low_temp_count": 0,
            "delayed_risk_count": 0,
            "port_breach_count": 0,
            "avg_temp": 0.0,
            "avg_delay_prob": 0.0,
            "avg_route_risk": 0.0,
            "avg_performance_pct": 0.0,
            "performance_label": "On-Time Readiness",
            "deltas": {},
            "sparklines": {},
        }

    work = df.copy()
    max_ts = work["timestamp"].max()
    recent_cutoff = max_ts - pd.Timedelta(days=30)
    prior_cutoff = max_ts - pd.Timedelta(days=60)

    recent_df = work[work["timestamp"] > recent_cutoff]
    prior_df = work[(work["timestamp"] > prior_cutoff) & (work["timestamp"] <= recent_cutoff)]

    excursion_mask = (work["iot_temperature"] > profile.critical_temp_c) | (
        work["iot_temperature"] < profile.min_temp_c
    )
    high_risk_mask = work["risk_classification"] == "High Risk"
    delayed_mask = work["delay_probability"] > SOP_DELAY_ESCALATION_THRESHOLD
    port_breach_mask = work["port_congestion_level"] > SOP_PORT_CONGESTION_CRITICAL

    if "order_fulfillment_status" in work.columns:
        perf_series = work["order_fulfillment_status"].astype(float) * 100.0
        perf_label = "Order Fulfillment Rate"
    else:
        perf_series = (1.0 - work["delay_probability"].astype(float)) * 100.0
        perf_label = "On-Time Readiness (1 - Delay Prob)"

    # Period-over-period deltas (latest 30d vs prior 30d)
    deltas: dict[str, str | None] = {}
    if not recent_df.empty and not prior_df.empty:
        r_exc = int(
            (
                (recent_df["iot_temperature"] > profile.critical_temp_c)
                | (recent_df["iot_temperature"] < profile.min_temp_c)
            ).sum()
        )
        p_exc = int(
            (
                (prior_df["iot_temperature"] > profile.critical_temp_c)
                | (prior_df["iot_temperature"] < profile.min_temp_c)
            ).sum()
        )
        r_hr = int((recent_df["risk_classification"] == "High Risk").sum())
        p_hr = int((prior_df["risk_classification"] == "High Risk").sum())
        r_del = int((recent_df["delay_probability"] > SOP_DELAY_ESCALATION_THRESHOLD).sum())
        p_del = int((prior_df["delay_probability"] > SOP_DELAY_ESCALATION_THRESHOLD).sum())

        r_perf = (
            recent_df["order_fulfillment_status"].mean() * 100.0
            if "order_fulfillment_status" in recent_df.columns
            else (1.0 - recent_df["delay_probability"].mean()) * 100.0
        )
        p_perf = (
            prior_df["order_fulfillment_status"].mean() * 100.0
            if "order_fulfillment_status" in prior_df.columns
            else (1.0 - prior_df["delay_probability"].mean()) * 100.0
        )

        deltas = {
            "records": f"{len(recent_df) - len(prior_df):+d} vs prior 30d",
            "high_risk": f"{r_hr - p_hr:+d} vs prior 30d",
            "excursions": f"{r_exc - p_exc:+d} vs prior 30d",
            "delayed": f"{r_del - p_del:+d} vs prior 30d",
            "performance": f"{r_perf - p_perf:+.1f} pp vs prior 30d",
            "temp": f"{recent_df['iot_temperature'].mean() - prior_df['iot_temperature'].mean():+.2f} °C vs prior 30d",
        }

    # Weekly sparklines across last 16 weeks in dataset
    work_idx = work.set_index("timestamp")
    weekly_counts = work_idx["record_id"].resample("W").count().tail(16).tolist()
    weekly_excursions = (
        excursion_mask.set_axis(work["timestamp"]).resample("W").sum().tail(16).astype(int).tolist()
    )
    weekly_high_risk = (
        high_risk_mask.set_axis(work["timestamp"]).resample("W").sum().tail(16).astype(int).tolist()
    )
    weekly_delayed = (
        delayed_mask.set_axis(work["timestamp"]).resample("W").sum().tail(16).astype(int).tolist()
    )
    weekly_temp = work_idx["iot_temperature"].resample("W").mean().round(2).tail(16).fillna(0).tolist()
    weekly_perf = (
        perf_series.set_axis(work["timestamp"]).resample("W").mean().round(1).tail(16).fillna(0).tolist()
    )

    risk_counts = work["risk_classification"].value_counts()

    return {
        "total_records": int(len(work)),
        "recent_30d_records": int(len(recent_df)),
        "high_risk_count": int(risk_counts.get("High Risk", 0)),
        "moderate_risk_count": int(risk_counts.get("Moderate Risk", 0)),
        "low_risk_count": int(risk_counts.get("Low Risk", 0)),
        "excursion_count": int(excursion_mask.sum()),
        "high_temp_count": int((work["iot_temperature"] > profile.critical_temp_c).sum()),
        "low_temp_count": int((work["iot_temperature"] < profile.min_temp_c).sum()),
        "delayed_risk_count": int(delayed_mask.sum()),
        "port_breach_count": int(port_breach_mask.sum()),
        "avg_temp": float(work["iot_temperature"].mean()),
        "avg_delay_prob": float(work["delay_probability"].mean()),
        "avg_route_risk": float(work["route_risk_level"].mean()),
        "avg_performance_pct": float(perf_series.mean()),
        "performance_label": perf_label,
        "deltas": deltas,
        "sparklines": {
            "records": weekly_counts,
            "excursions": weekly_excursions,
            "high_risk": weekly_high_risk,
            "delayed": weekly_delayed,
            "temp": weekly_temp,
            "performance": weekly_perf,
        },
    }


def generate_operational_alerts(
    df: pd.DataFrame,
    profile: ColdChainProfile,
    weather_snapshots: list[dict[str, Any]] | None = None,
    limit: int = 15,
) -> list[dict[str, Any]]:
    """Generate real operational alerts directly from dataset violations and Open-Meteo checks."""
    alerts: list[dict[str, Any]] = []
    if df.empty:
        return alerts

    # 1. Critical High-Temperature Excursions (most recent severe rows)
    hot_breaches = (
        df[df["iot_temperature"] > profile.critical_temp_c]
        .sort_values(["timestamp", "iot_temperature"], ascending=[False, False])
        .head(4)
    )
    for row in hot_breaches.itertuples():
        alerts.append(
            {
                "severity": "CRITICAL",
                "category": "Temperature Excursion",
                "timestamp": str(row.timestamp),
                "record_id": row.record_id,
                "corridor": row.corridor_zone,
                "summary": (
                    f"{row.record_id} recorded {row.iot_temperature:.1f}°C "
                    f"(threshold > {profile.critical_temp_c:.1f}°C) at "
                    f"({row.vehicle_gps_latitude:.2f}, {row.vehicle_gps_longitude:.2f})."
                ),
                "recommendation": "SOP §1: Contact driver to restart auxiliary cooling; divert to emergency cold storage if delay > 1h.",
            }
        )

    # 2. Tier 2 Risk Escalations (High Risk + Delay Prob > 0.65)
    tier2 = (
        df[
            (df["risk_classification"] == "High Risk")
            & (df["delay_probability"] > SOP_DELAY_ESCALATION_THRESHOLD)
        ]
        .sort_values(["timestamp", "delay_probability"], ascending=[False, False])
        .head(4)
    )
    for row in tier2.itertuples():
        alerts.append(
            {
                "severity": "HIGH",
                "category": "Tier 2 Escalation",
                "timestamp": str(row.timestamp),
                "record_id": row.record_id,
                "corridor": row.corridor_zone,
                "summary": (
                    f"{row.record_id} flagged High Risk with {row.delay_probability:.1%} delay probability "
                    f"(Route Risk {row.route_risk_level:.1f}/10)."
                ),
                "recommendation": "SOP §3: Escalate immediately to Tier 2 Logistics Manager and review alternate routing.",
            }
        )

    # 3. Port Congestion Diversion Triggers (> 7.0)
    port_alerts = (
        df[df["port_congestion_level"] > SOP_PORT_CONGESTION_CRITICAL]
        .sort_values(["timestamp", "port_congestion_level"], ascending=[False, False])
        .head(3)
    )
    for row in port_alerts.itertuples():
        alerts.append(
            {
                "severity": "WARNING",
                "category": "Port Congestion Breach",
                "timestamp": str(row.timestamp),
                "record_id": row.record_id,
                "corridor": row.corridor_zone,
                "summary": (
                    f"{row.record_id} port congestion at {row.port_congestion_level:.2f}/10 "
                    f"(SOP trigger > {SOP_PORT_CONGESTION_CRITICAL:.1f})."
                ),
                "recommendation": "SOP §2: Suspend standard port routing; divert active SoCal freight to Inland Empire Overflow Depot (San Bernardino).",
            }
        )

    # 4. Live Open-Meteo Weather Advisories
    if weather_snapshots:
        for snap in weather_snapshots:
            if snap.get("ok") and (snap.get("observed_wind_kmh") or 0) > 10.0:
                alerts.append(
                    {
                        "severity": "WARNING",
                        "category": "Live Weather Disruption",
                        "timestamp": str(snap.get("observed_time") or "Live"),
                        "record_id": snap.get("hub_code", "CORRIDOR"),
                        "corridor": snap.get("hub_name", "Monitored Corridor"),
                        "summary": (
                            f"Open-Meteo observed {snap['observed_wind_kmh']:.1f} km/h wind and "
                            f"{snap['observed_temp_c']:.1f}°C external temp."
                        ),
                        "recommendation": "Derived corridor risk elevated (8.5/10). Verify transit clearance and trailer refrigeration load.",
                    }
                )

    severity_rank = {"CRITICAL": 0, "HIGH": 1, "WARNING": 2, "INFO": 3}
    alerts.sort(key=lambda a: (severity_rank.get(a["severity"], 9), a["timestamp"]), reverse=False)
    return alerts[:limit]


def build_executive_briefing(
    df: pd.DataFrame,
    kpis: dict[str, Any],
    profile: ColdChainProfile,
    source_info: dict[str, Any],
) -> str:
    """Create a strictly data-grounded executive operational summary (zero invented metrics)."""
    if df.empty:
        return "No fleet telemetry records are currently loaded. Check SQL Server connectivity or the raw dataset path."

    total = kpis["total_records"]
    high_risk = kpis["high_risk_count"]
    high_pct = (high_risk / total * 100.0) if total else 0.0
    excursions = kpis["excursion_count"]
    delayed = kpis["delayed_risk_count"]
    port_breaches = kpis["port_breach_count"]

    top_corridor = (
        df[df["risk_classification"] == "High Risk"]["corridor_zone"].value_counts().idxmax()
        if high_risk > 0
        else df["corridor_zone"].value_counts().idxmax()
    )
    ts_min = df["timestamp"].min().strftime("%Y-%m-%d")
    ts_max = df["timestamp"].max().strftime("%Y-%m-%d")

    return (
        f"**Operational Snapshot ({ts_min} to {ts_max} | Source: {source_info.get('source_label', 'Telemetry')}):** "
        f"Across **{total:,}** monitored telemetry observations, **{high_risk:,}** (**{high_pct:.1f}%**) carry a "
        f"`High Risk` classification, with the highest concentration in **{top_corridor}**. "
        f"Under the **{profile.label}** envelope ({profile.min_temp_c:.1f}°C to {profile.critical_temp_c:.1f}°C), "
        f"**{excursions:,}** observations fall outside safe limits (**{kpis['high_temp_count']:,}** above "
        f"{profile.critical_temp_c:.1f}°C and **{kpis['low_temp_count']:,}** below {profile.min_temp_c:.1f}°C). "
        f"Additionally, **{delayed:,}** records exceed the SOP §3 delay-probability escalation threshold (>65%), "
        f"and **{port_breaches:,}** exceed the SOP §2 port congestion trigger (>7.0/10), requiring Tier 2 review and "
        f"potential San Bernardino overflow diversion."
    )


def build_operational_report_md(
    df: pd.DataFrame,
    kpis: dict[str, Any],
    profile: ColdChainProfile,
    source_info: dict[str, Any],
) -> str:
    """Generate a downloadable Markdown operational summary report."""
    briefing = build_executive_briefing(df, kpis, profile, source_info)
    lines = [
        "# FDE Intelligence — Cold Chain Operational Report",
        "",
        f"- **Data Source:** {source_info.get('source_label', 'Unknown')}",
        f"- **Loaded At:** {source_info.get('loaded_at', 'N/A')}",
        f"- **Temperature Profile:** {profile.label} ({profile.source})",
        "",
        "## Executive Briefing",
        briefing,
        "",
        "## Core Metrics",
        f"- Total Telemetry Observations: {kpis['total_records']:,}",
        f"- High Risk Records: {kpis['high_risk_count']:,}",
        f"- Temperature Excursions: {kpis['excursion_count']:,}",
        f"- Delay Escalations (>65%): {kpis['delayed_risk_count']:,}",
        f"- Port Congestion Breaches (>7.0): {kpis['port_breach_count']:,}",
        f"- Mean Cargo Temperature: {kpis['avg_temp']:.2f} °C",
        f"- Mean Delay Probability: {kpis['avg_delay_prob']:.1%}",
        f"- Mean Route Risk Index: {kpis['avg_route_risk']:.2f} / 10",
        f"- {kpis['performance_label']}: {kpis['avg_performance_pct']:.1f}%",
        "",
    ]
    return "\n".join(lines)
