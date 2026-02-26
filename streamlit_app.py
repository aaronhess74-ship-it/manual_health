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

# Color Constants
COLOR_NORMAL = "#2ecc71"  # Green
COLOR_WARNING = "#f1c40f" # Amber/Yellow
COLOR_DANGER = "#e74c3c"  # Red

tab1, tab2 = st.tabs(["🍴 Nutrition Budget", "🩺 Health Metrics"])

# --- TAB 1: NUTRITION BUDGET ---
with tab1:
    try:
        response = supabase.table("daily_variance").select("*").execute()
        if response.data:
            latest = response.data[0]
            st.subheader(f"Status for {latest['date']}")
            c1, c2, c3 = st.columns(3)
            c1.metric("Calories", f"{latest['total_calories']}", f"{TARGET_CALORIES - latest['total_calories']} Left")
            c2.metric("Protein", f"{latest['total_protein']}g", f"{TARGET_PROTEIN - latest['total_protein']}g Left")
            c3.metric("Carbs", f"{latest['total_carbs']}g", f"{TARGET_CARBS - latest['total_carbs']}g Left")
    except:
        st.info("Log a meal below to see today's nutrition status.")

    st.divider()
    st.subheader("🍴 Log a Meal")
    try:
        food_query = supabase.table("foods").select("*").execute()
        if food_query.data:
            food_dict = {f["food_name"]: f for f in food_query.data}
            with st.form("log_form"):
                selected_name = st.selectbox("Select Food", options=list(food_dict.keys()))
                servings = st.number_input("Servings", min_value=0.1, value=1.0, step=0.1)
                if st.form_submit_button("Add to Diary"):
                    food_record = food_dict[selected_name]
                    new_log = {"food_id": food_record["food_id"], "servings": servings, "log_date": str(datetime.now().date())}
                    supabase.table("daily_logs").insert(new_log).execute()
                    st.rerun()
    except Exception: pass

    st.divider()
    st.subheader("📜 Today's Log History")
    try:
        history_res = supabase.table("daily_logs").select("log_id, servings, log_date, foods(food_name, calories)").eq("log_date", str(datetime.now().date())).execute()
        if history_res.data:
            for item in history_res.data:
                col1, col2, col3 = st.columns([3, 1, 1])
                col1.write(f"**{item['foods']['food_name']}** ({item['servings']} servings)")
                col2.write(f"{int(item['foods']['calories'] * item['servings'])} cal")
                if col3.button("🗑️", key=f"del_{item['log_id']}"):
                    supabase.table("daily_logs").delete().eq("log_id", item['log_id']).execute()
                    st.rerun()
    except Exception: pass

# --- TAB 2: HEALTH METRICS ---
with tab2:
    # Default Trend Colors
    bp_line_color = COLOR_NORMAL
    glu_line_color = COLOR_NORMAL
    wgt_line_color = COLOR_NORMAL
    
    st.subheader("🏷️ Latest Vitals Status")
    try:
        last_res = supabase.table("health_metrics").select("*").order("date", desc=True).order("time", desc=True).limit(1).execute()
        if last_res.data:
            v = last_res.data[0]
            s, d, g, w = int(v['blood_pressure_systolic']), int(v['blood_pressure_diastolic']), int(v['blood_glucose']), float(v['weight_lb'])
            
            # 1. BP Logic & Color
            if s < 120 and d < 80: 
                bp_status, bp_line_color = "🟢 Normal", COLOR_NORMAL
            elif 120 <= s < 130 and d < 80: 
                bp_status, bp_line_color = "🟡 Elevated", COLOR_WARNING
            else: 
                bp_status, bp_line_color = "🔴 Hypertension", COLOR_DANGER
            
            # 2. Glucose Logic & Color
            if g < 100: 
                g_status, glu_line_color = "🟢 Normal", COLOR_NORMAL
            elif 100 <= g < 126: 
                g_status, glu_line_color = "🟡 Pre-diabetes", COLOR_WARNING
            else: 
                g_status, glu_line_color = "🔴 High", COLOR_DANGER

            # 3. Weight Logic & Color
            if 155 <= w <= 179:
                w_status, wgt_line_color = "🟢 Goal Range", COLOR_NORMAL
            elif 180 <= w <= 200:
                w_status, wgt_line_color = "🟡 Warning Range", COLOR_WARNING