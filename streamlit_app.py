import streamlit as st
from supabase import create_client
from datetime import datetime, timedelta
import pandas as pd

# 1. Setup Connection
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.set_page_config(page_title="My Health Dashboard", layout="wide")
st.title("💪 My Health Dashboard")

# Manual Targets
TARGET_CALORIES = 2000
TARGET_PROTEIN = 150
TARGET_CARBS = 250

# Color Constants
COLOR_NORMAL = "#2ecc71"  # Green
COLOR_WARNING = "#f1c40f"  # Amber
COLOR_DANGER = "#e74c3c"  # Red
COLOR_DIAB = "#9b59b6"  # Purple (for Glucose High)

tab1, tab2 = st.tabs(["🍴 Nutrition Budget", "🩺 Health Metrics"])

# --- TAB 1: NUTRITION BUDGET ---
with tab1:
    try:
        response = supabase.table("daily_variance").select("*").execute()
        if response.data:
            latest = response.data[0]
            st.subheader(f"Status for {latest['date']}")
            c1, c2, c3 = st.columns(3)
            c1.metric(
                "Calories",
                f"{latest['total_calories']}",
                f"{TARGET_CALORIES - latest['total_calories']} Left",
            )
            c2.metric(
                "Protein",
                f"{latest['total_protein']}g",
                f"{TARGET_PROTEIN - latest['total_protein']}g Left",
            )
            c3.metric(
                "Carbs",
                f"{latest['total_carbs']}g",
                f"{TARGET_CARBS - latest['total_carbs']}g Left",
            )
    except:
        st.info("Log a meal below to see today's nutrition status.")

    st.divider()
    st.subheader("🍴 Log a Meal")
    try:
        food_query = supabase.table("foods").select("*").execute()
        if food_query.data:
            food_dict = {f["food_name"]: f for f in food_query.data}
            with st.form("log_form"):
                selected_name = st.selectbox(
                    "Select Food", options=list(food_dict.keys())
                )
                servings = st.number_input(
                    "Servings", min_value=0.1, value=1.0, step=0.1
                )
                if st.form_submit_button("Add to Diary"):
                    food_record = food_dict[selected_name]
                    new_log = {
                        "food_id": food_record["food_id"],
                        "servings": servings,
                        "log_date": str(datetime.now().date()),
                    }
                    supabase.table("daily_logs").insert(new_log).execute()
                    st.rerun()
    except Exception:
        pass

    st.divider()
    st.subheader("📜 Today's Log History")
    try:
        history_res = (
            supabase.table("daily_logs")
            .select("log_id, servings, log_date, foods(food_name, calories)")
            .eq("log_date", str(datetime.now().date()))
            .execute()
        )
        if history_res.data:
            for item in history_res.data:
                col1, col2, col3 = st.columns([3, 1, 1])
                col1.write(
                    f"**{item['foods']['food_name']}** ({item['servings']} servings)"
                )
                col2.write(f"{int(item['foods']['calories'] * item['servings'])} cal")
                if col3.button("🗑️", key=f"del_{item['log_id']}"):
                    supabase.table("daily_logs").delete().eq(
                        "log_id", item["log_id"]
                    ).execute()
                    st.rerun()
    except Exception:
        pass

