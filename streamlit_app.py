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
TARGET_CALORIES, TARGET_PROTEIN, TARGET_NET_CARBS = (
    2000,
    150,
    50,
)  # Adjusted carb target for Net Carbs
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

            # Net Carbs is now the primary metric in the display
            c1, c2, c3, c4, c5 = st.columns(5)

            net_carbs = latest.get("total_net_carbs", 0)

            c1.metric(
                "Calories",
                f"{int(latest.get('total_calories', 0))}",
                f"{TARGET_CALORIES - int(latest.get('total_calories', 0))} Left",
            )
            c2.metric(
                "Protein",
                f"{int(latest.get('total_protein', 0))}g",
                f"{TARGET_PROTEIN - int(latest.get('total_protein', 0))}g Left",
            )
            c3.metric(
                "Net Carbs",
                f"{int(net_carbs)}g",
                f"{TARGET_NET_CARBS - int(net_carbs)}g Left",
            )
            c4.metric("Total Fat", f"{int(latest.get('total_fat', 0))}g")
            c5.metric("Fiber", f"{int(latest.get('total_fiber', 0))}g")
    except:
        pass

    st.divider()
    st.subheader("⚡ Quick Log")
    try:
        recent_logs = (
            supabase.table("daily_logs")
            .select("food_id, foods(food_name)")
            .order("log_id", desc=True)
            .limit(20)
            .execute()
        )
        if recent_logs.data:
            seen, quick_foods = set(), []
            for r in recent_logs.data:
                fid, fname = r["food_id"], r["foods"]["food_name"]
                if fid not in seen:
                    quick_foods.append({"id": fid, "name": fname})
                    seen.add(fid)
                if len(quick_foods) == 5:
                    break
            cols = st.columns(len(quick_foods))
            for i, food in enumerate(quick_foods):
                if cols[i].button(f"➕ {food['name']}", key=f"q_{food['id']}"):
                    supabase.table("daily_logs").insert(
                        {
                            "food_id": food["id"],
                            "servings": 1.0,
                            "log_date": str(datetime.now().date()),
                        }
                    ).execute()
                    st.rerun()
    except:
        st.caption("Log items to see Quick Log.")

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
                    fat_v, fib_v = (
                        selected_food.get("fat_g"),
                        selected_food.get("fiber_g"),
                    )
                    if (
                        fat_v is None
                        or pd.isna(fat_v)
                        or fib_v is None
                        or pd.isna(fib_v)
                    ):
                        st.info(f"💡 Updating macros for {selected_name}")
                        u_fat = st.number_input("Fat (g)", value=0.0)
                        u_fib = st.number_input("Fiber (g)", value=0.0)
                        if st.button("Update & Log"):
                            supabase.table("foods").update(
                                {"fat_g": u_fat, "fiber_g": u_fib}
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
            n_cal, n_pro, n_carb = (
                c1.number_input("Cals", 0),
                c2.number_input("Prot", 0),
                c3.number_input("Carb", 0),
            )
            c4, c5 = st.columns(2)
            n_fat, n_fib = c4.number_input("Fat", 0), c5.number_input("Fiber", 0)
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

    st.divider()
    st.subheader("📜 Today's Log History")
    try:
        history_res = (
            supabase.table("daily_logs")
            .select("log_id, servings, foods(food_name, calories)")
            .eq("log_date", str(datetime.now().date()))
            .execute()
        )
        if history_res.data:
            for item in history_res.data:
                c1, c2, c3 = st.columns([3, 1, 1])
                c1.write(f"**{item['foods']['food_name']}**")
                c2.write(f"{int(item['foods']['calories'] * item['servings'])} cal")
                if c3.button("🗑️", key=f"del_{item['log_id']}"):
                    supabase.table("daily_logs").delete().eq(
                        "log_id", item["log_id"]
                    ).execute()
                    st.rerun()
    except:
        pass

# --- TAB 2 & 3 (Preserved from previous state) ---
# [Vitals and Activity sections remain exactly as in the last iteration]
