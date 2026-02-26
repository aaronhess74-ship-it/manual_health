import streamlit as st
from supabase import create_client

# 1. Connect to your Supabase
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.title("💪 My Health Budget")

# --- PART 1: THE DASHBOARD ---
try:
    response = supabase.table("daily_variance").select("*").execute()
    if response.data:
        latest = response.data[0]
        st.subheader(f"Status for {latest['date']}")

        # Budget math
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
    st.info("Log a meal below to start your daily dashboard!")

st.divider()

# --- PART 2: THE DROPDOWN (Manual Fix) ---
st.subheader("🍴 Quick Log Meal")

try:
    # We fetch ALL columns to avoid naming errors
    food_query = supabase.table("foods").select("*").execute()

    if food_query.data:
        # HARD-CODED NAMES: Changing 'id' to 'food_id' and 'food_name' to whatever you used
        # If your column is 'Name', change 'food_name' to 'Name' below:
        food_options = {f["food_name"]: f["food_id"] for f in food_query.data}

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
                    "log_date": "2026-02-26",  # Hardcoded for testing, we can automate later
                }
                supabase.table("daily_logs").insert(new_log).execute()
                st.success(f"Successfully logged {selected_food}!")
                st.rerun()
    else:
        st.warning(
            "Your 'foods' table is empty. Add a row in Supabase with columns: food_id and food_name."
        )

except Exception as e:
    # This will show us the EXACT column names if it fails again
    st.error(f"Error: {e}")
    if "food_query" in locals() and food_query.data:
        st.write("Your actual columns are:", list(food_query.data[0].keys()))
