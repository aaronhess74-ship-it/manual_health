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

# Constants
TARGET_CALORIES, TARGET_PROTEIN, TARGET_CARBS = 2000, 150, 250
COLOR_NORMAL, COLOR_WARNING, COLOR_DANGER = "#2ecc71", "#f1c40f", "#e74c3c"

tab1, tab2, tab3 = st.tabs(
    ["🍴 Nutrition Budget", "🩺 Health Metrics", "🏃 Activity Tracker"]
)

# --- TAB 1: NUTRITION BUDGET ---
with tab1:
    try:
        response = supabase.table("daily_variance").select("*").execute()
        if response.data:
            latest = response.data[0]
            st.subheader(f"Status for {latest['date']}")
            # Expanded to 5 columns for full macro tracking
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Calories", f"{int(latest.get('total_calories', 0))}")
            c2.metric("Protein", f"{int(latest.get('total_protein', 0))}g")
            c3.metric("Carbs", f"{int(latest.get('total_carbs', 0))}g")
            c4.metric("Fat", f"{int(latest.get('total_fat', 0))}g")
            c5.metric("Fiber", f"{int(latest.get('total_fiber', 0))}g")
    except Exception as e:
        st.error(f"Dashboard error: {e}")

    st.divider()

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("🍴 Log Existing Food")
        try:
            food_query = (
                supabase.table("foods").select("*").order("food_name").execute()
            )
            if food_query.data:
                food_dict = {f["food_name"]: f for f in food_query.data}
                selected_name = st.selectbox(
                    "Search database...", options=list(food_dict.keys()), index=None
                )

                if selected_name:
                    selected_food = food_dict[selected_name]

                    # Logic to identify if Fat or Fiber data is missing/null
                    fat_val = selected_food.get("fat_g")
                    fib_val = selected_food.get("fiber_g")
                    needs_data = (fat_val is None or pd.isna(fat_val)) or (
                        fib_val is None or pd.isna(fib_val)
                    )

                    if needs_data:
                        st.warning(f"⚠️ {selected_name} is missing Fat or Fiber info.")
                        c_fat = st.number_input("Enter Fat (g)", value=0.0)
                        c_fib = st.number_input("Enter Fiber (g)", value=0.0)
                        if st.button("Update Food & Log"):
                            supabase.table("foods").update(
                                {"fat_g": c_fat, "fiber_g": c_fib}
                            ).eq("food_id", selected_food["food_id"]).execute()
                            supabase.table("daily_logs").insert(
                                {
                                    "food_id": selected_food["food_id"],
                                    "servings": 1.0,
                                    "log_date": str(datetime.now().date()),
                                }
                            ).execute()
                            st.rerun()
                    else:
                        servings = st.number_input(
                            "Servings", min_value=0.1, value=1.0, step=0.1
                        )
                        if st.button("Log Meal"):
                            supabase.table("daily_logs").insert(
                                {
                                    "food_id": selected_food["food_id"],
                                    "servings": servings,
                                    "log_date": str(datetime.now().date()),
                                }
                            ).execute()
                            st.rerun()
        except:
            pass

    with col_b:
        st.subheader("🆕 Add New Food")
        with st.form("new_food_form", clear_on_submit=True):
            n_name = st.text_input("Food Name")
            c1, c2, c3 = st.columns(3)
            n_cal = c1.number_input("Calories", 0)
            n_pro = c2.number_input("Protein", 0)
            n_carb = c3.number_input("Carbs", 0)

            c4, c5 = st.columns(2)
            n_fat = c4.number_input("Fat", 0)
            n_fib = c5.number_input("Fiber", 0)

            if st.form_submit_button("Save & Log"):
                if n_name:
                    res = (
                        supabase.table("foods")
                        .insert(
                            {
                                "food_name": n_name,
                                "calories": n_cal,
                                "protein_g": n_pro,
                                "carbs_g": n_carb,
                                "fat_g": n_fat,
                                "fiber_g": n_fib,
                            }
                        )
                        .execute()
                    )
                    if res.data:
                        supabase.table("daily_logs").insert(
                            {
                                "food_id": res.data[0]["food_id"],
                                "servings": 1.0,
                                "log_date": str(datetime.now().date()),
                            }
                        ).execute()
                        st.rerun()

