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
COLOR_NORMAL = "#2ecc71"
COLOR_WARNING = "#f1c40f"
COLOR_DANGER = "#e74c3c"

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
    except Exception:
        st.info("Log a meal below to see today's status.")

    st.divider()
    
    # NEW: MEAL QUICK-ADD
    st.subheader("⚡ Quick Log (Frequent Foods)")
    try:
        # Fetch top 5 most frequent foods from logs
        freq_res = supabase.rpc('get_frequent_foods').execute() # Requires a small SQL function
        # Fallback: Just grab the first 3 from the foods table if RPC isn't setup
        if not freq_res.data:
            freq_res = supabase.table("foods").select("*").limit(3).execute()
        
        if freq_res.data:
            cols = st.columns(len(freq_res.data))
            for idx, food in enumerate(freq_res.data):
                if cols[idx].button(f"➕ {food['food_name']}", use_container_width=True):
                    new_log = {"food_id": food['food_id'], "servings": 1.0, "log_date": str(datetime.now().date())}
                    supabase.table("daily_logs").insert(new_log).execute()
                    st.toast(f"Logged 1 serving of {food['food_name']}!")
                    st.rerun()
    except Exception:
        st.write("Log a few meals to see quick-add buttons here.")

    with st.expander("🍴 Manual Log"):
        try:
            food_query = supabase.table("foods").select("*").execute()
            if food_query.data:
                food_dict = {f["food_name"]: f for f in food_query.