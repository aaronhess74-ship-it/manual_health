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
    except Exception as e:
        st.info("Log a meal below to see today's status.")

    st.divider()

    # Quick Log Logic
    st.subheader("⚡ Quick Log")
    try:
        recent_logs = (
            supabase.table("daily_logs")
            .select("food_id, foods(food_name)")
            .order("log_id", desc=True)
            .limit(20)
            .execute()
        )
        if recent_logs.data:
            seen = set()
            quick_foods = []
            for r in recent_logs.data:
                fid, fname = r["food_id"], r["foods"]["food_name"]
                if fid not in seen:
                    quick_foods.append({"id": fid, "name": fname})
                    seen.add(fid)
                if len(quick_foods) == 5:
                    break

            cols = st.columns(len(quick_foods))
            for i, food in enumerate(quick_foods):
                if cols[i].button(f"➕ {food['name']}", key=f"q_{food['id']}"):
                    supabase.table("daily_logs").insert(
                        {
                            "food_id": food["id"],
                            "servings": 1.0,
                            "log_date": str(datetime.now().date()),
                        }
                    ).execute()
                    st.rerun()
    except Exception as e:
        st.caption("Log items manually to see Quick Log buttons.")

    st.divider()
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("🍴 Log Existing Food")
        try:
            food_query = (
                supabase.table("foods").select("*").order("food_name").execute()
            )
            if food_query.data:
                food_dict = {f["food_name"]: f for f in food_query.data}
                selected_name = st.selectbox(
                    "Search database...",
                    options=list(food_dict.keys()),
                    index=None,
                    placeholder="Type to search...",
                )
                servings = st.number_input(
                    "Servings", min_value=0.1, value=1.0, step=0.1
                )
                if st.button("Log Meal") and selected_name:
                    supabase.table("daily_logs").insert(
                        {
                            "food_id": food_dict[selected_name]["food_id"],
                            "servings": servings,
                            "log_date": str(datetime.now().date()),
                        }
                    ).execute()
                    st.rerun()
        except Exception as e:
            st.error("Error loading search.")

    with col_b:
        st.subheader("🆕 Add New Food")
        with st.form("new_food_form", clear_on_submit=True):
            new_name = st.text_input("Food Name")
            c1, c2, c3 = st.columns(3)
            nc, np, ncb = (
                c1.number_input("Cals", 0),
                c2.number_input("Prot", 0),
                c3.number_input("Carb", 0),
            )
            if st.form_submit_button("Save & Log"):
                if new_name:
                    f_res = (
                        supabase.table("foods")
                        .insert(
                            {
                                "food_name": new_name,
                                "calories": nc,
                                "protein_g": np,
                                "carbs_g": ncb,
                            }
                        )
                        .execute()
                    )
                    if f_res.data:
                        supabase.table("daily_logs").insert(
                            {
                                "food_id": f_res.data[0]["food_id"],
                                "servings": 1.0,
                                "log_date": str(datetime.now().date()),
                            }
                        ).execute()
                        st.rerun()

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
                c1, c2, c3 = st.columns([3, 1, 1])
                c1.write(f"**{item['foods']['food_name']}**")
                c2.write(f"{int(item['foods']['calories'] * item['servings'])} cal")
                if c3.button("🗑️", key=f"del_{item['log_id']}"):
                    supabase.table("daily_logs").delete().eq(
                        "log_id", item["log_id"]
                    ).execute()
                    st.rerun()
    except Exception as e:
        pass

# --- TAB 2: HEALTH METRICS ---
with tab2:
    bp_line_color, glu_line_color, wgt_line_color = (
        COLOR_NORMAL,
        COLOR_NORMAL,
        COLOR_NORMAL,
    )

    # 1. Latest Status & Warnings
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

            # BP Status Logic
            if s < 120 and d < 80:
                bp_s, bp_line_color = "🟢 Normal", COLOR_NORMAL
            elif 120 <= s < 130 and d < 80:
                bp_s, bp_line_color = "🟡 Elevated", COLOR_WARNING
            else:
                bp_s, bp_line_color = "🔴 Hypertension", COLOR_DANGER

            # Glucose Status Logic
            if g < 100:
                g_s, glu_line_color = "🟢 Normal", COLOR_NORMAL
            elif 100 <= g < 126:
                g_s, glu_line_color = "🟡 Pre-diabetes", COLOR_WARNING
            else:
                g_s, glu_line_color = "🔴 High", COLOR_DANGER

            # Weight Status Logic
            if 155 <= w <= 179:
                w_s, wgt_line_color = "🟢 Goal Range", COLOR_NORMAL
            elif 180 <= w <= 200:
                w_s, wgt_line_color = "🟡 Warning Range", COLOR_WARNING
            else:
                w_s, wgt_line_color = "🔴 Above Range", COLOR_DANGER

            if bp_line_color == COLOR_DANGER or glu_line_color == COLOR_DANGER:
                st.warning(
                    "⚠️ **Attention:** Vitals are currently in the High zone. Consider resting."
                )

            st.subheader("🏷️ Latest Vitals Status")
            m1, m2, m3 = st.columns(3)
            m1.metric("Blood Pressure", f"{s}/{d}")
            m1.markdown(f"**Status:** {bp_s}")
            m2.metric("Glucose", f"{g} mg/dL")
            m2.markdown(f"**Status:** {g_s}")
            m3.metric("Weight", f"{w} lbs")
            m3.markdown(f"**Status:** {w_s}")
    except Exception as e:
        st.info("Log your first vitals to see status summary.")

    # 2. Weekly Summary
    st.divider()
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
                st.write(f"* Avg Glucose: **{w_df['blood_glucose'].mean():.1f} mg/dL**")
                st.write(f"* Avg Weight: **{w_df['weight_lb'].mean():.1f} lbs**")
                st.write(f"* Total Entries: **{len(w_df)}**")
        except Exception as e:
            st.write("No weekly data yet.")

    # 3. Log Form
    st.divider()
    with st.expander("🩺 Log New Vitals & Weight"):
        with st.form("vitals_form", clear_on_submit=True):
            col_d, col_t = st.columns(2)
            m_date, m_time = col_d.date_input("Date"), col_t.time_input("Time")
            c1, c2, c3 = st.columns(3)
            sys, dia = (
                c1.number_input("Systolic", 120),
                c2.number_input("Diastolic", 80),
            )
            weight_v, glu_v = (
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
                        "blood_glucose": glu_v,
                        "weight_lb": weight_v,
                    }
                ).execute()
                st.rerun()

    # 4. Trends
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
            st.write("#### Weight (lbs)")
            st.line_chart(
                df[df["weight_lb"] > 0], x="date", y="weight_lb", color=wgt_line_color
            )
            st.write("#### Blood Glucose")
            st.line_chart(df, x="date", y="blood_glucose", color=glu_line_color)
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Download Data", data=csv, file_name="health_export.csv"
            )
    except Exception as e:
        st.error(f"Chart Error: {e}")