# --- TAB 2: HEALTH METRICS ---
with tab2:
    bp_line_color, glu_line_color, wgt_line_color = (
        COLOR_NORMAL,
        COLOR_NORMAL,
        COLOR_NORMAL,
    )
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
            if s < 120 and d < 80:
                bp_s, bp_line_color = "🟢 Normal", COLOR_NORMAL
            elif 120 <= s < 130 and d < 80:
                bp_s, bp_line_color = "🟡 Elevated", COLOR_WARNING
            else:
                bp_s, bp_line_color = "🔴 Hypertension", COLOR_DANGER
            if g < 100:
                g_s, glu_line_color = "🟢 Normal", COLOR_NORMAL
            elif 100 <= g < 126:
                g_s, glu_line_color = "🟡 Pre-diabetes", COLOR_WARNING
            else:
                g_s, glu_line_color = "🔴 High", COLOR_DANGER
            if 155 <= w <= 179:
                w_s, wgt_line_color = "🟢 Goal Range", COLOR_NORMAL
            elif 180 <= w <= 200:
                w_s, wgt_line_color = "🟡 Warning Range", COLOR_WARNING
            else:
                w_s, wgt_line_color = "🔴 Above Range", COLOR_DANGER

            st.subheader("🏷️ Latest Vitals Status")
            m1, m2, m3 = st.columns(3)
            m1.metric("Blood Pressure", f"{s}/{d}")
            m1.markdown(f"**Status:** {bp_s}")
            m2.metric("Glucose", f"{g} mg/dL")
            m2.markdown(f"**Status:** {g_s}")
            m3.metric("Weight", f"{w} lbs")
            m3.markdown(f"**Status:** {w_s}")
    except:
        pass

    st.divider()
    with st.expander("🩺 Log New Vitals"):
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

    st.divider()
    st.subheader("📈 Health Trends")
    time_view = st.radio(
        "Range:", ["7 Days", "30 Days", "Year"], horizontal=True, key="health_range"
    )
    cutoff = datetime.now().date() - timedelta(
        days=7 if time_view == "7 Days" else (30 if time_view == "30 Days" else 365)
    )
    try:
        res = (
            supabase.table("health_metrics")
            .select("*")
            .gte("date", cutoff.isoformat())
            .order("date", desc=False)
            .execute()
        )
        if res.data:
            df_h = pd.DataFrame(res.data)
            st.write("#### Blood Pressure")
            st.line_chart(
                df_h,
                x="date",
                y=["blood_pressure_systolic", "blood_pressure_diastolic"],
                color=[bp_line_color, "#5dade2"],
            )
            st.write("#### Weight (lbs)")
            st.line_chart(df_h, x="date", y="weight_lb", color=wgt_line_color)
            st.write("#### Blood Glucose")
            st.line_chart(df_h, x="date", y="blood_glucose", color=glu_line_color)

            st.divider()
            csv_vitals = df_h.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Download Vitals Log (CSV)",
                data=csv_vitals,
                file_name=f"vitals_log_{datetime.now().date()}.csv",
            )
    except:
        pass

# --- TAB 3: ACTIVITY TRACKER ---
with tab3:
    st.subheader("🏃 Log Activity")
    category = st.radio(
        "Activity Type:", ["Strength", "Static", "Cardio"], horizontal=True
    )

    with st.form("activity_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        ex_date = col1.date_input("Date", value=datetime.now().date())
        ex_name = col2.text_input("Exercise Name (e.g. Walking, Pushups, Planks)")

        c1, c2, c3 = st.columns(3)
        dur, sets, reps, dist = 0.0, 0, 0, 0.0

        if category == "Strength":
            sets = c1.number_input("Sets", min_value=0, value=0)
            reps = c2.number_input("Reps", min_value=0, value=0)
        elif category == "Static":
            dur = c1.number_input("Duration (min)", min_value=0.0, value=0.0, step=0.1)
            sets = c2.number_input("Sets", min_value=0, value=0)
            reps = c3.number_input("Reps", min_value=0, value=0)
        elif category == "Cardio":
            dur = c1.number_input("Duration (min)", min_value=0.0, value=0.0, step=0.1)
            dist = c2.number_input("Distance (mi)", min_value=0.0, value=0.0, step=0.1)

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

            # PACE CALCULATION
            df_a["pace_min_mi"] = df_a.apply(
                lambda r: (
                    round(r["duration_min"] / r["distance_miles"], 2)
                    if r["distance_miles"] > 0
                    else None
                ),
                axis=1,
            )

            # --- CHARTS ---
            chart_col1, chart_col2 = st.columns(2)

            with chart_col1:
                st.subheader("📈 Duration Trends")
                last_dur = df_a["duration_min"].iloc[-1]
                act_color = (
                    COLOR_NORMAL
                    if last_dur >= 30
                    else (COLOR_WARNING if last_dur >= 11 else COLOR_DANGER)
                )
                st.line_chart(df_a, x="date", y="duration_min", color=act_color)

            with chart_col2:
                st.subheader("⏱️ Cardio Pace (min/mi)")
                df_cardio = df_a[df_a["type"] == "Cardio"].dropna(
                    subset=["pace_min_mi"]
                )
                if not df_cardio.empty:
                    st.line_chart(df_cardio, x="date", y="pace_min_mi", color="#3498db")
                else:
                    st.info("Log Cardio distance to see pace trends.")

            st.divider()
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
                "📥 Download Workout Log (CSV)",
                data=csv_act,
                file_name=f"workout_log_{datetime.now().date()}.csv",
            )
        else:
            st.info("No activities logged yet.")
    except Exception as e:
        st.error(f"Error loading trends: {e}")
