import streamlit as st
from supabase import create_client
from datetime import datetime, timedelta
import pandas as pd

# 1. Setup Connection
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.set_page_config(page_title="My Health Dashboard", layout="wide")
st.title("💪 My Health Dashboard")

# Manual Targets
TARGET_CALORIES = 2000
TARGET_PROTEIN = 150
TARGET_CARBS = 250

tab1, tab2 = st.tabs(["🍴 Nutrition Budget", "🩺 Health Metrics"])

# --- TAB 1: NUTRITION BUDGET ---
with tab1:
    try:
        response = supabase.table("daily_variance").select("*").execute()
        if response.data:
            latest = response.data[0]
            st.subheader(f"Status for {latest['date']}")

            c1, c2, c3 = st.columns(3)
            c1.metric(
                "Calories",
                f"{latest['total_calories']}",
                f"{TARGET_CALORIES - latest['total_calories']} Left",
            )
            c2.metric(
                "Protein",
                f"{latest['total_protein']}g",
                f"{TARGET_PROTEIN - latest['total_protein']}g Left",
            )
            c3.metric(
                "Carbs",
                f"{latest['total_carbs']}g",
                f"{TARGET_CARBS - latest['total_carbs']}g Left",
            )
    except:
        st.info("Log a meal below to see today's nutrition status.")

    st.divider()

    st.subheader("🍴 Log a Meal")
    try:
        food_query = supabase.table("foods").select("*").execute()
        if food_query.data:
            food_dict = {f["food_name"]: f for f in food_query.data}
            with st.form("log_form"):
                selected_name = st.selectbox(
                    "Select Food", options=list(food_dict.keys())
                )
                servings = st.number_input(
                    "Servings", min_value=0.1, value=1.0, step=0.1
                )
                if st.form_submit_button("Add to Diary"):
                    food_record = food_dict[selected_name]
                    new_log = {
                        "food_id": food_record["food_id"],
                        "servings": servings,
                        "log_date": str(datetime.now().date()),
                    }
                    supabase.table("daily_logs").insert(new_log).execute()
                    st.success(f"Logged {selected_name}!")
                    st.rerun()
    except Exception as e:
        st.error(f"Food Log Error: {e}")

# --- TAB 2: HEALTH METRICS ---
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
            "Weight (lbs)", min_value=0.0, max_value=500.0, step=0.1
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
            try:
                supabase.table("health_metrics").insert(new_metric).execute()
                st.success("Vitals saved!")
                st.rerun()
            except Exception as e:
                st.error(f"Error saving to Supabase: {e}")

    st.divider()

    # --- TIME VIEW FILTER ---
    st.subheader("📈 Health Trends")
    time_view = st.radio("View Range:", ["7 Days", "30 Days", "Year"], horizontal=True)

    today = datetime.now().date()
    if time_view == "7 Days":
        cutoff = today - timedelta(days=7)
    elif time_view == "30 Days":
        cutoff = today - timedelta(days=30)
    else:
        cutoff = today - timedelta(days=365)

    try:
        # Fetch data and sort by date/time
        res = (
            supabase.table("health_metrics")
            .select("*")
            .gte("date", cutoff.isoformat())
            .order("date", desc=False)
            .order("time", desc=False)
            .execute()
        )

        if res.data:
            df = pd.DataFrame(res.data)

            # 1. Convert numeric columns
            metrics = [
                "blood_pressure_systolic",
                "blood_pressure_diastolic",
                "blood_glucose",
                "weight_lb",
            ]
            for m in metrics:
                df[m] = pd.to_numeric(df[m], errors="coerce")

            # 2. Prepare the Chart Data
            # We use the 'date' column for the X-axis so it groups by day visually.
            # Because we DON'T aggregate, Streamlit will plot multiple points on the same vertical 'day' line.

            st.write(f"#### Blood Pressure Trend")
            st.line_chart(
                df, x="date", y=["blood_pressure_systolic", "blood_pressure_diastolic"]
            )

            weight_df = df[df["weight_lb"] > 0].copy()
            if not weight_df.empty:
                st.write(f"#### Weight Trend (lbs)")
                st.line_chart(weight_df, x="date", y="weight_lb")

            st.write(f"#### Blood Glucose Trend")
            st.line_chart(df, x="date", y="blood_glucose")

        else:
            st.info(f"No data found for the last {time_view}.")

    except Exception as e:
        st.error(f"Chart Display Error: {e}")
