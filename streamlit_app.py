import streamlit as st
from supabase import create_client

# 1. Setup Connection
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
        col1, col2, col3 = st.columns(3)

        # Budget math (multiply by -1 so 'under' is a positive remaining balance)
        cal_remain = latest["calorie_variance"] * -1
        prot_remain = latest["protein_variance"] * -1
        carb_remain = latest["carbs_variance"] * -1

        col1.metric("Calories", f"{latest['total_calories']}", f"{cal_remain} Left")
        col2.metric("Protein", f"{latest['total_protein']}g", f"{prot_remain} Left")
        col3.metric("Carbs", f"{latest['total_carbs']}g", f"{carb_remain} Left")
except Exception as e:
    st.info("Log a meal below to see your daily totals!")

st.divider()

# --- PART 2: LOG A MEAL (With Adjustable Servings) ---
st.subheader("🍴 Log a Meal")

try:
    food_query = supabase.table("food_name").select("*").execute()
    if food_query.data:
        # Create a dictionary to store food info
        food_dict = {f["name"]: f for f in food_query.data}

        with st.form("log_form"):
            selected_name = st.selectbox("Select Food", options=list(food_dict.keys()))
            servings = st.number_input("Servings", min_value=0.1, value=1.0, step=0.1)

            submit_log = st.form_submit_button("Add to Diary")

            if submit_log:
                food = food_dict[selected_name]
                new_log = {
                    "food_id": food["food_id"],
                    "servings": servings,
                    "log_date": "2026-02-26",  # We can make this dynamic later
                }
                supabase.table("daily_logs").insert(new_log).execute()
                st.success(f"Logged {servings}x {selected_name}!")
                st.rerun()
    else:
        st.warning("Your food library is empty. Add a food below first.")
except Exception as e:
    st.error(f"Logging Error: {e}")

st.divider()

# --- PART 3: FOOD LIBRARY BUILDER ---
with st.expander("➕ Add New Food to Library"):
    with st.form("new_food_form", clear_on_submit=True):
        f_name = st.text_input("Food Name (e.g. Almond Milk)")
        f_brand = st.text_input("Brand (Optional)")
        f_size = st.text_input("Serving Size (e.g. 1 cup)")

        c1, c2, c3 = st.columns(3)
        f_cal = c1.number_input("Calories", min_value=0)
        f_prot = c2.number_input("Protein (g)", min_value=0)
        f_carb = c3.number_input("Carbs (g)", min_value=0)

        f_fat = st.number_input("Fat (g)", min_value=0)

        submit_food = st.form_submit_button("Save to Library")

        if submit_food and f_name:
            new_food = {
                "name": f_name,
                "brand": f_brand,
                "serving_size": f_size,
                "calories": f_cal,
                "protein_g": f_prot,
                "carbs_g": f_carb,
                "fat_g": f_fat,
            }
            try:
                supabase.table("food_name").insert(new_food).execute()
                st.success(f"Added {f_name} to your library!")
                st.rerun()
            except Exception as e:
                st.error(f"Could not save food: {e}")
