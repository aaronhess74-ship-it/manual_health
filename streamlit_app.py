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
    except: pass

    st.divider()
    
    # Quick Log Logic
    st.subheader("⚡ Quick Log")
    try:
        recent_logs = supabase.table("daily_logs").select("food_id, foods(food_name)").order("log_id", desc=True).limit(20).execute()
        if recent_logs.data:
            seen = set()
            quick_foods = []
            for r in recent_logs.data:
                fid, fname = r['food_id'], r['foods']['food_name']
                if fid not in seen:
                    quick_foods.append({'id': fid, 'name': fname})
                    seen.add(fid)
                if len(quick_foods) == 5: break
            
            cols = st.columns(len(quick_foods))
            for i, food in enumerate(quick_foods):
                if cols[i].button(f"➕ {food['name']}", key=f"q_{food['id']}"):
                    supabase.table("daily_logs").insert({"food_id": food['id'], "servings": 1.0, "log_date": str(datetime.now().date())}).execute()
                    st.rerun()
    except: st.caption("Log items to see Quick Log buttons.")

    st.divider()
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("🍴 Log Existing Food")
        try:
            food_query = supabase.table("foods").select("*").order("food_name").execute()
            if food_query.data:
                food_dict = {f["food_name"]: f for f in food_query.data}
                selected_name = st.selectbox("Search database...", options=list(food_dict.keys()), index=None, placeholder="Type to search...")
                servings = st.number_input("Servings", min_value=0.1, value=1.0, step=0.1)
                if st.button("Log Meal") and selected_name:
                    supabase.table("daily_logs").insert({"food_id": food_dict[selected_name]["food_id"], "servings": servings, "log_date": str(datetime.now().date())}).execute()
                    st.rerun()
        except: pass

    with col_b:
        st.subheader("🆕 Add New Food")
        with st.form("new_food_form", clear_on_submit=True):
            new_name = st.text_input("Food Name")
            c1, c2, c3 = st.columns(3)
            nc, np, ncb = c1.number_input("Cals", 0), c2.number_input("Prot", 0), c3.number_input("Carb", 0)
            if st.form_submit_button("Save & Log"):
                if new_name:
                    f_res = supabase.table("foods").insert({"food_name": new_name, "calories": nc, "protein_g": np, "carbs_g": ncb}).execute()
                    if f_res.data:
                        supabase.table("daily_logs").insert({"food_id": f_res.data[0]['food_id'], "servings": 1.0, "log_date": str(datetime.now().date())}).execute()
                        st.rerun()

    st.divider()
    st.subheader("📜 Today's Log History")
    try:
        history_res = supabase.table("daily_logs").select("log_id, servings, foods(food_name, calories)").eq("log_date", str(datetime.now().date())).execute()
        if history_res.data:
            for item in history_res.data:
                c1, c2, c3 = st.columns([3, 1, 1])
                c1.write(f"**{item['foods']['food_name']}**")
                c2.write(f"{int(item['foods']['calories'] * item['servings'])} cal")
                if c3.button("🗑️", key=f"del_{item['log_id']}"):
                    supabase.table("daily_logs").delete().eq("log_id", item['log_id']).execute()
                    st.rerun()
    except: pass

# --- TAB 2: HEALTH METRICS ---
with tab2:
    bp_line_color, glu_line_color, wgt_line_color = COLOR_NORMAL, COLOR_NORMAL, COLOR_NORMAL
    
    # 1. Latest Status & Warnings
    try:
        last_res = supabase.table("health_metrics").select("*").order("date", desc=True).order("time", desc=True).limit(1).execute()