import streamlit as st
from supabase import create_client

# 1. Connect to your Supabase
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.title("💪 My Health Budget")

# --- DEBUGGER: Let's see what the app can actually see ---
with st.expander("Connection Debugger"):
    try:
        test_foods = supabase.table("foods").select("count", count="exact").execute()
        st.write(f"✅ Connected! Found {test_foods.count} items in your 'foods' table.")
    except Exception as e:
        st.error(f"❌ Connection Error: {e}")

# --- PART 1: THE DASHBOARD ---
try:
    response = supabase.table("daily_variance").select("*").execute()
    if response.data:
        latest = response.data[0]
        st.subheader(f"Status for {latest['date']}")

        cal_budget = latest["calorie_variance"] * -1
        prot_budget = latest["protein_variance"] * -1
        carb_budget = latest["carbs_variance"] * -1

        col1, col2, col3 = st.columns(3)
        col1.metric(
            "Calories Eaten", f"{latest['total_calories']}", f"{cal_budget} Remaining"
        )
        col2.metric(
            "Protein (g)", f"{latest['total_protein']}", f"{prot_budget} Remaining"
        )
        col3.metric("Carbs (g)", f"{latest['total_carbs']}", f"{carb_budget} Remaining")
except Exception as e:
    st.info("Waiting for dashboard data...")

st.divider()

# --- PART 2: THE DROPDOWN ---
st.subheader("🍴 Quick Log Meal")

try:
    # We fetch the food list
    food_query = supabase.table("foods").select("id, food_name").execute()

    if food_query.data:
        food_options = {f["food_name"]: f["id"] for f in food_query.data}

        with st.form("meal_form", clear_on_submit=True):
            selected_food = st.selectbox(
                "Select Food", options=list(food_options.keys())
            )
            servings = st.number_input("Servings", min_value=0.1, value=1.0)
            submit = st.form_submit_button("Add to Diary")

            if submit:
                new_log = {
                    "food_id": food_options[selected_food],
                    "servings": servings,
                    "log_date": str(latest["date"])
                    if "latest" in locals()
                    else "2026-02-26",
                }
                supabase.table("daily_logs").insert(new_log).execute()
                st.success("Logged!")
                st.rerun()
    else:
        st.warning("No foods found in your 'foods' table. Add some in Supabase first!")

except Exception as e:
    st.error(f"Dropdown Error: {e}")
