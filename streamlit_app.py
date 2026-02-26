import streamlit as st
from supabase import create_client
from datetime import datetime
import pandas as pd

# 1. Setup Connection
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.set_page_config(page_title="Health Dashboard", layout="wide")
st.title("💪 My Health Dashboard")

tab1, tab2, tab3 = st.tabs(["🍴 Nutrition Budget", "🩺 Health Metrics", "⚙️ Settings"])


# --- HELPERS ---
def get_targets():
    res = (
        supabase.table("user_targets")
        .select("*")
        .order("updated_at", desc=True)
        .limit(1)
        .execute()
    )
    return (
        res.data[0]
        if res.data
        else {"target_calories": 2000, "target_protein": 150, "target_carbs": 250}
    )


targets = get_targets()

# --- TAB 1: NUTRITION BUDGET (No changes here) ---
with tab1:
    try:
        response = supabase.table("daily_variance").select("*").execute()
        if response.data:
            latest = response.data[0]
            st.subheader("Daily Budget Status")
            c1, c2, c3 = st.columns(3)
            c1.metric(
                "Calories",
                f"{latest['total_calories']}",
                f"{targets['target_calories'] - latest['total_calories']} Left",
            )
            c2.metric(
                "Protein",
                f"{latest['total_protein']}g",
                f"{targets['target_protein'] - latest['total_protein']}g Left",
            )
            c3.metric(
                "Carbs",
                f"{latest['total_carbs']}g",
                f"{targets['target_carbs'] - latest['total_carbs']}g Left",
            )
    except:
        st.info("Log a meal below to see today's status.")

    st.divider()
    # [Rest of Nutrition Logic remains the same]

# --- TAB 2: HEALTH METRICS (Updated for Weight & BP) ---
with tab2:
    st.subheader("🩺 Log Vitals & Weight")

    with st.form("vitals_form", clear_on_submit=True):
        col_d, col_t = st.columns(2)
        m_date = col_d.date_input("Date", value=datetime.now().date())
        m_time = col_t.time_input("Time", value=datetime.now().time())

        c1, c2, c3 = st.columns(3)
        sys = c1.number_input("Systolic", min_value=50, max_value=250, value=120)
        dia = c2.number_input("Diastolic", min_value=30, max_value=150, value=80)
        weight = c3.number_input(
            "Weight (lbs)", min_value=0.0, max_value=500.0, value=180.0, step=0.1
        )

        glucose = st.number_input(
            "Blood Glucose (mg/dL)", min_value=0, max_value=600, value=100
        )
        m_notes = st.text_area("Notes")

        if st.form_submit_button("Save Metrics"):
            new_metric = {
                "date": str(m_date),
                "time": str(m_time),
                "blood_pressure_systolic": sys,
                "blood_pressure_diastolic": dia,
                "blood_glucose": glucose,
                "weight_lb": weight,
                "notes": m_notes,
            }
            supabase.table("health_metrics").insert(new_metric).execute()
            st.success("Metrics saved!")
            st.rerun()

    st.divider()
    st.subheader("📈 Health Trends")

    try:
        res = (
            supabase.table("health_metrics")
            .select("*")
            .order("date", desc=True)
            .limit(50)
            .execute()
        )
        if res.data:
            df = pd.DataFrame(res.data)
            # Combine Date and Time for a precise X-axis if multiple entries exist per day
            df["timestamp"] = pd.to_datetime(df["date"] + " " + df["time"])
            df = df.sort_values("timestamp")

            # 1. Blood Pressure Trend (Multi-line)
            st.write("#### Blood Pressure Trend")
            st.line_chart(
                df,
                x="timestamp",
                y=["blood_pressure_systolic", "blood_pressure_diastolic"],
            )

            # 2. Weight Trend
            st.write("#### Weight Trend (lbs)")
            st.line_chart(df, x="timestamp", y="weight_lb")

            # 3. Glucose Trend
            st.write("#### Blood Glucose Trend")
            st.line_chart(df, x="timestamp", y="blood_glucose")

    except Exception as e:
        st.info("Log your metrics to generate charts.")

# --- TAB 3: SETTINGS ---
with tab3:
    st.subheader("🎯 Daily Goal Targets")
    with st.form("settings_form"):
        new_cal = st.number_input("Calorie Target", value=targets["target_calories"])
        new_prot = st.number_input(
            "Protein Target (g)", value=targets["target_protein"]
        )
        new_carb = st.number_input("Carbs Target (g)", value=targets["target_carbs"])

        if st.form_submit_button("Update Targets"):
            supabase.table("user_targets").insert(
                {
                    "target_calories": new_cal,
                    "target_protein": new_prot,
                    "target_carbs": new_carb,
                }
            ).execute()
            st.success("Targets updated!")
            st.rerun()
