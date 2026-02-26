import streamlit as st
from supabase import create_client

# 1. Connect to your Supabase
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.title("💪 My Health Dashboard")

# 2. Fetch data from your 'daily_variance' view
try:
    response = supabase.table("daily_variance").select("*").execute()
    data = response.data

    if data:
        st.subheader("Today's Variance")
        # Show the most recent entry
        latest = data[0]

        col1, col2, col3 = st.columns(3)
        col1.metric(
            "Calories",
            f"{latest['total_calories']}",
            f"{latest['calorie_variance']} vs Goal",
        )
        col2.metric(
            "Protein", f"{latest['total_protein']}g", f"{latest['protein_variance']}g"
        )
        col3.metric(
            "Carbs", f"{latest['total_carbs']}g", f"{latest['carbs_variance']}g"
        )

        st.write("### Full History")
        st.table(data)
    else:
        st.info("No data found for today. Go to Supabase and add a log!")

except Exception as e:
    st.error(f"Error connecting to Supabase: {e}")
