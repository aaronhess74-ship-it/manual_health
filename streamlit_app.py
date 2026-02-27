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

import pandas as pd
import altair as alt
from datetime import datetime

with tab1:
    # --- 1. SET TARGETS ---
    T_CAL, T_PRO, T_CHO, T_FAT = 2000, 150, 200, 70

    # --- 2. DATA FETCHING ---
    try:
        # Fetching nutrition logs (daily_logs)
        res_n = (
            supabase.table("daily_logs")
            .select("*")
            .order("log_date", desc=False)
            .execute()
        )
        df_n = pd.DataFrame(res_n.data) if res_n.data else pd.DataFrame()

        if not df_n.empty:
            # Merge Date and Time (matching our Health Metrics logic)
            df_n["ts"] = pd.to_datetime(
                df_n["log_date"].astype(str)
                + " "
                + df_n.get("log_time", "00:00:00").fillna("00:00:00").astype(str)
            )

            # --- 3. DAILY SUMMARY (TODAY) ---
            today_str = datetime.now().strftime("%Y-%m-%d")
            today_df = df_n[df_n["log_date"].astype(str) == today_str]

            s_cal = today_df["calories"].sum()
            s_pro = today_df["protein"].sum()
            s_cho = today_df["carbs"].sum()
            s_fat = today_df["fat"].sum()

            st.subheader(f"🍳 Today's Progress ({datetime.now().strftime('%b %d')})")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric(
                "Calories",
                f"{int(s_cal)}",
                f"{int(s_cal - T_CAL)} vs Goal",
                delta_color="inverse",
            )
            c2.metric("Protein", f"{int(s_pro)}g", f"{int(s_pro - T_PRO)}g")
            c3.metric("Carbs", f"{int(s_cho)}g", f"{int(s_cho - T_CHO)}g")
            c4.metric("Fat", f"{int(s_fat)}g", f"{int(s_fat - T_FAT)}g")

            # Simple Progress Bar
            progress = min(s_cal / T_CAL, 1.0)
            st.progress(progress, text=f"Calorie Intake: {int(progress * 100)}%")
            st.divider()

        # --- 4. LOG NEW MEAL ---
        st.subheader("🍕 Log Meal")
        with st.expander("Add New Entry", expanded=False):
            with st.form("meal_form", clear_on_submit=True):
                f1, f2 = st.columns(2)
                d_meal = f1.date_input("Date", datetime.now().date())
                t_meal = f2.time_input("Time", datetime.now().time())

                meal_name = st.text_input("Meal Name (e.g., Chicken Salad)")

                f3, f4, f5, f6 = st.columns(4)
                cal = f3.number_input("Calories", 0, 3000, 500)
                pro = f4.number_input("Protein (g)", 0, 300, 30)
                cho = f5.number_input("Carbs (g)", 0, 500, 40)
                fat = f6.number_input("Fat (g)", 0, 200, 15)

                if st.form_submit_button("Log Entry"):
                    supabase.table("daily_logs").insert(
                        {
                            "log_date": d_meal.isoformat(),
                            "log_time": t_meal.strftime("%H:%M:%S"),
                            "meal_name": meal_name,
                            "calories": cal,
                            "protein": pro,
                            "carbs": cho,
                            "fat": fat,
                        }
                    ).execute()
                    st.rerun()

        # --- 5. NUTRITION TRENDS ---
        if not df_n.empty:
            st.subheader("📈 Consumption Trends")
            # Aggregate by day for the chart
            daily_agg = (
                df_n.groupby("log_date")
                .agg({"calories": "sum", "protein": "sum"})
                .reset_index()
            )

            cal_chart = (
                alt.Chart(daily_agg)
                .mark_area(
                    line={"color": "#2ecc71"},
                    color=alt.Gradient(
                        gradient="linear",
                        stops=[
                            alt.GradientStop(color="#2ecc71", offset=0),
                            alt.GradientStop(color="transparent", offset=1),
                        ],
                        x1=1,
                        x2=1,
                        y1=1,
                        y2=0,
                    ),
                )
                .encode(
                    x=alt.X("log_date:T", title="Date"),
                    y=alt.Y("calories:Q", title="Total Calories"),
                    tooltip=["log_date", "calories"],
                )
                .properties(height=250)
            )

            st.altair_chart(cal_chart, use_container_width=True)

            # --- 6. MANAGE LOGS (Edit/Delete) ---
            with st.expander("🗑️ Manage Recent Meals"):
                if "edit_n_id" not in st.session_state:
                    st.session_state.edit_n_id = None
                recent_n = df_n.sort_values("ts", ascending=False).head(10)

                for _, row in recent_n.iterrows():
                    l_id = row["log_id"]
                    if st.session_state.edit_n_id == l_id:
                        with st.container(border=True):
                            st.write(f"**Editing: {row['meal_name']}**")
                            # Reuse same layout as health metrics for consistency
                            nc1, nc2, nc3 = st.columns(3)
                            n_date = nc1.date_input(
                                "Date", row["ts"].date(), key=f"nd_{l_id}"
                            )
                            n_time = nc2.time_input(
                                "Time", row["ts"].time(), key=f"nt_{l_id}"
                            )
                            n_name = nc3.text_input(
                                "Name", row["meal_name"], key=f"nn_{l_id}"
                            )

                            mc1, mc2, mc3, mc4 = st.columns(4)
                            n_cal = mc1.number_input(
                                "Cal", value=int(row["calories"]), key=f"nc_{l_id}"
                            )
                            n_pro = mc2.number_input(
                                "Pro", value=int(row["protein"]), key=f"np_{l_id}"
                            )
                            n_cho = mc3.number_input(
                                "Cho", value=int(row["carbs"]), key=f"nh_{l_id}"
                            )
                            n_fat = mc4.number_input(
                                "Fat", value=int(row["fat"]), key=f"nf_{l_id}"
                            )

                            sc1, sc2, _ = st.columns([1, 1, 4])
                            if sc1.button("✅ Save", key=f"nsv_{l_id}"):
                                supabase.table("daily_logs").update(
                                    {
                                        "log_date": n_date.isoformat(),
                                        "log_time": n_time.strftime("%H:%M:%S"),
                                        "meal_name": n_name,
                                        "calories": n_cal,
                                        "protein": n_pro,
                                        "carbs": n_cho,
                                        "fat": n_fat,
                                    }
                                ).eq("log_id", l_id).execute()
                                st.session_state.edit_n_id = None
                                st.rerun()
                            if sc2.button("Cancel", key=f"ncn_{l_id}"):
                                st.session_state.edit_n_id = None
                                st.rerun()
                    else:
                        r1, r2, r3 = st.columns([3, 5, 2])
                        r1.write(f"**{row['ts'].strftime('%b %d | %H:%M')}**")
                        r2.write(f"{row['meal_name']} ({int(row['calories'])} cal)")
                        eb1, eb2 = r3.columns(2)
                        if eb1.button("✏️", key=f"ned_{l_id}"):
                            st.session_state.edit_n_id = l_id
                            st.rerun()
                        if eb2.button("🗑️", key=f"ndl_{l_id}"):
                            supabase.table("daily_logs").delete().eq(
                                "log_id", l_id
                            ).execute()
                            st.rerun()

    except Exception as e:
        st.error(f"Nutrition Tab Error: {e}")