# --- TAB 2: HEALTH METRICS ---
with tab2:
    # Default Trend Colors
    bp_line_color = COLOR_NORMAL
    glu_line_color = COLOR_NORMAL

    st.subheader("🏷️ Latest Vitals Status")
    try:
        last_res = (
            supabase.table("health_metrics")
            .select("*")
            .order("date", desc=True)
            .order("time", desc=True)
            .limit(1)
            .execute()
        )
        if last_res.data:
            v = last_res.data[0]
            s, d, g = (
                int(v["blood_pressure_systolic"]),
                int(v["blood_pressure_diastolic"]),
                int(v["blood_glucose"]),
            )

            # BP Logic & Line Color
            if s < 120 and d < 80:
                bp_status, bp_line_color = "🟢 Normal", COLOR_NORMAL
            elif 120 <= s < 130 and d < 80:
                bp_status, bp_line_color = "🟡 Elevated", COLOR_WARNING
            else:
                bp_status, bp_line_color = "🔴 Hypertension", COLOR_DANGER

            # Glucose Logic & Line Color
            if g < 100:
                g_status, glu_line_color = "🟢 Normal", COLOR_NORMAL
            elif 100 <= g < 126:
                g_status, glu_line_color = "🟡 Pre-diabetes", COLOR_WARNING
            else:
                g_status, glu_line_color = "🔴 High", COLOR_DIAB

            m1, m2, m3 = st.columns(3)
            with m1:
                st.metric("Blood Pressure", f"{s}/{d}")
                st.markdown(f"**Status:** {bp_status}")
            with m2:
                st.metric("Glucose", f"{g} mg/dL")
                st.markdown(f"**Status:** {g_status}")
            with m3:
                st.metric("Weight", f"{v['weight_lb']} lbs")
    except Exception:
        pass

    st.divider()
    with st.expander("🩺 Log New Vitals & Weight"):
        with st.form("vitals_form", clear_on_submit=True):
            col_d, col_t = st.columns(2)
            m_date = col_d.date_input("Date", value=datetime.now().date())
            m_time = col_t.time_input("Time", value=datetime.now().time())
            c1, c2, c3 = st.columns(3)
            sys = c1.number_input("Systolic", min_value=50, max_value=250, value=120)
            dia = c2.number_input("Diastolic", min_value=30, max_value=150, value=80)
            weight = c3.number_input(
                "Weight (lbs)", min_value=0.0, max_value=500.0, step=0.1
            )
            glucose = st.number_input(
                "Blood Glucose (mg/dL)", min_value=0, max_value=600, value=100
            )
            if st.form_submit_button("Save Metrics"):
                new_metric = {
                    "date": str(m_date),
                    "time": str(m_time),
                    "blood_pressure_systolic": sys,
                    "blood_pressure_diastolic": dia,
                    "blood_glucose": glucose,
                    "weight_lb": weight,
                }
                supabase.table("health_metrics").insert(new_metric).execute()
                st.rerun()

    st.divider()
    st.subheader("📈 Health Trends")
    time_view = st.radio("View Range:", ["7 Days", "30 Days", "Year"], horizontal=True)
    today = datetime.now().date()
    cutoff = today - timedelta(
        days=7 if time_view == "7 Days" else (30 if time_view == "30 Days" else 365)
    )

    try:
        res = (
            supabase.table("health_metrics")
            .select("*")
            .gte("date", cutoff.isoformat())
            .order("date", desc=False)
            .order("time", desc=False)
            .execute()
        )
        if res.data:
            df = pd.DataFrame(res.data)
            metrics = [
                "blood_pressure_systolic",
                "blood_pressure_diastolic",
                "blood_glucose",
                "weight_lb",
            ]
            for m in metrics:
                df[m] = pd.to_numeric(df[m], errors="coerce")

            st.write("#### Blood Pressure")
            # Multiple lines (Systolic/Diastolic) use a list of colors
            st.line_chart(
                df,
                x="date",
                y=["blood_pressure_systolic", "blood_pressure_diastolic"],
                color=[bp_line_color, "#5dade2"],
            )

            weight_df = df[df["weight_lb"] > 0]
            if not weight_df.empty:
                st.write("#### Weight (lbs)")
                st.line_chart(weight_df, x="date", y="weight_lb", color="#af7ac5")

            st.write("#### Blood Glucose")
            st.line_chart(df, x="date", y="blood_glucose", color=glu_line_color)

            # --- STEP 3: EXPORT BUTTON ---
            st.divider()
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Download Health Data (CSV)",
                data=csv,
                file_name=f"health_data_{datetime.now().strftime('%Y-%m-%d')}.csv",
                mime="text/csv",
            )
    except Exception as e:
        st.error(f"Chart Error: {e}")
