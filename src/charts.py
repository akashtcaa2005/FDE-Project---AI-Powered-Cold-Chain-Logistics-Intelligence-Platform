"""Altair and PyDeck visualizations styled for the FDE dark enterprise theme."""

from __future__ import annotations

import altair as alt
import pandas as pd
import pydeck as pdk

from src.config import ColdChainProfile

RISK_COLORS = {
    "High Risk": "#FB7185",
    "Moderate Risk": "#FBBF24",
    "Low Risk": "#34D399",
}


def _configure_chart(chart: alt.Chart, height: int = 280) -> alt.Chart:
    return (
        chart.properties(height=height)
        .configure_view(strokeWidth=0, fill="transparent")
        .configure(background="transparent")
        .configure_axis(
            gridColor="#1A2942",
            domainColor="#243552",
            tickColor="#243552",
            labelColor="#94A3B8",
            titleColor="#CBD5E1",
            labelFontSize=11,
            titleFontSize=12,
        )
        .configure_legend(
            labelColor="#CBD5E1",
            titleColor="#94A3B8",
            orient="top",
        )
        .configure_title(color="#F1F5F9", fontSize=14, anchor="start")
    )


def chart_risk_distribution(df: pd.DataFrame) -> alt.Chart:
    counts = (
        df["risk_classification"]
        .value_counts()
        .rename_axis("Risk")
        .reset_index(name="Records")
    )
    order = ["High Risk", "Moderate Risk", "Low Risk"]
    chart = (
        alt.Chart(counts)
        .mark_bar(cornerRadiusTopRight=6, cornerRadiusBottomRight=6)
        .encode(
            y=alt.Y("Risk:N", sort=order, title=None),
            x=alt.X("Records:Q", title="Telemetry Observations"),
            color=alt.Color(
                "Risk:N",
                scale=alt.Scale(domain=order, range=[RISK_COLORS[k] for k in order]),
                legend=None,
            ),
            tooltip=["Risk:N", alt.Tooltip("Records:Q", format=",")],
        )
    )
    return _configure_chart(chart, height=240)


def chart_temperature_trend_with_thresholds(
    df: pd.DataFrame, profile: ColdChainProfile, freq: str = "W"
) -> alt.Chart:
    ts_df = (
        df.set_index("timestamp")["iot_temperature"]
        .resample(freq)
        .agg(["mean", "min", "max"])
        .reset_index()
        .dropna()
    )
    base = alt.Chart(ts_df).encode(x=alt.X("timestamp:T", title="Timeline"))

    band = base.mark_area(opacity=0.18, color="#38BDF8").encode(
        y=alt.Y("min:Q", title="Temperature (°C)"),
        y2="max:Q",
    )
    mean_line = base.mark_line(color="#38BDF8", strokeWidth=2.2).encode(
        y="mean:Q",
        tooltip=[
            alt.Tooltip("timestamp:T", title="Period"),
            alt.Tooltip("mean:Q", title="Mean °C", format=".2f"),
            alt.Tooltip("min:Q", title="Min °C", format=".2f"),
            alt.Tooltip("max:Q", title="Max °C", format=".2f"),
        ],
    )

    rules_df = pd.DataFrame(
        [
            {"y": profile.critical_temp_c, "label": f"Critical ({profile.critical_temp_c:.1f}°C)"},
            {"y": profile.min_temp_c, "label": f"Min Safe ({profile.min_temp_c:.1f}°C)"},
        ]
    )
    crit_rule = (
        alt.Chart(rules_df.iloc[[0]])
        .mark_rule(color="#FB7185", strokeDash=[5, 4], strokeWidth=1.5)
        .encode(y="y:Q", tooltip=["label:N"])
    )
    min_rule = (
        alt.Chart(rules_df.iloc[[1]])
        .mark_rule(color="#34D399", strokeDash=[5, 4], strokeWidth=1.5)
        .encode(y="y:Q", tooltip=["label:N"])
    )

    return _configure_chart(band + mean_line + crit_rule + min_rule, height=290)


