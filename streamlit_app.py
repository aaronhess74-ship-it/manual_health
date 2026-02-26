import streamlit as st
from supabase import create_client
from datetime import datetime

# 1. Setup Connection
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.title("💪 My Health Dashboard")

# Create Tabs for Organization
tab1, tab2 = st.tabs(["🍴 Nutrition Budget", "🩺 Health Metrics"])

# --- TAB 1: NUTRITION (Your existing working logic) ---
with tab1:
    try:
        response = supabase.table("daily_variance").select("*").execute()
        if response.data:
            latest = response.data[0]
            st.subheader(f"Status for {latest['date']}")
            col1, col2, col3 = st.columns(3)
            col1.metric(
                "Calories",
                f"{latest['total_calories']}",
                f"{latest['calorie_variance'] * -1} Left",
            )
            col2.metric(
                "Protein",
                f"{latest['total_protein']}g",
                f"{latest['protein_variance'] * -1} Left",
            )
            col3.metric(
                "Carbs",
                f"{latest['total_carbs']}g",
                f"{latest['carbs_variance'] * -1} Left",
            )
    except:
        st.info("Log a meal to see today's budget.")

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

    # Library Builder
    with st.expander("➕ Add New Food to Library"):
        with st.form("new_food_form", clear_on_submit=True):
            f_name = st.text_input("Food Name")
            f_brand = st.text_input("Brand")
            f_size = st.text_input("Serving Size")
            c1, c2, c3 = st.columns(3)
            f_cal = c1.number_input("Calories", min_value=0)
            f_prot = c2.number_input("Protein (g)", min_value=0)
            f_carb = c3.number_input("Carbs (g)", min_value=0)
            f_fat = st.number_input("Fat (g)", min_value=0)
            if st.form_submit_button("Save Food") and f_name:
                new_food = {
                    "food_name": f_name,
                    "brand": f_brand,
                    "serving_size": f_size,
                    "calories": f_cal,
                    "protein_g": f_prot,
                    "carbs_g": f_carb,
                    "fat_g": f_fat,
                }
                supabase.table("foods").insert(new_food).execute()
                st.success(f"Added {f_name}!")
                st.rerun()

# --- TAB 2: HEALTH METRICS (New Section) ---
with tab2:
    st.subheader("🩺 Log Vitals")

    with st.form("vitals_form", clear_on_submit=True):
        col_d, col_t = st.columns(2)
        m_date = col_d.date_input("Date", value=datetime.now().date())
        m_time = col_t.time_input("Time", value=datetime.now().time())

        c1, c2 = st.columns(2)
        sys = c1.number_input(
            "Systolic (Top #)", min_value=50, max_value=250, value=120
        )
        dia = c2.number_input(
            "Diastolic (Bottom #)", min_value=30, max_value=150, value=80
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
                "notes": m_notes,
            }
            try:
                # Target the exact table name 'health_metrics'
                supabase.table("health_metrics").insert(new_metric).execute()
                st.success("Vitals saved successfully!")
            except Exception as e:
                st.error(f"Error saving vitals: {e}")

    # Optional: Show recent history
    st.divider()
    st.subheader("Recent Logs")
    try:
        history = (
            supabase.table("health_metrics")
            .select("*")
            .order("date", desc=True)
            .limit(5)
            .execute()
        )
        if history.data:
            st.table(history.data)
    except:
        pass
