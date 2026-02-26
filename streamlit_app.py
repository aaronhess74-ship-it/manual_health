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
COLOR_NORMAL = "#2ecc71"
COLOR_WARNING = "#f1c40f"
COLOR_DANGER = "#e74c3c"

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
    except Exception:
        st.info("Log a meal below to see today's status.")

    st.divider()

    # NEW: MEAL QUICK-ADD
    st.subheader("⚡ Quick Log (Frequent Foods)")
    try:
        # Fetch top 5 most frequent foods from logs
        freq_res = supabase.rpc(
            "get_frequent_foods"
        ).execute()  # Requires a small SQL function
        # Fallback: Just grab the first 3 from the foods table if RPC isn't setup
        if not freq_res.data:
            freq_res = supabase.table("foods").select("*").limit(3).execute()

        if freq_res.data:
            cols = st.columns(len(freq_res.data))
            for idx, food in enumerate(freq_res.data):
                if cols[idx].button(
                    f"➕ {food['food_name']}", use_container_width=True
                ):
                    new_log = {
                        "food_id": food["food_id"],
                        "servings": 1.0,
                        "log_date": str(datetime.now().date()),
                    }
                    supabase.table("daily_logs").insert(new_log).execute()
                    st.toast(f"Logged 1 serving of {food['food_name']}!")
                    st.rerun()
    except Exception:
        st.write("Log a few meals to see quick-add buttons here.")

    with st.expander("🍴 Manual Log"):
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
            .select("log_id, servings, foods(food_name, calories)")
            .eq("log_date", str(datetime.now().date()))
            .execute()
        )
        if history_res.data:
            for item in history_res.data:
                col1, col2, col3 = st.columns([3, 1, 1])
                col1.write(f"**{item['foods']['food_name']}**")
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
    bp_line_color, glu_line_color, wgt_line_color = (
        COLOR_NORMAL,
        COLOR_NORMAL,
        COLOR_NORMAL,
    )

    # 1. CLINICAL WARNINGS & LATEST STATUS
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
            s, d, g, w = (
                int(v["blood_pressure_systolic"]),
                int(v["blood_pressure_diastolic"]),
                int(v["blood_glucose"]),
                float(v["weight_lb"]),
            )

            # Logic for Status & Line Colors
            if s < 120 and d < 80:
                bp_status, bp_line_color = "🟢 Normal", COLOR_NORMAL
            elif 120 <= s < 130 and d < 80:
                bp_status, bp_line_color = "🟡 Elevated", COLOR_WARNING
            else:
                bp_status, bp_line_color = "🔴 Hypertension", COLOR_DANGER

            if g < 100:
                g_status, glu_line_color = "🟢 Normal", COLOR_NORMAL
            elif 100 <= g < 126:
                g_status, glu_line_color = "🟡 Pre-diabetes", COLOR_WARNING
            else:
                g_status, glu_line_color = "🔴 High", COLOR_DANGER

            if 155 <= w <= 179:
                w_status, wgt_line_color = "🟢 Goal Range", COLOR_NORMAL
            elif 180 <= w <= 200:
                w_status, wgt_line_color = "🟡 Warning Range", COLOR_WARNING
            else:
                w_status, wgt_line_color = "🔴 Above Range", COLOR_DANGER

            # NEW: SMART WARNING BOX
            if bp_line_color == COLOR_DANGER or glu_line_color == COLOR_DANGER:
                st.warning(
                    f"⚠️ **Attention Required:** Your latest {'Blood Pressure' if bp_line_color == COLOR_DANGER else ''} {'and' if (bp_line_color == COLOR_DANGER and glu_line_color == COLOR_DANGER) else ''} {'Glucose' if glu_line_color == COLOR_DANGER else ''} is currently in the High zone. Consider resting and re-checking."
                )

            st.subheader("🏷️ Latest Vitals Status")
            m1, m2, m3 = st.columns(3)
            with m1:
                st.metric("Blood Pressure", f"{s}/{d}")
                st.markdown(f"**Status:** {bp_status}")
            with m2:
                st.metric("Glucose", f"{g} mg/dL")
                st.markdown(f"**Status:** {g_status}")
            with m3:
                st.metric("Weight", f"{w} lbs")
                st.markdown(f"**Status:** {w_status}")
    except Exception:
        pass

    st.divider()

    # NEW: WEEKLY SUMMARY INSIGHTS
    with st.expander("📊 Weekly Insights Summary"):
        try:
            seven_days_ago = (datetime.now() - timedelta(days=7)).date()
            week_data = (
                supabase.table("health_metrics")
                .select("*")
                .gte("date", str(seven_days_ago))
                .execute()
            )
            if week_data.data:
                w_df = pd.DataFrame(week_data.data)
                avg_glu = w_df["blood_glucose"].mean()
                avg_wgt = w_df["weight_lb"].mean()
                st.write(f"**Last 7 Days:**")
                st.write(f"* Average Glucose: **{avg_glu:.1f} mg/dL**")
                st.write(f"* Average Weight: **{avg_wgt:.1f} lbs**")
                st.write(f"* Total Entries: **{len(w_df)} logs**")
            else:
                st.write("Not enough data for a weekly summary yet.")
        except Exception:
            pass

    st.divider()
    with st.expander("🩺 Log New Vitals & Weight"):
        with st.form("vitals_form", clear_on_submit=True):
            col_d, col_t = st.columns(2)
            m_date, m_time = col_d.date_input("Date"), col_t.time_input("Time")
            c1, c2, c3 = st.columns(3)
            sys, dia = (
                c1.number_input("Systolic", value=120),
                c2.number_input("Diastolic", value=80),
            )
            weight_val, glucose_val = (
                c3.number_input("Weight", value=180.0),
                st.number_input("Glucose", value=100),
            )
            if st.form_submit_button("Save Metrics"):
                supabase.table("health_metrics").insert(
                    {
                        "date": str(m_date),
                        "time": str(m_time),
                        "blood_pressure_systolic": sys,
                        "blood_pressure_diastolic": dia,
                        "blood_glucose": glucose_val,
                        "weight_lb": weight_val,
                    }
                ).execute()
                st.rerun()

    st.divider()
    st.subheader("📈 Health Trends")
    time_view = st.radio("Range:", ["7 Days", "30 Days", "Year"], horizontal=True)
    cutoff = datetime.now().date() - timedelta(
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
            for m in [
                "blood_pressure_systolic",
                "blood_pressure_diastolic",
                "blood_glucose",
                "weight_lb",
            ]:
                df[m] = pd.to_numeric(df[m], errors="coerce")

            st.write("#### Blood Pressure")
            st.line_chart(
                df,
                x="date",
                y=["blood_pressure_systolic", "blood_pressure_diastolic"],
                color=[bp_line_color, "#5dade2"],
            )
            weight_df = df[df["weight_lb"] > 0]
            if not weight_df.empty:
                st.write("#### Weight (lbs)")
                st.line_chart(weight_df, x="date", y="weight_lb", color=wgt_line_color)
            st.write("#### Blood Glucose")
            st.line_chart(df, x="date", y="blood_glucose", color=glu_line_color)

            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Download Data", data=csv, file_name="health_export.csv"
            )
    except Exception as e:
        st.error(f"Chart Error: {e}")
