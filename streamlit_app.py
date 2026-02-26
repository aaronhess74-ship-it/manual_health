import streamlit as st
from supabase import create_client
from datetime import datetime
import pandas as pd

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
TARGET_WEIGHT = 180
TARGET_GLUCOSE = 100
TARGET_BP_SYS = 130

# Visual Constants
C_RED, C_YELLOW, C_GREEN, C_GRAY = "#e74c3c", "#f1c40f", "#2ecc71", "#bdc3c7"

tab1, tab2, tab3, tab4 = st.tabs(
    ["🍴 Nutrition", "🩺 Health Metrics", "🏃 Activity", "📊 Reports & Exports"]
)

# --- TAB 1: NUTRITION (Full Restoration) ---
with tab1:
    try:
        response = supabase.table("daily_variance").select("*").execute()
        if response.data:
            latest = response.data[0]
            st.subheader(f"Status for {latest['date']}")

            cals = float(latest.get("total_calories", 0))
            prot = float(latest.get("total_protein", 0))
            net_c = float(latest.get("total_net_carbs", 0))
            fat = float(latest.get("total_fat", 0))
            fib = float(latest.get("total_fiber", 0))

            def get_status_icon(curr, target, is_ceiling=True):
                if is_ceiling:
                    if curr > target:
                        return "🔴 OVER"
                    if curr >= (target * 0.90):
                        return "🟡 NEAR"
                    return "🟢 OK"
                else:
                    if curr >= target:
                        return "🟢 GOAL"
                    if curr >= (target * 0.90):
                        return "🟡 LOW"
                    return "🔴 URGENT"

            c1, c2, c3, c4, c5 = st.columns(5)
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
            c4.metric(
                f"Total Fat {get_status_icon(fat, TARGET_FAT_MAX)}",
                f"{int(fat)}g",
                f"{int(TARGET_FAT_MAX - fat)} Left",
            )
            c5.metric(
                f"Fiber {get_status_icon(fib, TARGET_FIBER_MIN, False)}",
                f"{int(fib)}g",
                f"{int(fib - TARGET_FIBER_MIN)} vs Target",
            )
    except:
        pass

    st.divider()
    st.subheader("⚡ Quick Log")
    try:
        # Fetches the last 5 unique foods you actually logged
        recent = (
            supabase.table("daily_logs")
            .select("food_id, foods(food_name)")
            .order("log_id", desc=True)
            .limit(25)
            .execute()
        )
        if recent.data:
            seen, quick_foods = set(), []
            for r in recent.data:
                if r["foods"] and r["food_id"] not in seen:
                    quick_foods.append(
                        {"id": r["food_id"], "name": r["foods"]["food_name"]}
                    )
                    seen.add(r["food_id"])
                if len(quick_foods) == 5:
                    break

            q_cols = st.columns(len(quick_foods))
            for i, f in enumerate(quick_foods):
                if q_cols[i].button(f"➕ {f['name']}", key=f"q_{f['id']}"):
                    supabase.table("daily_logs").insert(
                        {
                            "food_id": f["id"],
                            "servings": 1.0,
                            "log_date": str(datetime.now().date()),
                        }
                    ).execute()
                    st.rerun()
    except:
        pass

    st.divider()
    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader("🍴 Log Existing")
        f_query = supabase.table("foods").select("*").order("food_name").execute()
        if f_query.data:
            f_dict = {f["food_name"]: f for f in f_query.data}
            sel = st.selectbox(
                "Search Library", options=list(f_dict.keys()), index=None
            )
            if sel:
                food = f_dict[sel]
                srv = st.number_input("Servings", 0.1, 10.0, value=1.0)
                if st.button("Log Selection"):
                    supabase.table("daily_logs").insert(
                        {
                            "food_id": food["food_id"],
                            "servings": srv,
                            "log_date": str(datetime.now().date()),
                        }
                    ).execute()
                    st.rerun()

    with col_right:
        st.subheader("🆕 New Food")
        with st.form("new_food_form", clear_on_submit=True):
            n_name = st.text_input("Food Name")
            c_c1, c_c2 = st.columns(2)
            n_cal = c_c1.number_input("Calories", 0)
            n_prot = c_c2.number_input("Protein (g)", 0)
            n_carb = c_c1.number_input("Carbs (g)", 0)
            n_fat = c_c2.number_input("Fat (g)", 0)
            n_fib = st.number_input("Fiber (g)", 0)
            if st.form_submit_button("Save & Log"):
                res = (
                    supabase.table("foods")
                    .insert(
                        {
                            "food_name": n_name,
                            "calories": n_cal,
                            "protein_g": n_prot,
                            "carbs_g": n_carb,
                            "fat_g": n_fat,
                            "fiber_g": n_fib,
                        }
                    )
                    .execute()
                )
                if res.data:
                    supabase.table("daily_logs").insert(
                        {
                            "food_id": res.data[0]["food_id"],
                            "servings": 1.0,
                            "log_date": str(datetime.now().date()),
                        }
                    ).execute()
                    st.rerun()

