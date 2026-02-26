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

tab1, tab2, tab3 = st.tabs(
    ["🍴 Nutrition Budget", "🩺 Health Metrics", "🏃 Activity Tracker"]
)

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
        pass

    st.divider()
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
            seen, quick_foods = set(), []
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
    except:
        st.caption("Log items to see Quick Log buttons.")

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
        except:
            pass
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
            df_history = []
            for item in history_res.data:
                c1, c2, c3 = st.columns([3, 1, 1])
                c1.write(f"**{item['foods']['food_name']}**")
                c2.write(f"{int(item['foods']['calories'] * item['servings'])} cal")
                if c3.button("🗑️", key=f"del_{item['log_id']}"):
                    supabase.table("daily_logs").delete().eq(
                        "log_id", item["log_id"]
                    ).execute()
                    st.rerun()
                df_history.append(
                    {
                        "Food": item["foods"]["food_name"],
                        "Calories": item["foods"]["calories"] * item["servings"],
                    }
                )

            if df_history:
                csv_food = pd.DataFrame(df_history).to_csv(index=False).encode("utf-8")
                st.download_button(
                    "📥 Download Food Log (CSV)",
                    data=csv_food,
                    file_name=f"food_log_{datetime.now().date()}.csv",
                )
    except:
        pass

# --- TAB 2: HEALTH METRICS ---
with tab2:
    bp_line_color, glu_line_color, wgt_line_color = (
        COLOR_NORMAL,
        COLOR_NORMAL,
        COLOR_NORMAL,
    )
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
            if s < 120 and d < 80:
                bp_s, bp_line_color = "🟢 Normal", COLOR_NORMAL
            elif 120 <= s < 130 and d < 80:
                bp_s, bp_line_color = "🟡 Elevated", COLOR_WARNING
            else:
                bp_s, bp_line_color = "🔴 Hypertension", COLOR_DANGER
            if g < 100:
                g_s, glu_line_color = "🟢 Normal", COLOR_NORMAL
            elif 100 <= g < 126:
                g_s, glu_line_color = "🟡 Pre-diabetes", COLOR_WARNING
            else:
                g_s, glu_line_color = "🔴 High", COLOR_DANGER
            if 155 <= w <= 179:
                w_s, wgt_line_color = "🟢 Goal Range", COLOR_NORMAL
            elif 180 <= w <= 200:
                w_s, wgt_line_color = "🟡 Warning Range", COLOR_WARNING
            else:
                w_s, wgt_line_color = "🔴 Above Range", COLOR_DANGER

            st.subheader("🏷️ Latest Vitals Status")
            m1, m2, m3 = st.columns(3)
            m1.metric("Blood Pressure", f"{s}/{d}")
            m1.markdown(f"**Status:** {bp_s}")
            m2.metric("Glucose", f"{g} mg/dL")
            m2.markdown(f"**Status:** {g_s}")
            m3.metric("Weight", f"{w} lbs")
            m3.markdown(f"**Status:** {w_s}")
    except:
        pass

    st.divider()
    with st.expander("🩺 Log New Vitals"):
        with st.form("v_form", clear_on_submit=True):
            col_d, col_t = st.columns(2)
            d_val, t_val = col_d.date_input("Date"), col_t.time_input("Time")
            c1, c2, c3 = st.columns(3)
            sys, dia = (
                c1.number_input("Systolic", 120),
                c2.number_input("Diastolic", 80),
            )
            weight_v, glu_v = c
