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

# Colors for Trends
C_RED, C_YELLOW, C_GREEN, C_GRAY = "#e74c3c", "#f1c40f", "#2ecc71", "#bdc3c7"

tab1, tab2, tab3, tab4 = st.tabs(
    ["🍴 Nutrition", "🩺 Health Metrics", "🏃 Activity", "📊 Reports & Exports"]
)

# --- TAB 1: NUTRITION ---
# --- TAB 1: NUTRITION (FIXED QUICK LOG & STATUS) ---
with tab1:
    try:
        # Fetch the daily summary (totalled views)
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
    except Exception as e:
        st.error("Waiting for daily summary data...")

    st.divider()
    st.subheader("⚡ Quick Log")
    try:
        recent_res = (
            supabase.table("daily_logs")
            .select("food_id, foods(food_name)")
            .order("log_id", desc=True)
            .limit(30)
            .execute()
        )
        if recent_res.data:
            seen = set()
            quick_foods = []
            for r in recent_res.data:
                if r["foods"] and r["food_id"] not in seen:
                    quick_foods.append(
                        {"id": r["food_id"], "name": r["foods"]["food_name"]}
                    )
                    seen.add(r["food_id"])
                if len(quick_foods) >= 5:
                    break
            if quick_foods:
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
            else:
                st.info("Log a few items below to see Quick Log buttons here!")
    except:
        pass

    st.divider()
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("🍴 Log Existing")
        f_query = supabase.table("foods").select("*").order("food_name").execute()
        if f_query.data:
            f_dict = {f["food_name"]: f for f in f_query.data}
            sel = st.selectbox(
                "Search Food Library...", options=list(f_dict.keys()), index=None
            )
            if sel:
                food = f_dict[sel]
                srv = st.number_input("Servings", 0.1, 10.0, value=1.0, step=0.1)
                if st.button("Log Meal"):
                    supabase.table("daily_logs").insert(
                        {
                            "food_id": f["id"],
                            "servings": 1.0,
                            "food_id": food["food_id"],
                            "servings": srv,
                            "log_date": str(datetime.now().date()),
                        }
                    ).execute()
                    st.rerun()
    except:
        pass

# --- TAB 2: HEALTH METRICS (Restored Trends & Colored Status) ---
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
            nf, nfi = st.number_input("Fat", 0), st.number_input("Fib", 0)
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

    st.subheader("📜 Today's History")
    h_res = (
        supabase.table("daily_logs")
        .select("log_id, servings, foods(food_name, calories)")
        .eq("log_date", str(datetime.now().date()))
        .execute()
    )
    if h_res.data:
        for item in h_res.data:
            hc1, hc2, hc3 = st.columns([3, 1, 1])
            hc1.write(f"**{item['foods']['food_name']}**")
            hc2.write(f"{int(item['foods']['calories'] * item['servings'])} cal")
            if hc3.button("🗑️", key=f"del_{item['log_id']}"):
                supabase.table("daily_logs").delete().eq(
                    "log_id", item["log_id"]
                ).execute()
                st.rerun()

# --- TAB 2: HEALTH METRICS (RESTORED TRENDS & STATUS) ---
with tab2:
    with st.expander("➕ Log New Vitals", expanded=True):
        with st.form("v_form"):
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
        all_v = (
            supabase.table("health_metrics")
            .select("*")
            .order("date", desc=False)
            .execute()
        )
        if all_v.data:
            df_v = pd.DataFrame(all_v.data)
            latest_v = all_v.data[-1]

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
                    if w < 185
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
            st.subheader("📉 Health Trends (with Targets)")
            st.subheader("📉 Health Trends")
            df_v["Target Weight"], df_v["Target Glucose"], df_v["Target BP"] = (
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
                y=["blood_pressure_systolic", "blood_pressure_diastolic", "Target BP"],
                color=[bp_c, "#95a5a6", C_GRAY],
            )
    except:
        st.info("Log your first vitals to see trends.")
        st.info("No vitals data found yet.")

