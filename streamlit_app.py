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

# Define your targets here manually (since we don't have a targets table)
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
            # Math based on hardcoded constants above
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

    # Log Meal Form
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
            # Create a timestamp for cleaner sorting on the X-axis
            df["timestamp"] = pd.to_datetime(df["date"] + " " + df["time"])
            df = df.sort_values("timestamp")

            # 1. Blood Pressure Chart
            st.write("#### Blood Pressure")
            st.line_chart(
                df,
                x="timestamp",
                y=["blood_pressure_systolic", "blood_pressure_diastolic"],
            )

            # 2. Weight Chart
            st.write("#### Weight (lbs)")
            st.line_chart(df, x="timestamp", y="weight_lb")

            # 3. Glucose Chart
            st.write("#### Blood Glucose")
            st.line_chart(df, x="timestamp", y="blood_glucose")
    except Exception as e:
        st.info("Log your first vitals to see trend charts!")
