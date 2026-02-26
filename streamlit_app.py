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

# --- TAB 1: NUTRITION ---
with tab1:
    try:
        response = supabase.table("daily_variance").select("*").execute()
        if response.data:
            latest = response.data[0]
            st.subheader(f"Status for {latest['date']}")

            cals, prot = (
                float(latest.get("total_calories", 0)),
                float(latest.get("total_protein", 0)),
            )
            net_c, fat = (
                float(latest.get("total_net_carbs", 0)),
                float(latest.get("total_fat", 0)),
            )
            fib = float(latest.get("total_fiber", 0))

            def get_status_icon(curr, target, is_ceiling=True):
                if is_ceiling:
                    if curr > target:
                        return "🔴 OVER"
                    if curr >= (target * 0.90):
                        return "🟡 NEAR"
                    return "🟢 OK"
                return "🟢 GOAL" if curr >= target else "🔴 URGENT"

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
    col_l, col_r = st.columns(2)
    with col_l:
        st.subheader("🍴 Log Existing")
        f_query = supabase.table("foods").select("*").order("food_name").execute()
        if f_query.data:
            f_dict = {f["food_name"]: f for f in f_query.data}
            sel = st.selectbox("Search Food", options=list(f_dict.keys()), index=None)
            if sel:
                food = f_dict[sel]
                srv = st.number_input("Servings", 0.1, 10.0, value=1.0)
                if st.button("Log Meal"):
                    supabase.table("daily_logs").insert(
                        {
                            "food_id": food["food_id"],
                            "servings": srv,
                            "log_date": str(datetime.now().date()),
                        }
                    ).execute()
                    st.rerun()
    with col_r:
        st.subheader("🆕 New Food")
        with st.form("new_f"):
            fn = st.text_input("Name")
            c1, c2 = st.columns(2)
            cal, pr = c1.number_input("Cal", 0), c2.number_input("Prot", 0)
            cb, ft = c1.number_input("Carb", 0), c2.number_input("Fat", 0)
            fi = st.number_input("Fiber", 0)
            if st.form_submit_button("Add & Log"):
                res = (
                    supabase.table("foods")
                    .insert(
                        {
                            "food_name": fn,
                            "calories": cal,
                            "protein_g": pr,
                            "carbs_g": cb,
                            "fat_g": ft,
                            "fiber_g": fi,
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

# --- TAB 2: HEALTH METRICS (RESTORED TARGETS & TRENDS) ---
with tab2:
    with st.expander("➕ Log Vitals", expanded=True):
        with st.form("v_form"):
            v_d = st.date_input("Date", datetime.now().date())
            c1, c2, c3 = st.columns(3)
            sys, dia = c1.number_input("Sys", 120), c2.number_input("Dia", 80)
            wt, gl = c3.number_input("Weight", 180.0), st.number_input("Glucose", 100)
            if st.form_submit_button("Save"):
                supabase.table("health_metrics").insert(
                    {
                        "date": str(v_d),
                        "blood_pressure_systolic": sys,
                        "blood_pressure_diastolic": dia,
                        "blood_glucose": gl,
                        "weight_lb": wt,
                    }
                ).execute()
                st.rerun()

    try:
        hv = (
            supabase.table("health_metrics")
            .select("*")
            .order("date", desc=False)
            .execute()
        )
        if hv.data:
            df_h = pd.DataFrame(hv.data)
            latest = hv.data[-1]

            def get_bp_info(s):
                return (
                    ("🟢 OK", C_GREEN)
                    if s < 130
                    else (("🟡 NEAR", C_YELLOW) if s < 140 else ("🔴 HIGH", C_RED))
                )

            def get_glu_info(g):
                return (
                    ("🟢 OK", C_GREEN)
                    if g < 100
                    else (("🟡 NEAR", C_YELLOW) if g < 126 else ("🔴 HIGH", C_RED))
                )

            def get_wt_info(w):
                return (
                    ("🟢 OK", C_GREEN)
                    if w <= TARGET_WEIGHT
                    else (("🟡 HIGH", C_YELLOW) if w < 200 else ("🔴 DANGER", C_RED))
                )

            bp_s, bp_c = get_bp_info(latest["blood_pressure_systolic"])
            gl_s, gl_c = get_glu_info(latest["blood_glucose"])
            wt_s, wt_c = get_wt_info(latest["weight_lb"])

            m1, m2, m3 = st.columns(3)
            m1.metric(
                f"BP {bp_s}",
                f"{int(latest['blood_pressure_systolic'])}/{int(latest['blood_pressure_diastolic'])}",
            )
            m2.metric(f"Glucose {gl_s}", f"{latest['blood_glucose']} mg/dL")
            m3.metric(f"Weight {wt_s}", f"{latest['weight_lb']} lbs")

            st.divider()
            st.subheader("📉 Health Trends & Targets")
            df_h["Target Weight"], df_h["Target Glucose"], df_h["Target BP"] = (
                TARGET_WEIGHT,
                TARGET_GLUCOSE,
                TARGET_BP_SYS,
            )

            t1, t2 = st.columns(2)
            with t1:
                st.line_chart(
                    df_h,
                    x="date",
                    y=["weight_lb", "Target Weight"],
                    color=[wt_c, C_GRAY],
                )
            with t2:
                st.line_chart(
                    df_h,
                    x="date",
                    y=["blood_glucose", "Target Glucose"],
                    color=[gl_c, C_GRAY],
                )
            st.line_chart(
                df_h,
                x="date",
                y=["blood_pressure_systolic", "blood_pressure_diastolic", "Target BP"],
                color=[bp_c, "#95a5a6", C_GRAY],
            )
    except:
        pass

# --- TAB 3: ACTIVITY (RESTORED RADIO BUTTONS & COMPLEX LOGGING) ---
with tab3:
    st.subheader("🏃 Log Activity")
    act_type = st.radio(
        "Activity Category", ["Strength", "Static/Yoga", "Cardio"], horizontal=True
    )

    with st.form("complex_act_form"):
        ad = st.date_input("Date", datetime.now().date())
        an = st.text_input("Exercise Name")
        c1, c2 = st.columns(2)

        dur, dist, sets, reps = 0.0, 0.0, 0, 0
        if act_type == "Cardio":
            dur = c1.number_input("Minutes", 0.0)
            dist = c2.number_input("Miles", 0.0)
        elif act_type == "Strength":
            sets = c1.number_input("Sets", 0)
            reps = c2.number_input("Reps", 0)
        else:  # Static
            dur = st.number_input("Duration (Minutes)", 0.0)

        if st.form_submit_button("Log Exercise"):
            supabase.table("activity_logs").insert(
                {
                    "date": str(ad),
                    "exercise_name": an,
                    "type": act_type,
                    "duration_min": dur,
                    "distance_miles": dist,
                    "sets": sets,
                    "reps": reps,
                }
            ).execute()
            st.rerun()

    st.divider()
    try:
        ar = (
            supabase.table("activity_logs")
            .select("*")
            .order("date", desc=False)
            .execute()
        )
        if ar.data:
            df_a = pd.DataFrame(ar.data)
            st.subheader("📈 Activity Volume Trend")
            st.line_chart(df_a, x="date", y="duration_min", color="#3498db")
            st.dataframe(
                df_a.sort_values(by="date", ascending=False), use_container_width=True
            )
    except:
        pass

# --- TAB 4: REPORTS (RESTORED UNIFIED MASTER REPORT) ---
with tab4:
    st.subheader("📊 Unified Health & Nutrition Master")
    try:
        # Merge all three main tables on date
        df_n = pd.DataFrame(supabase.table("daily_variance").select("*").execute().data)
        df_h = pd.DataFrame(supabase.table("health_metrics").select("*").execute().data)
        df_a = pd.DataFrame(supabase.table("activity_logs").select("*").execute().data)

        if not df_n.empty and not df_h.empty:
            df_master = pd.merge(df_n, df_h, on="date", how="outer")
            if not df_a.empty:
                # Aggregate activity by date to avoid duplicates in merge
                df_a_daily = (
                    df_a.groupby("date")
                    .agg({"duration_min": "sum", "distance_miles": "sum"})
                    .reset_index()
                )
                df_master = pd.merge(df_master, df_a_daily, on="date", how="outer")

            df_master = df_master.sort_values(by="date", ascending=False)
            st.dataframe(df_master, use_container_width=True)

            csv = df_master.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Download Master Report",
                csv,
                "health_master_unified.csv",
                "text/csv",
            )
        else:
            st.info("Log daily data to see the Master Unified Report.")
    except:
        pass

    st.divider()
    st.subheader("📁 Individual Tables")
    rep_sel = st.selectbox(
        "View Source Data", ["Nutrition Variance", "Health Vitals", "Activity Logs"]
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