# --- TAB 2: HEALTH METRICS ---
import altair as alt
from datetime import datetime
import pandas as pd

with tab2:
    # --- 1. DATA FETCHING & COLUMN MERGING ---
    try:
        res = (
            supabase.table("health_metrics")
            .select("*")
            .order("date", desc=False)
            .execute()
        )
        df_v = pd.DataFrame(res.data) if res.data else pd.DataFrame()

        if not df_v.empty:
            # Merge the 'date' and 'time' columns for the app logic
            # If 'time' is null in your DB, it defaults to midnight
            df_v["ts"] = pd.to_datetime(
                df_v["date"].astype(str)
                + " "
                + df_v["time"].fillna("00:00:00").astype(str)
            )

            # Format the X-axis labels: hide 00:00, show actual times
            def format_label(dt):
                if dt.hour == 0 and dt.minute == 0 and dt.second == 0:
                    return dt.strftime("%b %d")
                return dt.strftime("%b %d | %H:%M")

            df_v["chart_label"] = df_v["ts"].apply(format_label)

            # --- 2. LATEST METRICS (Current Status) ---
            st.subheader("📊 Current Status")

            def get_latest(col):
                valid = df_v.dropna(subset=[col]).sort_values("ts")
                return valid.iloc[-1] if not valid.empty else None

            l_bp, l_gl, l_wt = (
                get_latest("blood_pressure_systolic"),
                get_latest("blood_glucose"),
                get_latest("weight_lb"),
            )

            m1, m2, m3 = st.columns(3)
            if l_bp is not None:
                s, d = (
                    int(l_bp["blood_pressure_systolic"]),
                    int(l_bp["blood_pressure_diastolic"]),
                )
                bp_emoji = (
                    "🟢" if s < 120 and d < 80 else "🟡" if s < 130 and d < 80 else "🔴"
                )
                m1.metric("Latest BP", f"{bp_emoji} {s}/{d}")
                m1.caption(f"Logged: {l_bp['ts'].strftime('%b %d at %H:%M')}")

            if l_gl is not None:
                g = int(l_gl["blood_glucose"])
                gl_emoji = "🟢" if g < 100 else "🟡" if g < 126 else "🔴"
                m2.metric("Latest Glucose", f"{gl_emoji} {g} mg/dL")
                m2.caption(f"Logged: {l_gl['ts'].strftime('%b %d at %H:%M')}")

            if l_wt is not None:
                m3.metric("Latest Weight", f"⚖️ {l_wt['weight_lb']} lbs")
                m3.caption(f"Logged: {l_wt['ts'].strftime('%b %d at %H:%M')}")

            st.divider()

        # --- 3. INPUT FORMS (Split Date/Time for DB) ---
        st.subheader("➕ Log New Measurement")
        col_bp, col_wt, col_gl = st.columns(3)
        now = datetime.now()

        with col_bp:
            with st.expander("❤️ Blood Pressure", expanded=False):
                d_bp = st.date_input("Date", now.date(), key="d_bp_v10")
                t_bp = st.time_input("Time", now.time(), key="t_bp_v10")
                sys = st.number_input("Systolic", 0, 300, 120, key="sys_v10")
                dia = st.number_input("Diastolic", 0, 200, 80, key="dia_v10")
                n_bp = st.text_input("Notes", key="n_bp_v10")
                if st.button("Log BP", key="btn_bp_v10"):
                    supabase.table("health_metrics").insert(
                        {
                            "date": d_bp.isoformat(),
                            "time": t_bp.strftime("%H:%M:%S"),
                            "blood_pressure_systolic": sys,
                            "blood_pressure_diastolic": dia,
                            "notes": n_bp,
                        }
                    ).execute()
                    st.rerun()

        with col_wt:
            with st.expander("⚖️ Weight", expanded=False):
                d_wt = st.date_input("Date", now.date(), key="d_wt_v10")
                t_wt = st.time_input("Time", now.time(), key="t_wt_v10")
                w_wt = st.number_input(
                    "Weight (lbs)", 0.0, 500.0, 180.0, key="w_wt_v10"
                )
                n_wt = st.text_input("Notes", key="n_wt_v10")
                if st.button("Log Weight", key="btn_wt_v10"):
                    supabase.table("health_metrics").insert(
                        {
                            "date": d_wt.isoformat(),
                            "time": t_wt.strftime("%H:%M:%S"),
                            "weight_lb": w_wt,
                            "notes": n_wt,
                        }
                    ).execute()
                    st.rerun()

        with col_gl:
            with st.expander("🩸 Glucose", expanded=False):
                d_gl = st.date_input("Date", now.date(), key="d_gl_v10")
                t_gl = st.time_input("Time", now.time(), key="t_gl_v10")
                g_gl = st.number_input("Glucose", 0, 500, 100, key="g_gl_v10")
                n_gl = st.text_input("Notes", key="n_gl_v10")
                if st.button("Log Glucose", key="btn_gl_v10"):
                    supabase.table("health_metrics").insert(
                        {
                            "date": d_gl.isoformat(),
                            "time": t_gl.strftime("%H:%M:%S"),
                            "blood_glucose": g_gl,
                            "notes": n_gl,
                        }
                    ).execute()
                    st.rerun()

        if not df_v.empty:
            st.divider()

            # --- 4. THE CHARTS (Ordinal Axis with Tooltips) ---
            def create_health_chart(data, y_col, color, y_domain, title):
                chart_df = data.dropna(subset=[y_col]).sort_values("ts")
                base = alt.Chart(chart_df).encode(
                    x=alt.X("chart_label:O", title="Entry", sort=None),
                    tooltip=[
                        alt.Tooltip("chart_label:N", title="Logged At"),
                        alt.Tooltip(f"{y_col}:Q", title=title),
                    ],
                )
                line = base.mark_line(color=color, strokeWidth=3).encode(
                    y=alt.Y(f"{y_col}:Q", scale=alt.Scale(domain=y_domain))
                )
                points = base.mark_circle(color=color, size=60).encode(y=f"{y_col}:Q")
                labels = base.mark_text(dy=-15, color="white").encode(
                    y=f"{y_col}:Q", text=alt.Text(f"{y_col}:Q", format=".1f")
                )
                return (line + points + labels).properties(height=300)

            st.write("**Weight (150 - 300 lbs)**")
            st.altair_chart(
                create_health_chart(df_v, "weight_lb", "#3498db", [150, 300], "Weight"),
                use_container_width=True,
            )

            st.write("**Glucose (0 - 200 mg/dL)**")
            st.altair_chart(
                create_health_chart(
                    df_v, "blood_glucose", "#f1c40f", [0, 200], "Glucose"
                ),
                use_container_width=True,
            )

            st.write("**Blood Pressure (0 - 250 mmHg)**")
            bp_df = df_v.dropna(subset=["blood_pressure_systolic"]).sort_values("ts")
            bp_base = alt.Chart(bp_df).encode(x=alt.X("chart_label:O", sort=None))
            bp_range = bp_base.mark_bar(width=10, color="#e74c3c", opacity=0.6).encode(
                y=alt.Y("blood_pressure_diastolic:Q", scale=alt.Scale(domain=[0, 250])),
                y2="blood_pressure_systolic:Q",
            )
            st.altair_chart((bp_range).properties(height=300), use_container_width=True)

            # --- 5. MANAGE ENTRIES (With Date/Time Splitting) ---
            with st.expander("🗑️ Manage & Edit Recent Entries"):
                if "editing_id" not in st.session_state:
                    st.session_state.editing_id = None
                recent = df_v.sort_values("ts", ascending=False).head(15)

                for _, row in recent.iterrows():
                    m_id = row["metric_id"]
                    if st.session_state.editing_id == m_id:
                        with st.container(border=True):
                            st.write(f"**Editing Entry**")
                            ec1, ec2, ec3 = st.columns(3)
                            e_date = ec1.date_input(
                                "Date", row["ts"].date(), key=f"edat_{m_id}"
                            )
                            e_time = ec2.time_input(
                                "Time", row["ts"].time(), key=f"etim_{m_id}"
                            )
                            e_notes = ec3.text_input(
                                "Notes", row["notes"] or "", key=f"enot_{m_id}"
                            )

                            vc1, vc2 = st.columns(2)
                            e_w = vc1.number_input(
                                "Weight",
                                value=float(row["weight_lb"])
                                if not pd.isna(row["weight_lb"])
                                else 0.0,
                                key=f"ewgt_{m_id}",
                            )
                            e_g = vc2.number_input(
                                "Glucose",
                                value=int(row["blood_glucose"])
                                if not pd.isna(row["blood_glucose"])
                                else 0,
                                key=f"eglu_{m_id}",
                            )

                            sc1, sc2, _ = st.columns([1, 1, 4])
                            if sc1.button("✅ Save", key=f"btnsave_{m_id}"):
                                up_data = {
                                    "date": e_date.isoformat(),
                                    "time": e_time.strftime("%H:%M:%S"),
                                    "notes": e_notes,
                                }
                                if not pd.isna(row["weight_lb"]):
                                    up_data["weight_lb"] = e_w
                                if not pd.isna(row["blood_glucose"]):
                                    up_data["blood_glucose"] = e_g

                                supabase.table("health_metrics").update(up_data).eq(
                                    "metric_id", m_id
                                ).execute()
                                st.session_state.editing_id = None
                                st.rerun()
                            if sc2.button("Cancel", key=f"btncan_{m_id}"):
                                st.session_state.editing_id = None
                                st.rerun()
                    else:
                        c1, c2, c3 = st.columns([3, 5, 2])
                        c1.write(f"**{row['chart_label']}**")
                        vals = []
                        if not pd.isna(row["weight_lb"]):
                            vals.append(f"{row['weight_lb']} lbs")
                        if not pd.isna(row["blood_glucose"]):
                            vals.append(f"Glu: {row['blood_glucose']}")
                        if not pd.isna(row["blood_pressure_systolic"]):
                            vals.append(
                                f"BP: {int(row['blood_pressure_systolic'])}/{int(row['blood_pressure_diastolic'])}"
                            )
                        c2.write(" | ".join(vals))
                        eb1, eb2 = c3.columns(2)
                        if eb1.button("✏️", key=f"ebtn_{m_id}"):
                            st.session_state.editing_id = m_id
                            st.rerun()
                        if eb2.button("🗑️", key=f"dbtn_{m_id}"):
                            supabase.table("health_metrics").delete().eq(
                                "metric_id", m_id
                            ).execute()
                            st.rerun()

    except Exception as e:
        st.error(f"Error drawing dashboard: {e}")

