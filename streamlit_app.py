import streamlit as st
from supabase import create_client
from datetime import datetime
import pandas as pd

# 1. Connection
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.set_page_config(page_title="Health Dashboard Pro", layout="wide")
st.title("💪 My Health Dashboard")

tab1, tab2, tab3, tab4 = st.tabs(
    ["🍴 Nutrition", "🩺 Health Metrics", "🏃 Activity", "📊 Reports & Exports"]
)

# --- TAB 1: NUTRITION (Unchanged) ---
with tab1:
    st.subheader("Daily Nutrition")
    try:
        res = supabase.table("daily_variance").select("*").limit(1).execute()
        if res.data:
            st.write(f"Latest Log: {res.data[0].get('date')}")
            st.json(res.data[0])
    except Exception as e:
        st.error(f"Nutrition Error: {e}")

# --- TAB 2: HEALTH METRICS (Unchanged) ---
with tab2:
    st.subheader("Vitals")
    try:
        h_res = (
            supabase.table("health_metrics")
            .select("*")
            .order("date", desc=True)
            .limit(5)
            .execute()
        )
        if h_res.data:
            st.table(pd.DataFrame(h_res.data))
    except Exception as e:
        st.error(f"Health Error: {e}")

# --- TAB 3: ACTIVITY (The fix for Line 322) ---
with tab3:
    st.subheader("🏃 Log Activity")
    act_cat = st.radio("Category", ["Strength", "Cardio", "Endurance"], horizontal=True)

    with st.form("act_form", clear_on_submit=True):
        a_date = st.date_input("Date", datetime.now().date())
        name = st.text_input("Exercise Name")
        c1, c2, c3 = st.columns(3)
        dur, dist, s, r, w = 0.0, 0.0, 0, 0, 0

        if act_cat == "Strength":
            s = c1.number_input("Sets", 0, 100, 3)
            r = c2.number_input("Reps", 0, 100, 10)
            w = c3.number_input("Weight (lbs)", 0, 1000, 0)
        elif act_choice := "Cardio":
            dur = c1.number_input("Duration (min)", 0.0, 500.0, 30.0)
            dist = c2.number_input("Distance (mi)", 0.0, 100.0, 0.0)

        if st.form_submit_button("Log Activity"):
            if name:
                # Matches your schema: date, exercise_name, activity_category, duration_min, sets, reps, distance_miles
                supabase.table("activity_logs").insert(
                    {
                        "date": str(a_date),
                        "exercise_name": name,
                        "activity_category": act_cat,
                        "duration_min": dur,
                        "distance_miles": dist,
                        "sets": s,
                        "reps": r,
                    }
                ).execute()
                st.rerun()

    st.divider()
    st.subheader("📜 Activity History")
    try:
        # This is where Line 322 was. Added a generic select to prevent column-missing crashes.
        a_res = supabase.table("activity_logs").select("*").execute()
        if a_res.data:
            st.dataframe(pd.DataFrame(a_res.data))
    except Exception as e:
        st.error(f"Activity Table Error: {e}")

# --- TAB 4: REPORTS & EXPORTS ---
with tab4:
    st.subheader("📂 Master Export")
    if st.button("🚀 Export Everything"):
        try:
            # Simple fetch from all 3 sources
            n = (
                supabase.table("daily_logs")
                .select("log_date, foods(food_name, calories)")
                .execute()
            )
            h = supabase.table("health_metrics").select("*").execute()
            a = supabase.table("activity_logs").select("*").execute()

            master = []
            for i in n.data:
                if i.get("foods"):
                    master.append(
                        {
                            "date": i["log_date"],
                            "type": "Food",
                            "label": i["foods"]["food_name"],
                            "val": i["foods"]["calories"],
                        }
                    )
            for i in h.data:
                if i.get("weight_lb"):
                    master.append(
                        {
                            "date": i["date"],
                            "type": "Weight",
                            "label": "Weight",
                            "val": i["weight_lb"],
                        }
                    )
            for i in a.data:
                master.append(
                    {
                        "date": i["date"],
                        "type": "Activity",
                        "label": i.get("exercise_name"),
                        "val": i.get("duration_min"),
                    }
                )

            if master:
                df = pd.DataFrame(master)
                st.download_button(
                    "Download CSV",
                    df.to_csv(index=False).encode("utf-8"),
                    "health_master.csv",
                )
                st.dataframe(df.head(10))
        except Exception as e:
            st.error(f"Export Error: {e}")
