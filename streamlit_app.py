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

# --- TAB 1: NUTRITION ---
with tab1:
    try:
        response = supabase.table("daily_variance").select("*").execute()
        if response.data:
            latest = response.data[0]
            st.subheader(f"Status for {latest['date']}")
            c1, c2, c3, c4, c5 = st.columns(5)

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

    st.subheader("📜 Today's Meal History")
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
        all_v = (
            supabase.table("health_metrics")
            .select("*")
            .order("date", desc=False)
            .execute()
        )
        if all_v.data:
            df_v = pd.DataFrame(all_v.data)
            latest_v = all_v.data[-1]
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

# --- TAB 3: ACTIVITY ---
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
            st.line_chart(df_a, x="date", y="duration_min")
            st.subheader("📜 Activity History")
            st.dataframe(
                df_a.sort_values(by="date", ascending=False), use_container_width=True
            )
    except:
        pass

# --- TAB 4: REPORTS & EXPORTS ---
with tab4:
    st.subheader("📊 Performance & Data Central")

    # 1. Goal Performance Feature
    try:
        nut_data = (
            supabase.table("daily_variance")
            .select("*")
            .order("date", desc=False)
            .execute()
        )
        if nut_data.data:
            df_perf = pd.DataFrame(nut_data.data)
            df_perf["Cals_Pass"] = df_perf["total_calories"] <= TARGET_CALORIES
            df_perf["Prot_Pass"] = df_perf["total_protein"] >= TARGET_PROTEIN
            df_perf["Carb_Pass"] = df_perf["total_net_carbs"] <= TARGET_NET_CARBS

            days_tracked = len(df_perf)
            perfect_days = len(
                df_perf[
                    df_perf["Cals_Pass"] & df_perf["Prot_Pass"] & df_perf["Carb_Pass"]
                ]
            )
            win_rate = (perfect_days / days_tracked) * 100 if days_tracked > 0 else 0

            st.info(
                f"🏆 Overall Goal Win Rate: **{win_rate:.1f}%** ({perfect_days} perfect days out of {days_tracked})"
            )
    except:
        pass

    st.divider()

    # 2. Universal Report View
    st.subheader("📁 Data View & Export")
    report_type = st.selectbox(
        "Select View",
        [
            "Nutrition Variance",
            "Health Vitals",
            "Activity Logs",
            "Master Combined Report",
        ],
    )

    if report_type == "Master Combined Report":
        n = pd.DataFrame(supabase.table("daily_variance").select("*").execute().data)
        h = pd.DataFrame(supabase.table("health_metrics").select("*").execute().data)
        if not n.empty and not h.empty:
            df_master = pd.merge(n, h, on="date", how="outer").sort_values(
                by="date", ascending=False
            )
            st.dataframe(df_master, use_container_width=True)
            csv = df_master.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Download Master CSV", csv, "master_report.csv", "text/csv"
            )
        else:
            st.warning("Not enough data to combine reports.")
    else:
        tbl = (
            "daily_variance"
            if report_type == "Nutrition Variance"
            else "health_metrics"
            if report_type == "Health Vitals"
            else "activity_logs"
        )
        res = supabase.table(tbl).select("*").order("date", desc=True).execute()
        if res.data:
            df_r = pd.DataFrame(res.data)
            st.dataframe(df_r, use_container_width=True)
            csv = df_r.to_csv(index=False).encode("utf-8")
            st.download_button(
                f"📥 Download {report_type}", csv, f"{tbl}.csv", "text/csv"
            )

    # 3. Universal Food Importer (De-duplicating Upsert Version)
    st.divider()
    st.subheader("📥 Universal Food Importer")
    st.write("Upload Kaggle CSVs here. Duplicates will be automatically updated.")

    import_type = st.selectbox(
        "Select Source Format",
        ["Daily Food & Nutrition (Kaggle)", "USDA FoodData Central"],
    )
    uploaded_file = st.file_uploader("Upload CSV File", type="csv")

    if uploaded_file is not None:
        try:
            # Safer CSV reading to handle weird characters or extra commas
            df_raw = pd.read_csv(uploaded_file, on_bad_lines="skip", engine="python")
            df_raw.columns = df_raw.columns.str.strip()

            if import_type == "Daily Food & Nutrition (Kaggle)":
                mapping = {
                    "Food_Item": "food_name",
                    "Calories (kcal)": "calories",
                    "Protein (g)": "protein_g",
                    "Carbohydrates (g)": "carbs_g",
                    "Fat (g)": "fat_g",
                    "Fiber (g)": "fiber_g",
                }
            else:
                mapping = {
                    "description": "food_name",
                    "Energy": "calories",
                    "Protein": "protein_g",
                    "Carbohydrate, by difference": "carbs_g",
                    "Total lipid (fat)": "fat_g",
                    "Fiber, total dietary": "fiber_g",
                }

            existing_cols = [col for col in mapping.keys() if col in df_raw.columns]
            df_mapped = df_raw[existing_cols].rename(columns=mapping)

            # Fill missing columns with 0.0 to prevent database errors
            for col in ["calories", "protein_g", "carbs_g", "fat_g", "fiber_g"]:
                if col not in df_mapped.columns:
                    df_mapped[col] = 0.0

            st.write(f"Previewing {len(df_mapped)} items:")
            st.dataframe(df_mapped.head())

            if st.button("🚀 Confirm Universal Import"):
                food_list = df_mapped.to_dict(orient="records")
                try:
                    # USES UPSERT TO PREVENT DUPLICATES
                    supabase.table("foods").upsert(
                        food_list, on_conflict="food_name"
                    ).execute()
                    st.success(f"Successfully processed {len(food_list)} items!")
                    st.balloons()
                except Exception as e:
                    st.error(f"Import Error: {e}")
        except Exception as outer_e:
            st.error(f"File Reading Error: {outer_e}")