# --- TAB 2: HEALTH METRICS (Full Restoration with Color Logic) ---
with tab2:
    with st.expander("➕ Add New Entry", expanded=True):
        with st.form("vitals_form"):
            v_date = st.date_input("Date", datetime.now().date())
            c_v1, c_v2, c_v3 = st.columns(3)
            s_bp = c_v1.number_input("Systolic", 120)
            d_bp = c_v2.number_input("Diastolic", 80)
            w_lb = c_v3.number_input("Weight", 180.0)
            g_mg = st.number_input("Glucose", 100)
            if st.form_submit_button("Record Vitals"):
                supabase.table("health_metrics").insert(
                    {
                        "date": str(v_date),
                        "blood_pressure_systolic": s_bp,
                        "blood_pressure_diastolic": d_bp,
                        "blood_glucose": g_mg,
                        "weight_lb": w_lb,
                    }
                ).execute()
                st.rerun()

    try:
        h_data = (
            supabase.table("health_metrics")
            .select("*")
            .order("date", desc=False)
            .execute()
        )
        if h_data.data:
            df_h = pd.DataFrame(h_data.data)
            latest_v = h_data.data[-1]

            def get_bp_color(s):
                return (
                    ("🟢 OK", C_GREEN)
                    if s < 130
                    else (("🟡 NEAR", C_YELLOW) if s < 140 else ("🔴 HIGH", C_RED))
                )

            def get_glu_color(g):
                return (
                    ("🟢 OK", C_GREEN)
                    if g < 100
                    else (("🟡 NEAR", C_YELLOW) if g < 126 else ("🔴 HIGH", C_RED))
                )

            def get_wt_color(w):
                return (
                    ("🟢 OK", C_GREEN)
                    if w <= TARGET_WEIGHT
                    else (("🟡 HIGH", C_YELLOW) if w < 200 else ("🔴 DANGER", C_RED))
                )

            bp_txt, bp_col = get_bp_color(latest_v["blood_pressure_systolic"])
            gl_txt, gl_col = get_glu_color(latest_v["blood_glucose"])
            wt_txt, wt_col = get_wt_color(latest_v["weight_lb"])

            m1, m2, m3 = st.columns(3)
            m1.metric(
                f"BP {bp_txt}",
                f"{int(latest_v['blood_pressure_systolic'])}/{int(latest_v['blood_pressure_diastolic'])}",
            )
            m2.metric(f"Glucose {gl_txt}", f"{latest_v['blood_glucose']} mg/dL")
            m3.metric(f"Weight {wt_txt}", f"{latest_v['weight_lb']} lbs")

            st.divider()
            st.subheader("📉 Health Trends & Targets")
            df_h["Target Weight"], df_h["Target Glucose"], df_h["Target BP"] = (
                TARGET_WEIGHT,
                TARGET_GLUCOSE,
                TARGET_BP_SYS,
            )

            col_t1, col_t2 = st.columns(2)
            with col_t1:
                st.line_chart(
                    df_h,
                    x="date",
                    y=["weight_lb", "Target Weight"],
                    color=[wt_col, C_GRAY],
                )
            with col_t2:
                st.line_chart(
                    df_h,
                    x="date",
                    y=["blood_glucose", "Target Glucose"],
                    color=[gl_col, C_GRAY],
                )
            st.line_chart(
                df_h,
                x="date",
                y=["blood_pressure_systolic", "blood_pressure_diastolic", "Target BP"],
                color=[bp_col, "#95a5a6", C_GRAY],
            )
    except:
        pass

# --- TAB 3: ACTIVITY (Full Restoration) ---
with tab3:
    with st.form("activity_form"):
        act_date = st.date_input("Date", datetime.now().date())
        act_name = st.text_input("Exercise")
        c_a1, c_a2 = st.columns(2)
        act_min = c_a1.number_input("Minutes", 0.0)
        act_mi = c_a2.number_input("Miles", 0.0)
        if st.form_submit_button("Log Activity"):
            supabase.table("activity_logs").insert(
                {
                    "date": str(act_date),
                    "exercise_name": act_name,
                    "duration_min": act_min,
                    "distance_miles": act_mi,
                }
            ).execute()
            st.rerun()

    st.divider()
    try:
        act_data = (
            supabase.table("activity_logs")
            .select("*")
            .order("date", desc=False)
            .execute()
        )
        if act_data.data:
            df_a = pd.DataFrame(act_data.data)
            st.subheader("🏃 Activity Trend")
            st.line_chart(df_a, x="date", y="duration_min", color="#3498db")
            st.subheader("📜 History")
            st.dataframe(
                df_a.sort_values(by="date", ascending=False), use_container_width=True
            )
    except:
        pass

# --- TAB 4: REPORTS ---
with tab4:
    st.subheader("📋 System Reports")
    rep_sel = st.selectbox(
        "View Data", ["Nutrition Variance", "Health Vitals", "Activity Logs"]
    )
    rep_tbl = (
        "daily_variance"
        if rep_sel == "Nutrition Variance"
        else "health_metrics"
        if rep_sel == "Health Vitals"
        else "activity_logs"
    )
    rep_res = supabase.table(rep_tbl).select("*").order("date", desc=True).execute()
    if rep_res.data:
        st.dataframe(pd.DataFrame(rep_res.data), use_container_width=True)