# --- TAB 3: ACTIVITY (Restored Trends) ---
# --- TAB 3: ACTIVITY (RESTORED TRENDS) ---
with tab3:
    with st.form("act_form"):
        a_date = st.date_input("Date", datetime.now().date())
        name = st.text_input("Exercise Name")
        c1, c2 = st.columns(2)
        dur, dist = (
            c1.number_input("Minutes", 0.0),
            c2.number_input("Miles (if cardio)", 0.0),
        )
        if st.form_submit_button("Log Activity"):
            supabase.table("activity_logs").insert(
                {
                    "date": str(a_date),
                    "exercise_name": name,
                    "duration_min": dur,
                    "distance_miles": dist,
                }
            ).execute()
            st.rerun()

    st.divider()
    try:
        a_res = (
            supabase.table("activity_logs")
            .select("*")
            .order("date", desc=False)
            .execute()
        )
        if a_res.data:
            df_a = pd.DataFrame(a_res.data)
            st.subheader("🏃 Activity Trends")
            st.subheader("🏃 Activity History & Trends")
            st.line_chart(df_a, x="date", y="duration_min", color="#3498db")
            st.dataframe(
                df_a.sort_values(by="date", ascending=False), use_container_width=True
            )
    except:
        pass

# --- TAB 4: REPORTS & IMPORTER (With De-duplication) ---
# --- TAB 4: REPORTS & IMPORTER (CLEAN & SAFE) ---
with tab4:
    st.subheader("📥 Universal Food Importer")
    import_type = st.selectbox(
        "Format", ["Daily Food & Nutrition (Kaggle)", "USDA FoodData Central"]
    )
    uploaded_file = st.file_uploader("Upload CSV", type="csv")

    if uploaded_file:
        try:
            df_raw = pd.read_csv(uploaded_file, on_bad_lines="skip", engine="python")
            mapping = (
                {
                    "Food_Item": "food_name",
                    "Calories (kcal)": "calories",
                    "Protein (g)": "protein_g",
                    "Carbohydrates (g)": "carbs_g",
                    "Fat (g)": "fat_g",
                    "Fiber (g)": "fiber_g",
                }
                if "Kaggle" in import_type
                else {
                    "description": "food_name",
                    "Energy": "calories",
                    "Protein": "protein_g",
                    "Carbohydrate, by difference": "carbs_g",
                    "Total lipid (fat)": "fat_g",
                    "Fiber, total dietary": "fiber_g",
                }
            )
            df_mapped = df_raw[
                [c for c in mapping.keys() if c in df_raw.columns]
            ].rename(columns=mapping)
            for col in ["calories", "protein_g", "carbs_g", "fat_g", "fiber_g"]:
                if col not in df_mapped.columns:
                    df_mapped[col] = 0.0
    st.subheader("📊 Goal Performance")
    try:
        perf_res = supabase.table("daily_variance").select("*").execute()
        if perf_res.data:
            df_perf = pd.DataFrame(perf_res.data)
            win_rate = (
                len(df_perf[df_perf["total_calories"] <= TARGET_CALORIES])
                / len(df_perf)
            ) * 100
            st.info(f"🏆 Calorie Goal Win Rate: **{win_rate:.1f}%**")
    except:
        pass

            if st.button("🚀 Confirm Upsert Import"):
                supabase.table("foods").upsert(
                    df_mapped.to_dict(orient="records"), on_conflict="food_name"
                ).execute()
                st.success("Import Successful!")
                st.balloons()
        except Exception as e:
            st.error(f"Error: {e}")
    st.divider()
    st.subheader("📂 Master Data Export")
    report_type = st.selectbox(
        "View Table", ["Nutrition Variance", "Health Vitals", "Activity Logs"]
    )
    tbl = (
        "daily_variance"
        if report_type == "Nutrition Variance"
        else "health_metrics"
        if report_type == "Health Vitals"
        else "activity_logs"
    )
    res = supabase.table(tbl).select("*").order("date", desc=True).execute()
    if res.data:
        st.dataframe(pd.DataFrame(res.data), use_container_width=True)