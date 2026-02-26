import streamlit as st
from supabase import create_client

# 1. Connect to your Supabase
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.title("💪 My Health Budget")

# --- PART 1: THE DASHBOARD ---
try:
    # Fetch the view we made
    response = supabase.table("daily_variance").select("*").execute()
    data = response.data

    if data:
        latest = data[0]
        st.subheader(f"Status for {latest['date']}")

        # Flip the math: If variance is -1680, it means we have 1680 LEFT to eat.
        # We multiply by -1 so that 'under' looks like a positive 'budget'
        cal_budget = latest["calorie_variance"] * -1
        prot_budget = latest["protein_variance"] * -1
        carb_budget = latest["carbs_variance"] * -1

        col1, col2, col3 = st.columns(3)

        # 'Normal' delta shows green for up, red for down.
        # For calories, 'inverse' makes it green if we are under our limit.
        col1.metric(
            "Calories Eaten",
            f"{latest['total_calories']}",
            f"{cal_budget} Remaining",
            delta_color="normal",
        )
        col2.metric(
            "Protein (g)", f"{latest['total_protein']}", f"{prot_budget} Remaining"
        )
        col3.metric("Carbs (g)", f"{latest['total_carbs']}", f"{carb_budget} Remaining")

    else:
        st.info("No logs for today yet!")

except Exception as e:
    st.error(f"Display Error: {e}")

st.divider()

# --- PART 2: LOG A MEAL (The Input) ---
st.subheader("🍴 Quick Log Meal")

with st.form("meal_form", clear_on_submit=True):
    # Get food list from your 'foods' table for the dropdown
    food_query = supabase.table("foods").select("id, food_name").execute()
    food_options = {f["food_name"]: f["id"] for f in food_query.data}

    selected_food = st.selectbox("Select Food", options=list(food_options.keys()))
    servings = st.number_input("How many servings?", min_value=0.1, value=1.0, step=0.1)

    submit_button = st.form_submit_button("Add to Diary")

    if submit_button:
        # Save to your 'daily_logs' table
        new_log = {
            "food_id": food_options[selected_food],
            "servings": servings,
            "log_date": str(latest["date"]),  # Logs to current day shown above
        }

        result = supabase.table("daily_logs").insert(new_log).execute()
        if result:
            st.success(f"Added {servings}x {selected_food}!")
            st.rerun()  # Refresh the page to show new totals