def chart_delay_probability_hist(df: pd.DataFrame) -> alt.Chart:
    bins = [i / 20.0 for i in range(21)]
    cut = pd.cut(df["delay_probability"].clip(0.0, 1.0), bins=bins, include_lowest=True)
    counts = cut.value_counts().sort_index()
    hist_df = pd.DataFrame(
        {
            "bin_start": [iv.left for iv in counts.index],
            "bin_end": [iv.right for iv in counts.index],
            "range_label": [f"{iv.left:.0%}–{iv.right:.0%}" for iv in counts.index],
            "records": counts.values.astype(int),
        }
    )
    chart = (
        alt.Chart(hist_df)
        .mark_bar(color="#38BDF8", cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
        .encode(
            x=alt.X("bin_start:Q", bin="binned", title="Delay Probability"),
            x2="bin_end:Q",
            y=alt.Y("records:Q", title="Records"),
            tooltip=[
                alt.Tooltip("range_label:N", title="Probability Band"),
                alt.Tooltip("records:Q", title="Count", format=","),
            ],
        )
    )
    return _configure_chart(chart, height=250)


def chart_corridor_risk_comparison(df: pd.DataFrame) -> alt.Chart:
    agg = (
        df.groupby("corridor_zone", as_index=False)
        .agg(
            avg_route_risk=("route_risk_level", "mean"),
            avg_port_congestion=("port_congestion_level", "mean"),
            avg_delay_prob=("delay_probability", "mean"),
            records=("record_id", "count"),
        )
        .sort_values("avg_route_risk", ascending=False)
    )
    chart = (
        alt.Chart(agg)
        .mark_bar(cornerRadiusTopRight=5, cornerRadiusBottomRight=5)
        .encode(
            y=alt.Y("corridor_zone:N", sort="-x", title=None),
            x=alt.X("avg_route_risk:Q", title="Mean Route Risk Index (0–10)"),
            color=alt.Color(
                "avg_port_congestion:Q",
                scale=alt.Scale(scheme="tealblues"),
                title="Port Congestion",
            ),
            tooltip=[
                alt.Tooltip("corridor_zone:N", title="Corridor"),
                alt.Tooltip("records:Q", title="Records", format=","),
                alt.Tooltip("avg_route_risk:Q", title="Route Risk", format=".2f"),
                alt.Tooltip("avg_port_congestion:Q", title="Port Congestion", format=".2f"),
                alt.Tooltip("avg_delay_prob:Q", title="Delay Prob", format=".1%"),
            ],
        )
    )
    return _configure_chart(chart, height=270)


def chart_fleet_activity_timeline(df: pd.DataFrame) -> alt.Chart:
    daily = (
        df.set_index("timestamp")
        .groupby([pd.Grouper(freq="W"), "risk_classification"])["record_id"]
        .count()
        .reset_index(name="records")
    )
    order = ["High Risk", "Moderate Risk", "Low Risk"]
    chart = (
        alt.Chart(daily)
        .mark_area(opacity=0.75)
        .encode(
            x=alt.X("timestamp:T", title="Timeline"),
            y=alt.Y("records:Q", title="Weekly Observations"),
            color=alt.Color(
                "risk_classification:N",
                scale=alt.Scale(domain=order, range=[RISK_COLORS[k] for k in order]),
                title="Risk Class",
            ),
            tooltip=[
                alt.Tooltip("timestamp:T", title="Week"),
                alt.Tooltip("risk_classification:N", title="Risk"),
                alt.Tooltip("records:Q", title="Observations", format=","),
            ],
        )
    )
    return _configure_chart(chart, height=260)


def chart_delivery_performance_trend(df: pd.DataFrame) -> alt.Chart:
    work = df.set_index("timestamp")
    if "order_fulfillment_status" in work.columns:
        agg = work.resample("W").agg(
            fulfillment=("order_fulfillment_status", lambda s: s.mean() * 100.0),
            on_time_proxy=("delay_probability", lambda s: (1.0 - s.mean()) * 100.0),
        ).reset_index()
        melted = agg.melt("timestamp", var_name="Metric", value_name="Percentage")
        melted["Metric"] = melted["Metric"].map(
            {"fulfillment": "Order Fulfillment %", "on_time_proxy": "On-Time Readiness %"}
        )
    else:
        agg = work.resample("W").agg(
            on_time_proxy=("delay_probability", lambda s: (1.0 - s.mean()) * 100.0)
        ).reset_index()
        melted = agg.melt("timestamp", var_name="Metric", value_name="Percentage")
        melted["Metric"] = "On-Time Readiness %"

    chart = (
        alt.Chart(melted)
        .mark_line(strokeWidth=2.2)
        .encode(
            x=alt.X("timestamp:T", title="Timeline"),
            y=alt.Y("Percentage:Q", title="Performance (%)", scale=alt.Scale(domain=[0, 100])),
            color=alt.Color("Metric:N", scale=alt.Scale(range=["#34D399", "#38BDF8"])),
            tooltip=[
                alt.Tooltip("timestamp:T", title="Week"),
                alt.Tooltip("Metric:N"),
                alt.Tooltip("Percentage:Q", format=".1f"),
            ],
        )
    )
    return _configure_chart(chart, height=260)


def chart_excursion_frequency(df: pd.DataFrame, profile: ColdChainProfile) -> alt.Chart:
    work = df.copy()
    work["excursion"] = (
        (work["iot_temperature"] > profile.critical_temp_c)
        | (work["iot_temperature"] < profile.min_temp_c)
    ).astype(int)
    monthly = work.set_index("timestamp")["excursion"].resample("ME").sum().reset_index()
    chart = (
        alt.Chart(monthly)
        .mark_bar(color="#FB7185", cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X("timestamp:T", title="Month"),
            y=alt.Y("excursion:Q", title="Excursion Count"),
            tooltip=[
                alt.Tooltip("timestamp:T", title="Month", format="%b %Y"),
                alt.Tooltip("excursion:Q", title="Excursions", format=","),
            ],
        )
    )
    return _configure_chart(chart, height=260)


def chart_weather_forecast(hourly_df: pd.DataFrame) -> alt.Chart:
    base = alt.Chart(hourly_df).encode(x=alt.X("time:T", title="Forecast Hour (UTC)"))
    temp_line = base.mark_line(color="#38BDF8", strokeWidth=2.2).encode(
        y=alt.Y("temperature_c:Q", title="Temperature (°C)"),
        tooltip=[
            alt.Tooltip("time:T", title="Hour"),
            alt.Tooltip("temperature_c:Q", title="Temp °C", format=".1f"),
            alt.Tooltip("wind_kmh:Q", title="Wind km/h", format=".1f"),
        ],
    )
    wind_bar = base.mark_bar(opacity=0.25, color="#FBBF24").encode(
        y=alt.Y("wind_kmh:Q", title="Wind (km/h)"),
    )
    return _configure_chart(alt.layer(wind_bar, temp_line).resolve_scale(y="independent"), height=250)


def build_fleet_pydeck(df: pd.DataFrame, max_points: int = 1200) -> pdk.Deck:
    """Create a dark PyDeck geospatial visualization for telemetry points."""
    sample = df.tail(max_points).copy() if len(df) > max_points else df.copy()
    color_map = {
        "High Risk": [251, 113, 133, 195],
        "Moderate Risk": [251, 191, 36, 185],
        "Low Risk": [52, 211, 153, 175],
    }
    sample["fill_color"] = sample["risk_classification"].map(
        lambda r: color_map.get(r, [56, 189, 248, 170])
    )
    sample["temp_str"] = sample["iot_temperature"].map(lambda t: f"{t:.2f} °C")
    sample["delay_str"] = sample["delay_probability"].map(lambda d: f"{d:.1%}")
    sample["ts_str"] = sample["timestamp"].astype(str)

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=sample[
            [
                "record_id",
                "vehicle_gps_latitude",
                "vehicle_gps_longitude",
                "risk_classification",
                "temp_str",
                "delay_str",
                "route_risk_level",
                "corridor_zone",
                "ts_str",
                "fill_color",
            ]
        ],
        get_position="[vehicle_gps_longitude, vehicle_gps_latitude]",
        get_fill_color="fill_color",
        get_radius=18000,
        radius_min_pixels=4,
        radius_max_pixels=12,
        pickable=True,
    )

    center_lat = float(sample["vehicle_gps_latitude"].mean()) if not sample.empty else 38.5
    center_lon = float(sample["vehicle_gps_longitude"].mean()) if not sample.empty else -96.0

    view_state = pdk.ViewState(latitude=center_lat, longitude=center_lon, zoom=3.3, pitch=0)
    tooltip = {
        "html": (
            "<b>{record_id}</b> · {corridor_zone}<br/>"
            "Risk: <b>{risk_classification}</b><br/>"
            "Temp: {temp_str} | Delay Prob: {delay_str}<br/>"
            "Route Risk: {route_risk_level} | {ts_str}"
        ),
        "style": {
            "backgroundColor": "#0B1525",
            "color": "#E2E8F0",
            "border": "1px solid #38BDF8",
            "fontSize": "12px",
        },
    }
    return pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        map_style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
        tooltip=tooltip,
    )