# --- TAB 3: ACTIVITY (UI SWAP FIX) ---
with tab3:
    st.subheader("🏃 Log Activity")

    # 1. Radio moves OUTSIDE the form to trigger the UI refresh
    act_type = st.radio(
        "Select Activity Type",
        ["Strength", "Cardio", "Endurance"],
        horizontal=True,
        key="activity_selector",
    )

    # 2. The Form begins AFTER the radio button
    with st.form("act_form", clear_on_submit=True):
        a_date = st.date_input("Date", datetime.now().date())
        name = st.text_input("Exercise Name")

        c1, c2, c3 = st.columns(3)

        # Initialize defaults
        dur, dist, sets, reps, weight_ex = 0.0, 0.0, 0, 0, 0

        # UI now swaps instantly when you click the radio buttons above
        if act_type == "Strength":
            sets = c1.number_input("Sets", min_value=0, value=3)
            reps = c2.number_input("Reps", min_value=0, value=10)
            weight_ex = c3.number_input("Weight (lbs)", min_value=0, value=0)

        elif act_type == "Cardio":
            dur = c1.number_input("Duration (mins)", min_value=0.0, value=30.0)
            dist = c2.number_input("Distance (miles)", min_value=0.0, value=0.0)

        elif act_type == "Endurance":
            dur = c1.number_input("Duration (mins)", min_value=0.0, value=30.0)
            sets = c2.number_input("Sets", min_value=0, value=0)
            reps = c3.number_input("Reps", min_value=0, value=0)

        if st.form_submit_button("Log Activity"):
            if name:
                supabase.table("activity_logs").insert(
                    {
                        "date": str(a_date),
                        "exercise_name": name,
                        "activity_type": act_type,
                        "duration_min": dur,
                        "distance_miles": dist,
                        "sets": sets,
                        "reps": reps,
                        "weight_lbs": weight_ex,
                    }
                ).execute()
                st.rerun()
            else:
                st.warning("Please enter an exercise name.")

    st.divider()
    # (Rest of history table logic follows below...)
    try:
        a_res = (
            supabase.table("activity_logs")
            .select("*")
            .order("date", desc=False)
            .execute()
        )
        if a_res.data:
            df_a = pd.DataFrame(a_res.data)
            st.subheader("📜 Activity History")
            st.dataframe(
                df_a.sort_values(by="date", ascending=False),
                use_container_width=True,
                column_order=[
                    "date",
                    "exercise_name",
                    "activity_type",
                    "sets",
                    "reps",
                    "weight_lbs",
                    "duration_min",
                    "distance_miles",
                ],
            )
    except:
        pass

# --- TAB 4: REPORTS & EXPORTS (FULL RESTORED) ---
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

            if st.button("🚀 Confirm Upsert Import"):
                supabase.table("foods").upsert(
                    df_mapped.to_dict(orient="records"), on_conflict="food_name"
                ).execute()
                st.success("Import Successful!")
        except Exception as e:
            st.error(f"Error: {e}")

    st.divider()
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
