import streamlit as st
from supabase import create_client
from datetime import datetime
import pandas as pd
import altair as alt

# 1. Setup Connection
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.set_page_config(page_title="Health Dashboard Pro", layout="wide")
st.title("💪 My Health Dashboard")

# --- TARGET CONSTANTS ---
TARGET_CALORIES, TARGET_PROTEIN, TARGET_FAT_MAX = 1800, 160, 60
TARGET_NET_CARBS, TARGET_FIBER_MIN, TARGET_WEIGHT = 60, 30, 180

tab1, tab2, tab3, tab4 = st.tabs(
    ["🍴 Nutrition", "🩺 Health Metrics", "🏃 Activity", "📊 Reports"]
)

# --- TAB 1: NUTRITION ---
with tab1:
    try:
        # We fetch without ordering to prevent the 'date' vs 'log_date' sort error
        response = supabase.table("daily_variance").select("*").execute()
        if response.data:
            df_var = pd.DataFrame(response.data)
            # Try to find a date column for the header
            date_col = next(
                (c for c in ["log_date", "date"] if c in df_var.columns), None
            )
            latest = df_var.iloc[0]
            st.subheader(f"Status for {latest.get(date_col, 'Today')}")

            c1, c2, c3, c4, c5 = st.columns(5)
            cals, prot = (
                float(latest.get("total_calories", 0)),
                float(latest.get("total_protein", 0)),
            )
            net_c, fat, fib = (
                float(latest.get("total_net_carbs", 0)),
                float(latest.get("total_fat", 0)),
                float(latest.get("total_fiber", 0)),
            )

            def get_status(curr, target, ceil=True):
                if ceil:
                    return "🔴" if curr > target else "🟢"
                return "🟢" if curr >= target else "🔴"

            c1.metric(f"Calories {get_status(cals, TARGET_CALORIES)}", f"{int(cals)}")
            c2.metric(
                f"Protein {get_status(prot, TARGET_PROTEIN, False)}", f"{int(prot)}g"
            )
            c3.metric(
                f"Net Carbs {get_status(net_c, TARGET_NET_CARBS)}", f"{int(net_c)}g"
            )
            c4.metric(f"Total Fat {get_status(fat, TARGET_FAT_MAX)}", f"{int(fat)}g")
            c5.metric(
                f"Fiber {get_status(fib, TARGET_FIBER_MIN, False)}", f"{int(fib)}g"
            )
    except Exception as e:
        st.error(f"Nutrition Tab Error: {e}")

    st.divider()
    st.subheader("⚡ Quick Log")
    try:
        # Sort by log_id is always safe as it's the Primary Key
        r_res = (
            supabase.table("daily_logs")
            .select("food_id, foods(food_name)")
            .order("log_id", desc=True)
            .limit(5)
            .execute()
        )
        if r_res.data:
            cols = st.columns(len(r_res.data))
            for i, r in enumerate(r_res.data):
                if cols[i].button(f"➕ {r['foods']['food_name']}"):
                    supabase.table("daily_logs").insert(
                        {
                            "food_id": r["food_id"],
                            "servings": 1.0,
                            "log_date": str(datetime.now().date()),
                        }
                    ).execute()
                    st.rerun()
    except:
        pass

# --- TAB 2: HEALTH METRICS ---
with tab2:
    st.subheader("🩺 Health Vitals")
    try:
        # Fetch raw data - sorting in Python to avoid Postgrest errors
        h_res = supabase.table("health_metrics").select("*").execute()
        if h_res.data:
            df_h = pd.DataFrame(h_res.data)
            # Identify which date column we have
            h_date_col = "log_date" if "log_date" in df_h.columns else "date"
            df_h["sort_ts"] = pd.to_datetime(
                df_h[h_date_col].astype(str) + " " + df_h["time"].fillna("00:00:00")
            )
            df_h = df_h.sort_values("sort_ts", ascending=False)

            m1, m2 = st.columns(2)
            latest_w = (
                df_h.dropna(subset=["weight_lb"]).iloc[0]
                if not df_h.dropna(subset=["weight_lb"]).empty
                else None
            )
            if latest_w is not None:
                m1.metric("Latest Weight", f"{latest_w['weight_lb']} lbs")

            st.altair_chart(
                alt.Chart(df_h)
                .mark_line(point=True)
                .encode(x="sort_ts:T", y="weight_lb:Q"),
                use_container_width=True,
            )

        with st.expander("➕ Add New Metric"):
            with st.form("health_form"):
                new_w = st.number_input("Weight", 0.0)
                new_date = st.date_input("Date", datetime.now().date())
                if st.form_submit_button("Save"):
                    # We send to log_date as requested
                    supabase.table("health_metrics").insert(
                        {
                            "weight_lb": new_w,
                            "log_date": str(new_date),
                            "time": datetime.now().strftime("%H:%M:%S"),
                        }
                    ).execute()
                    st.rerun()
    except Exception as e:
        st.error(f"Health Tab Error: {e}")

# --- TAB 3: ACTIVITY (The Surgery) ---
with tab3:
    st.subheader("🏃 Activity Logging")
    with st.form("act_form"):
        act_name = st.text_input("Exercise Name")
        act_cat = st.selectbox("Category", ["Strength", "Cardio", "Endurance"])
        c1, c2 = st.columns(2)
        sets = c1.number_input("Sets", 0)
        reps = c2.number_input("Reps", 0)
        weight = c1.number_input("Weight (lbs)", 0)
        mins = c2.number_input("Duration (mins)", 0)
        act_date = st.date_input("Date", datetime.now().date())

        if st.form_submit_button("Log Activity"):
            if act_name:
                supabase.table("activity_logs").insert(
                    {
                        "exercise_name": act_name,
                        "activity_category": act_cat,
                        "sets": sets,
                        "reps": reps,
                        "weight_lbs": weight,
                        "duration_min": mins,
                        "log_date": str(act_date),  # Using log_date
                    }
                ).execute()
                st.rerun()

    st.divider()
    try:
        # Fetching without .order() to stop the crashing. We sort in Pandas.
        a_res = supabase.table("activity_logs").select("*").execute()
        if a_res.data:
            df_a = pd.DataFrame(a_res.data)
            # Find the actual date column name in the returned data
            actual_col = "log_date" if "log_date" in df_a.columns else "date"
            df_a = df_a.sort_values(actual_col, ascending=False)
            st.dataframe(df_a, use_container_width=True)
    except Exception as e:
        st.error(f"Activity History Error: {e}")

# --- TAB 4: REPORTS ---
with tab4:
    st.subheader("📊 Data Export")
    target_table = st.selectbox(
        "Select Table", ["activity_logs", "health_metrics", "daily_logs"]
    )
    if st.button("Download CSV"):
        res = supabase.table(target_table).select("*").execute()
        if res.data:
            csv = pd.DataFrame(res.data).to_csv(index=False)
            st.download_button(
                "Click to Download", csv, f"{target_table}.csv", "text/csv"
            )
