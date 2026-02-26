import streamlit as st
from supabase import create_client

# 1. Connect to your Supabase
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)
# Add this right below it to "poke" the connection:
st.sidebar.write("Connected to:", url.split("//")[1].split(".")[0])

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
# --- PART 2: THE DROPDOWN (Manual Override) ---
st.subheader("🍴 Quick Log Meal")

try:
    # 1. Fetch the data
    food_query = supabase.table("foods").select("*").execute()

    if food_query.data:
        # --- DATA INSPECTOR (Temporary) ---
        # This will show you exactly what column names Supabase is sending back
        first_row = food_query.data[0]
        st.write("🔍 Database Inspector - I see these columns:", list(first_row.keys()))

        # 2. Map the columns (Change 'food_name' or 'food_id' if the inspector shows different names)
        # For example, if it says ['ID', 'Name'], change the words below to match.
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
                    "log_date": "2026-02-26",
                }
                supabase.table("daily_logs").insert(new_log).execute()
                st.success(f"Logged {selected_food}!")
                st.rerun()
    else:
        st.warning(
            "Your 'foods' table returned 0 rows. Please double-check that you have saved at least one row in the Supabase Table Editor."
        )

except Exception as e:
    st.error(f"Connection Error: {e}")
