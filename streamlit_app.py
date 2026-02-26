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

# Define Tabs
tab1, tab2, tab3, tab4 = st.tabs(
    ["🍴 Nutrition", "🩺 Health Metrics", "🏃 Activity", "📊 Reports & Exports"]
)

# --- TAB 1: NUTRITION BUDGET ---
with tab1:
    try:
        response = supabase.table("daily_variance").select("*").execute()
        if response.data:
            latest = response.data[0]
            st.subheader(f"Status for {latest['date']}")
            c1, c2, c3, c4, c5 = st.columns(5)

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
                else:
                    if curr >= target:
                        return "🟢 GOAL"
                    if curr >= (target * 0.90):
                        return "🟡 LOW"
                    return "🔴 URGENT"

            c1.metric(
                f"Calories {get_status_icon(cals, TARGET_CALORIES)}",
                f"{int(cals)}",
                f"{int(TARGET_CALORIES - cals)} Left",
                delta_color="off",
            )
            c2.metric(
                f"Protein {get_status_icon(prot, TARGET_PROTEIN, False)}",
                f"{int(prot)}g",
                f"{int(prot - TARGET_PROTEIN)} vs Target",
                delta_color="off",
            )
            c3.metric(
                f"Net Carbs {get_status_icon(net_c, TARGET_NET_CARBS)}",
                f"{int(net_c)}g",
                f"{int(TARGET_NET_CARBS - net_c)} Left",
                delta_color="off",
            )
            c4.metric(
                f"Total Fat {get_status_icon(fat, TARGET_FAT_MAX)}",
                f"{int(fat)}g",
                f"{int(TARGET_FAT_MAX - fat)} Left",
                delta_color="off",
            )
            c5.metric(
                f"Fiber {get_status_icon(fib, TARGET_FIBER_MIN, False)}",
                f"{int(fib)}g",
                f"{int(fib - TARGET_FIBER_MIN)} vs Target",
                delta_color="off",
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
            .limit(20)
            .execute()
        )
        if recent.data:
            seen, quick_foods = set(), []
            for r in recent.data:
                fid, fname = r["food_id"], r["foods"]["food_name"]
                if fid not in seen and fid is not None:
                    quick_foods.append({"id": fid, "name": fname})
                    seen.add(fid)
                if len(quick_foods) == 5:
                    break
            cols = st.columns(len(quick_foods))
            for i, f in enumerate(quick_foods):
                if cols[i].button(f"➕ {f['name']}", key=f"q_{f['id']}"):
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
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("🍴 Log Existing")
        f_query = supabase.table("foods").select("*").order("food_name").execute()
        if f_query.data:
            f_dict = {f["food_name"]: f for f in f_query.data}
            sel = st.selectbox("Search...", options=list(f_dict.keys()), index=None)
            if sel:
                food = f_dict[sel]
                if food.get("fat_g") is None or pd.isna(food.get("fat_g")):
                    st.info(f"Adding missing macros for {sel}")
                    u_fat, u_fib = (
                        st.number_input("Fat", 0.0),
                        st.number_input("Fiber", 0.0),
                    )
                    if st.button("Update & Log"):
                        supabase.table("foods").update(
                            {"fat_g": u_fat, "fiber_g": u_fib}
                        ).eq("food_id", food["food_id"]).execute()
                        supabase.table("daily_logs").insert(
                            {
                                "food_id": food["food_id"],
                                "servings": 1.0,
                                "log_date": str(datetime.now().date()),
                            }
                        ).execute()
                        st.rerun()
                else:
                    srv = st.number_input("Servings", 0.1, 10.0, value=1.0, step=0.1)
                    if st.button("Log Meal"):
                        supabase.table("daily_logs").insert(
                            {
                                "food_id": food["food_id"],
                                "servings": srv,
                                "log_date": str(datetime.now().date()),
                            }
                        ).execute()
                        st.rerun()

    with col_b:
        st.subheader("🆕 New Food")
        with st.form("new_f", clear_on_submit=True):
            n_name = st.text_input("Name")
            c_c, c_p, c_cb = st.columns(3)
            nc, np, ncb = (
                c_c.number_input("Cal", 0),
                c_p.number_input("Prot", 0),
                c_cb.number_input("Carb", 0),
            )
            c_f, c_fi = st.columns(2)
            nf, nfi = c_f.number_input("Fat", 0), c_fi.number_input("Fib", 0)
            if st.form_submit_button("Save & Log"):
                if n_name:
                    res = (
                        supabase.table("foods")
                        .insert(
                            {
                                "food_name": n_name,
                                "calories": nc,
                                "protein_g": np,
                                "carbs_g": ncb,
                                "fat_g": nf,
                                "fiber_g": nfi,
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

# --- TAB 2: HEALTH METRICS ---
with tab2:
    with st.expander("➕ Log New Vitals", expanded=True):
        with st.form("v_form_top"):
            v_date = st.date_input("Date", datetime.now().date())
            c1, c2, c3 = st.columns(3)
            sys, dia = (
                c1.number_input("Systolic", 120),
                c2.number_input("Diastolic", 80),
            )
            weight, glu = (
                c3.number_input("Weight (lbs)", 180.0),
                st.number_input("Glucose (mg/dL)", 100),
            )
            if st.form_submit_button("Save Vitals"):
                supabase.table("health_metrics").insert(
                    {
                        "date": str(v_date),
                        "blood_pressure_systolic": sys,
                        "blood_pressure_diastolic": dia,
                        "blood_glucose": glu,
                        "weight_lb": weight,
                    }
                ).execute()
                st.rerun()

    try:
        all_vitals = (
            supabase.table("health_metrics")
            .select("*")
            .order("date", desc=False)
            .execute()
        )
        if all_vitals.data:
            df_v = pd.DataFrame(all_vitals.data)
            latest_v = all_vitals.data[-1]
            C_RED, C_YELLOW, C_GREEN, C_GRAY = (
                "#e74c3c",
                "#f1c40f",
                "#2ecc71",
                "#bdc3c7",
            )

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
                    if w < 180
                    else (("🟡 HIGH", C_YELLOW) if w < 220 else ("🔴 DANGER", C_RED))
                )

            bp_s, bp_c = get_bp_info(latest_v["blood_pressure_systolic"])
            gl_s, gl_c = get_glu_info(latest_v["blood_glucose"])
            wt_s, wt_c = get_wt_info(latest_v["weight_lb"])

            m1, m2, m3 = st.columns(3)
            m1.metric(
                f"BP {bp_s}",
                f"{int(latest_v['blood_pressure_systolic'])}/{int(latest_v['blood_pressure_diastolic'])}",
            )
            m2.metric(f"Glucose {gl_s}", f"{latest_v['blood_glucose']} mg/dL")
            m3.metric(f"Weight {wt_s}", f"{latest_v['weight_lb']} lbs")

            st.divider()
            df_v["Target Weight"], df_v["Target Glucose"], df_v["Target Systolic"] = (
                TARGET_WEIGHT,
                TARGET_GLUCOSE,
                TARGET_BP_SYS,
            )
            t1, t2 = st.columns(2)
            with t1:
                st.line_chart(
                    df_v,
                    x="date",
                    y=["weight_lb", "Target Weight"],
                    color=[wt_c, C_GRAY],
                )
            with t2:
                st.line_chart(
                    df_v,
                    x="date",
                    y=["blood_glucose", "Target Glucose"],
                    color=[gl_c, C_GRAY],
                )
            st.line_chart(
                df_v,
                x="date",
                y=[
                    "blood_pressure_systolic",
                    "blood_pressure_diastolic",
                    "Target Systolic",
                ],
                color=[bp_c, "#95a5a6", C_GRAY],
            )

            st.subheader("📜 Vitals History")
            st.dataframe(
                df_v.sort_values(by="date", ascending=False), use_container_width=True
            )
    except:
        st.info("No data logged yet.")

# --- TAB 3: ACTIVITY TRACKER ---
with tab3:
    cat = st.radio("Type:", ["Strength", "Static", "Cardio"], horizontal=True)
    with st.form("act_form"):
        a_date = st.date_input("Date", datetime.now().date())
        name = st.text_input("Exercise Name")
        c1, c2 = st.columns(2)
        dur, dist, sets, reps = 0.0, 0.0, 0, 0
        if cat == "Cardio":
            dur, dist = c1.number_input("Min", 0.0), c2.number_input("Mi", 0.0)
        else:
            sets, reps = c1.number_input("Sets", 0), c2.number_input("Reps", 0)
            if cat == "Static":
                dur = st.number_input("Min", 0.0)
        if st.form_submit_button("Log Activity"):
            supabase.table("activity_logs").insert(
                {
                    "date": str(a_date),
                    "exercise_name": name,
                    "duration_min": dur,
                    "distance_miles": dist,
                    "sets": sets,
                    "reps": reps,
                    "type": cat,
                }
            ).execute()
            st.rerun()

# --- TAB 4: REPORTS & EXPORTS ---
with tab4:
    st.subheader("📂 Central Data Export")
    report_type = st.selectbox(
        "Select Report Type", ["Nutrition History", "Health Vitals", "Activity Logs"]
    )

    if report_type == "Nutrition History":
        res = (
            supabase.table("daily_variance")
            .select("*")
            .order("date", desc=True)
            .execute()
        )
    elif report_type == "Health Vitals":
        res = (
            supabase.table("health_metrics")
            .select("*")
            .order("date", desc=True)
            .execute()
        )
    else:
        res = (
            supabase.table("activity_logs")
            .select("*")
            .order("date", desc=True)
            .execute()
        )

    if res.data:
        df_report = pd.DataFrame(res.data)
        st.dataframe(df_report, use_container_width=True)
        csv = df_report.to_csv(index=False).encode("utf-8")
        st.download_button(
            label=f"📥 Download {report_type} as CSV",
            data=csv,
            file_name=f"{report_type.lower().replace(' ', '_')}_{datetime.now().date()}.csv",
            mime="text/csv",
        )
    else:
        st.warning("No data found for this report type.")
