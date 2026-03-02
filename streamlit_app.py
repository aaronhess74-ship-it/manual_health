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
TARGET_CALORIES = 1800
TARGET_PROTEIN = 160
TARGET_FAT_MAX = 60
TARGET_NET_CARBS = 60
TARGET_FIBER_MIN = 30

# --- TAB 1: NUTRITION ---
tab1, tab2, tab3, tab4 = st.tabs(
    ["🍴 Nutrition", "🩺 Health Metrics", "🏃 Activity", "📊 Reports & Exports"]
)

with tab1:
    try:
        # Based on schema: daily_variance uses 'date'
        response = (
            supabase.table("daily_variance")
            .select("*")
            .order("date", desc=True)
            .limit(1)
            .execute()
        )
        if response.data:
            latest = response.data[0]
            st.subheader(f"Status for {latest['date']}")
            c1, c2, c3, c4, c5 = st.columns(5)

            cals = float(latest.get("total_calories", 0))
            prot = float(latest.get("total_protein", 0))
            net_c = float(latest.get("total_net_carbs", 0))

            def get_status_icon(curr, target, is_ceiling=True):
                if is_ceiling:
                    return "🔴 OVER" if curr > target else "🟢 OK"
                return "🟢 GOAL" if curr >= target else "🔴 LOW"

            c1.metric(
                f"Calories {get_status_icon(cals, TARGET_CALORIES)}",
                f"{int(cals)}",
                f"{int(TARGET_CALORIES - cals)} Left",
            )
            c2.metric(
                f"Protein {get_status_icon(prot, TARGET_PROTEIN, False)}",
                f"{int(prot)}g",
                f"{int(prot - TARGET_PROTEIN)} vs Target",
            )
            c3.metric(
                f"Net Carbs {get_status_icon(net_c, TARGET_NET_CARBS)}",
                f"{int(net_c)}g",
                f"{int(TARGET_NET_CARBS - net_c)} Left",
            )
            c4.metric("Total Fat", f"{int(latest.get('total_fat', 0))}g")
            c5.metric("Fiber", f"{int(latest.get('total_fiber', 0))}g")
    except Exception as e:
        st.error(f"Nutrition Error: {e}")

    st.divider()
    st.subheader("⚡ Quick Log")
    try:
        # daily_logs uses log_date
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
                if cols[i].button(f"➕ {r['foods']['food_name']}", key=f"q_{i}"):
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

    st.divider()
    st.subheader("🍴 Log Meal")
    f_query = supabase.table("foods").select("*").order("food_name").execute()
    if f_query.data:
        f_dict = {f["food_name"]: f for f in f_query.data}
        sel = st.selectbox(
            "Search Food Library...", options=list(f_dict.keys()), index=None
        )
        if sel:
            srv = st.number_input("Servings", 1.0)
            if st.button("Log Food"):
                supabase.table("daily_logs").insert(
                    {
                        "food_id": f_dict[sel]["food_id"],
                        "servings": srv,
                        "log_date": str(datetime.now().date()),
                    }
                ).execute()
                st.rerun()

# --- TAB 2: HEALTH METRICS ---
with tab2:
    try:
        # Based on schema: health_metrics uses 'date'
        res = (
            supabase.table("health_metrics")
            .select("*")
            .order("date", desc=False)
            .execute()
        )
        if res.data:
            df_h = pd.DataFrame(res.data)
            df_h["ts"] = pd.to_datetime(
                df_h["date"].astype(str)
                + " "
                + df_h["time"].fillna("00:00:00").astype(str)
            )

            st.subheader("📊 Weight Trend")
            chart = (
                alt.Chart(df_h)
                .mark_line(point=True)
                .encode(x="ts:T", y="weight_lb:Q")
                .properties(height=300)
            )
            st.altair_chart(chart, use_container_width=True)

            st.subheader("➕ Add Entry")
            with st.form("h_form"):
                w = st.number_input("Weight (lbs)", 0.0)
                sys = st.number_input("Systolic", 0)
                dia = st.number_input("Diastolic", 0)
                glu = st.number_input("Glucose", 0.0)
                if st.form_submit_button("Save Metric"):
                    supabase.table("health_metrics").insert(
                        {
                            "date": str(datetime.now().date()),
                            "time": datetime.now().strftime("%H:%M:%S"),
                            "weight_lb": w,
                            "blood_pressure_systolic": sys,
                            "blood_pressure_diastolic": dia,
                            "blood_glucose": glu,
                        }
                    ).execute()
                    st.rerun()
    except Exception as e:
        st.error(f"Health Error: {e}")

# --- TAB 3: ACTIVITY ---
with tab3:
    st.subheader("🏃 Log Activity")
    with st.form("act_form"):
        name = st.text_input("Exercise Name")
        cat = st.selectbox("Category", ["Strength", "Cardio", "Endurance"])
        c1, c2 = st.columns(2)
        s = c1.number_input("Sets", 0)
        r = c2.number_input("Reps", 0)
        w = c1.number_input("Weight (lbs)", 0)
        dur = c2.number_input("Duration (min)", 0.0)
        if st.form_submit_button("Log Activity"):
            # Based on schema: activity_logs uses 'log_date'
            supabase.table("activity_logs").insert(
                {
                    "log_date": str(datetime.now().date()),
                    "exercise_name": name,
                    "activity_category": cat,
                    "sets": s,
                    "reps": r,
                    "weight_lbs": w,
                    "duration_min": dur,
                }
            ).execute()
            st.rerun()

    st.divider()
    st.subheader("📜 History")
    try:
        # activity_logs uses log_date
        a_res = (
            supabase.table("activity_logs")
            .select("*")
            .order("log_date", desc=True)
            .execute()
        )
        if a_res.data:
            st.dataframe(pd.DataFrame(a_res.data), use_container_width=True)
    except Exception as e:
        st.error(f"Activity History Error: {e}")

# --- TAB 4: REPORTS ---
with tab4:
    st.subheader("📊 Viewer")
    t_choice = st.selectbox(
        "Table",
        ["daily_variance", "health_metrics", "activity_logs", "detailed_health_trends"],
    )

    # Map the correct date column for sorting based on your schema
    sort_map = {
        "daily_variance": "date",
        "health_metrics": "date",
        "activity_logs": "log_date",
        "detailed_health_trends": "date",
    }

    try:
        s_col = sort_map.get(t_choice, "created_at")
        res = (
            supabase.table(t_choice)
            .select("*")
            .order(s_col, desc=True)
            .limit(50)
            .execute()
        )
        if res.data:
            st.dataframe(pd.DataFrame(res.data), use_container_width=True)
    except Exception as e:
        st.error(f"Viewer Error: {e}")
