import streamlit as st
from supabase import create_client
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# 1. Setup Connection
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.set_page_config(page_title="My Health Dashboard", layout="wide")
st.title("💪 My Health Dashboard")

# Targets
TARGET_CALORIES = 2000
TARGET_PROTEIN = 150
TARGET_NET_CARBS = 50
TARGET_FIBER_MIN = 30
TARGET_FAT_MAX = 70

COLOR_NORMAL, COLOR_WARNING, COLOR_DANGER = "#2ecc71", "#f1c40f", "#e74c3c"

tab1, tab2, tab3 = st.tabs(
    ["🍴 Nutrition Budget", "🩺 Health Metrics", "🏃 Activity Tracker"]
)

# --- TAB 1: NUTRITION BUDGET (With Logic Zones) ---
with tab1:
    try:
        response = supabase.table("daily_variance").select("*").execute()
        if response.data:
            latest = response.data[0]
            st.subheader(f"Status for {latest['date']}")
            c1, c2, c3, c4, c5 = st.columns(5)

            # Current Values
            cals = int(latest.get("total_calories", 0))
            prot = int(latest.get("total_protein", 0))
            net_c = int(latest.get("total_net_carbs", 0))
            fat = int(latest.get("total_fat", 0))
            fib = int(latest.get("total_fiber", 0))

            # Helper for Ceiling Targets (Calories, Net Carbs, Fat)
            # Red: Over Target | Yellow: Within 10% below | Green: 11%+ below
            def get_ceiling_delta(current, target):
                if current > target:
                    return "inverse"  # Red
                if current >= (target * 0.90):  # Within 10% (90% to 100% of target)
                    return "off"  # Yellow/Grey
                return "normal"  # Green (11%+ below)

            # Helper for Floor Targets (Protein, Fiber)
            # Green: At or Above | Yellow: Within 10% below | Red: 11%+ below
            def get_floor_delta(current, target):
                if current >= target:
                    return "normal"  # Green
                if current >= (
                    target * 0.90
                ):  # Within 10% below (90% to 99% of target)
                    return "off"  # Yellow/Grey
                return "inverse"  # Red (11%+ below)

            # 1. Calories (Ceiling)
            c1.metric(
                "Calories",
                f"{cals}",
                f"{TARGET_CALORIES - cals} Left",
                delta_color=get_ceiling_delta(cals, TARGET_CALORIES),
            )

            # 2. Protein (Floor)
            c2.metric(
                "Protein",
                f"{prot}g",
                f"{prot - TARGET_PROTEIN} vs Target",
                delta_color=get_floor_delta(prot, TARGET_PROTEIN),
            )

            # 3. Net Carbs (Ceiling)
            c3.metric(
                "Net Carbs",
                f"{net_c}g",
                f"{TARGET_NET_CARBS - net_c} Left",
                delta_color=get_ceiling_delta(net_c, TARGET_NET_CARBS),
            )

            # 4. Total Fat (Ceiling)
            c4.metric(
                "Total Fat",
                f"{fat}g",
                f"{TARGET_FAT_MAX - fat} Left",
                delta_color=get_ceiling_delta(fat, TARGET_FAT_MAX),
            )

            # 5. Fiber (Floor)
            c5.metric(
                "Fiber",
                f"{fib}g",
                f"{fib - TARGET_FIBER_MIN} vs Target",
                delta_color=get_floor_delta(fib, TARGET_FIBER_MIN),
            )

    except Exception as e:
        st.error(f"Dashboard error: {e}")

# --- TAB 2: HEALTH METRICS ---
with tab2:
    try:
        last_res = (
            supabase.table("health_metrics")
            .select("*")
            .order("date", desc=True)
            .order("time", desc=True)
            .limit(1)
            .execute()
        )
        if last_res.data:
            v = last_res.data[0]
            s, d, g, w = (
                int(v["blood_pressure_systolic"]),
                int(v["blood_pressure_diastolic"]),
                int(v["blood_glucose"]),
                float(v["weight_lb"]),
            )
            st.subheader("🏷️ Latest Vitals")
            m1, m2, m3 = st.columns(3)
            m1.metric("Blood Pressure", f"{s}/{d}")
            m2.metric("Glucose", f"{g} mg/dL")
            m3.metric("Weight", f"{w} lbs")
    except:
        pass
    with st.expander("Log New Vitals"):
        with st.form("v_form", clear_on_submit=True):
            col_d, col_t = st.columns(2)
            d_val, t_val = col_d.date_input("Date"), col_t.time_input("Time")
            c1, c2, c3 = st.columns(3)
            sys, dia = (
                c1.number_input("Systolic", 120),
                c2.number_input("Diastolic", 80),
            )
            weight_v, glu_v = (
                c3.number_input("Weight", value=180.0),
                st.number_input("Glucose", value=100),
            )
            if st.form_submit_button("Save"):
                supabase.table("health_metrics").insert(
                    {
                        "date": str(d_val),
                        "time": str(t_val),
                        "blood_pressure_systolic": sys,
                        "blood_pressure_diastolic": dia,
                        "blood_glucose": glu_v,
                        "weight_lb": weight_v,
                    }
                ).execute()
                st.rerun()

# --- TAB 3: ACTIVITY TRACKER ---
with tab3:
    st.subheader("🏃 Log Activity")
    category = st.radio(
        "Activity Type:", ["Strength", "Static", "Cardio"], horizontal=True
    )
    with st.form("activity_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        ex_date, ex_name = col1.date_input("Date"), col2.text_input("Exercise Name")
        c1, c2, c3 = st.columns(3)
        dur, sets, reps, dist = 0.0, 0, 0, 0.0
        if category == "Strength":
            sets, reps = c1.number_input("Sets", 0), c2.number_input("Reps", 0)
        elif category == "Static":
            dur, sets, reps = (
                c1.number_input("Duration (min)", 0.0, step=0.1),
                c2.number_input("Sets", 0),
                c3.number_input("Reps", 0),
            )
        elif category == "Cardio":
            dur, dist = (
                c1.number_input("Duration (min)", 0.0, step=0.1),
                c2.number_input("Distance (mi)", 0.0, step=0.1),
            )
        if st.form_submit_button("Save Activity"):
            if ex_name:
                act_data = {
                    "date": str(ex_date),
                    "exercise_name": ex_name,
                    "duration_min": float(dur),
                    "sets": int(sets),
                    "reps": int(reps),
                    "distance_miles": float(dist),
                    "type": category,
                }
                supabase.table("activity_logs").insert(act_data).execute()
                st.rerun()

    st.divider()
    try:
        act_res = (
            supabase.table("activity_logs")
            .select("*")
            .order("date", desc=False)
            .execute()
        )
        if act_res.data:
            df_a = pd.DataFrame(act_res.data)
            df_a["pace_min_mi"] = df_a.apply(
                lambda r: (
                    round(r["duration_min"] / r["distance_miles"], 2)
                    if r["distance_miles"] > 0
                    else None
                ),
                axis=1,
            )

            tc1, tc2 = st.columns(2)
            tc1.subheader("📈 Duration Trends")
            st.line_chart(df_a, x="date", y="duration_min")
            tc2.subheader("⏱️ Cardio Pace")
            df_c = df_a[df_a["type"] == "Cardio"].dropna(subset=["pace_min_mi"])
            if not df_c.empty:
                st.line_chart(df_c, x="date", y="pace_min_mi")

            st.subheader("📜 Activity History")
            st.dataframe(
                df_a[
                    [
                        "date",
                        "exercise_name",
                        "type",
                        "duration_min",
                        "distance_miles",
                        "pace_min_mi",
                        "sets",
                        "reps",
                    ]
                ],
                use_container_width=True,
            )
            csv_act = df_a.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Download Workout CSV", data=csv_act, file_name="workouts.csv"
            )
    except:
        pass
