import streamlit as st
from supabase import create_client
from datetime import datetime, timedelta
import pandas as pd
import altair as alt
import io

# --- 1. DATABASE CONNECTION ---
url, key = st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

# --- 2. PAGE CONFIG ---
st.set_page_config(
    page_title="Health & Nutrition Master",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --- 3. SESSION STATE MANAGEMENT ---
if "edit_mode" not in st.session_state:
    st.session_state.edit_mode = None
if "edit_data" not in st.session_state:
    st.session_state.edit_data = {}
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# --- 4. AUTHENTICATION ---
if not st.session_state.authenticated:
    st.title("🔒 Private Health System")
    with st.form("login_form"):
        pwd = st.text_input("Access Key", type="password")
        if st.form_submit_button("Enter System"):
            if pwd == st.secrets["ADMIN_PASSWORD"]:
                st.session_state.update({"authenticated": True, "is_admin": True})
                st.rerun()
            elif pwd == st.secrets["GUEST_PASSWORD"]:
                st.session_state.update({"authenticated": True, "is_admin": False})
                st.rerun()
            else:
                st.error("Invalid Key")
    st.stop()

# --- 5. USER SCOPING ---
# Dynamic switching for Admin to view Guest data if needed
active_user = (
    "admin"
    if (
        st.session_state.is_admin
        and st.sidebar.radio("🔎 User View", ["Admin", "Guest"]) == "Admin"
    )
    else "guest"
)
record_owner = "admin" if st.session_state.is_admin else "guest"

# --- 6. NAVIGATION TABS ---
tab1, tab2, tab3, tab4 = st.tabs(
    ["🍴 Nutrition", "🩺 Health Metrics", "🏃 Activity", "📊 Reports"]
)

# =================================================================
# TAB 1: NUTRITION
# =================================================================
with tab1:
    # --- A. DAILY METRICS (THE TOP BAR) ---
    try:
        dv = (
            supabase.table("daily_variance")
            .select("*")
            .eq("user_id", active_user)
            .order("date", desc=True)
            .limit(1)
            .execute()
            .data
        )
        if dv:
            d = dv[0]
            st.subheader(f"Nutrition Snapshot: {d['date']}")
            m1, m2, m3, m4, m5 = st.columns(5)

            # Goal Logic: 1800 Cal, 160g Pro, 100g Net Carb, 60g Fat, 30g Fiber
            cal_left = 1800 - (d["total_calories"] or 0)
            m1.metric(
                "Calories",
                f"{int(d['total_calories'] or 0)}",
                f"{int(cal_left)} Left",
                delta_color="normal",
            )

            pro_diff = (d["total_protein"] or 0) - 160
            m2.metric(
                "Protein",
                f"{int(d['total_protein'] or 0)}g",
                f"{int(pro_diff)}g vs Goal",
            )

            carb_diff = (d["total_net_carbs"] or 0) - 100
            m3.metric(
                "Net Carbs",
                f"{int(d['total_net_carbs'] or 0)}g",
                f"{int(carb_diff)}g Over",
                delta_color="inverse",
            )

            fat_left = 60 - (d["total_fat"] or 0)
            m4.metric("Fat", f"{int(d['total_fat'] or 0)}g", f"{int(fat_left)}g Left")

            fib_diff = (d["total_fiber"] or 0) - 30
            m5.metric(
                "Fiber", f"{int(d['total_fiber'] or 0)}g", f"{int(fib_diff)}g vs Min"
            )
    except Exception as e:
        st.info("Log your first meal to see daily totals.")

    st.divider()

    # --- B. QUICK LOG (MOST FREQUENT) ---
    st.markdown("### ⚡ Quick Log (Recent Favorites)")
    freq_query = (
        supabase.table("daily_logs")
        .select("foods(food_name, food_id)")
        .eq("user_id", active_user)
        .execute()
        .data
    )
    if freq_query:
        food_names = [x["foods"]["food_name"] for x in freq_query if x.get("foods")]
        if food_names:
            top_5 = pd.Series(food_names).value_counts().head(5).index.tolist()
            q_cols = st.columns(len(top_5))
            for i, name in enumerate(top_5):
                if q_cols[i].button(f"➕ {name}"):
                    f_id = (
                        supabase.table("foods")
                        .select("food_id")
                        .eq("food_name", name)
                        .execute()
                        .data[0]["food_id"]
                    )
                    supabase.table("daily_logs").insert(
                        {
                            "food_id": f_id,
                            "servings": 1.0,
                            "log_date": str(datetime.now().date()),
                            "user_id": record_owner,
                            "meal_name": "Quick Log",
                        }
                    ).execute()
                    st.rerun()

    st.divider()

    # --- C. DETAILED LOGGING FORM ---
    st.markdown("### 📝 Entry Details")
    ed_n = st.session_state.edit_data if st.session_state.edit_mode == "nutr" else {}

    n_col1, n_col2 = st.columns([1, 1])
    with n_col1:
        entry_type = st.radio(
            "Log Method", ["Database Search", "Manual Macro Entry"], horizontal=True
        )

    with st.form("nutrition_master_form"):
        if entry_type == "Database Search":
            all_foods = (
                supabase.table("foods").select("*").order("food_name").execute().data
            )
            f_names = [f["food_name"] for f in all_foods]
            default_f = (
                f_names.index(ed_n["food_name"])
                if "food_name" in ed_n and ed_n["food_name"] in f_names
                else 0
            )

            sel_food = st.selectbox("Select Item", options=f_names, index=default_f)
            servings = st.number_input(
                "Servings", 0.1, 20.0, float(ed_n.get("servings", 1.0)), step=0.1
            )
        else:
            custom_name = st.text_input(
                "Custom Item Name", value=ed_n.get("food_name", "")
            )
            mc1, mc2, mc3, mc4 = st.columns(4)
            c_cal = mc1.number_input("Calories", 0, 3000, 0)
            c_pro = mc2.number_input("Protein (g)", 0, 300, 0)
            c_carb = mc3.number_input("Net Carbs (g)", 0, 300, 0)
            c_fat = mc4.number_input("Fat (g)", 0, 300, 0)

        meal_time = st.text_input(
            "Meal Category (e.g., Breakfast, Post-Workout)",
            value=ed_n.get("meal_name", ""),
        )

        submit_nutr = st.form_submit_button("Update Record" if ed_n else "Log Food")

        if submit_nutr:
            if entry_type == "Database Search":
                f_obj = next(
                    item for item in all_foods if item["food_name"] == sel_food
                )
                target_food_id = f_obj["food_id"]
            else:
                # Add new custom food to library
                new_f = (
                    supabase.table("foods")
                    .insert(
                        {
                            "food_name": custom_name,
                            "calories": c_cal,
                            "protein_g": c_pro,
                            "carbs_g": c_carb,
                            "fat_g": c_fat,
                            "is_custom": True,
                        }
                    )
                    .execute()
                )
                target_food_id = new_f.data[0]["food_id"]
                servings = 1.0

            payload = {
                "food_id": target_food_id,
                "servings": servings,
                "log_date": str(datetime.now().date()),
                "user_id": record_owner,
                "meal_name": meal_time,
            }

            if ed_n:
                supabase.table("daily_logs").update(payload).eq(
                    "log_id", ed_n["log_id"]
                ).execute()
            else:
                supabase.table("daily_logs").insert(payload).execute()

            st.session_state.update({"edit_mode": None, "edit_data": {}})
            st.rerun()

    # --- D. TODAY'S RECENT LOGS ---
    today_logs = (
        supabase.table("daily_logs")
        .select("*, foods(*)")
        .eq("log_date", str(datetime.now().date()))
        .eq("user_id", active_user)
        .order("log_id", desc=True)
        .execute()
        .data
    )
    if today_logs:
        st.markdown("#### Recently Logged Today")
        for row in today_logs:
            r1, r2, r3, r4 = st.columns([4, 2, 1, 1])
            r1.write(f"**{row['meal_name'] or 'Entry'}**: {row['foods']['food_name']}")
            r2.write(f"{int(row['foods']['calories'] * row['servings'])} kcal")
            if r3.button("📝", key=f"edit_n_{row['log_id']}"):
                st.session_state.update(
                    {
                        "edit_mode": "nutr",
                        "edit_data": {**row, "food_name": row["foods"]["food_name"]},
                    }
                )
                st.rerun()
            if r4.button("🗑️", key=f"del_n_{row['log_id']}"):
                supabase.table("daily_logs").delete().eq(
                    "log_id", row["log_id"]
                ).execute()
                st.rerun()

# =================================================================
# TAB 2: HEALTH METRICS
# =================================================================
with tab2:
    st.subheader("🩺 Clinical Vital Signs")
    ed_h = st.session_state.edit_data if st.session_state.edit_mode == "health" else {}

    # --- A. FORM WITH ICONS AND SPECIFIC INPUTS ---
    with st.form("health_master_form"):
        h_row1 = st.columns(3)
        w_val = h_row1[0].number_input(
            "⚖️ Weight (lbs)", 50.0, 500.0, float(ed_h.get("weight_lb", 185.0)), step=0.1
        )
        s_val = h_row1[1].number_input(
            "🩸 Systolic BP (Upper)",
            50,
            250,
            int(ed_h.get("blood_pressure_systolic", 120)),
        )
        d_val = h_row1[2].number_input(
            "🩸 Diastolic BP (Lower)",
            30,
            160,
            int(ed_h.get("blood_pressure_diastolic", 80)),
        )

        h_row2 = st.columns(2)
        g_val = h_row2[0].number_input(
            "🧪 Blood Glucose (mg/dL)",
            0.0,
            600.0,
            float(ed_h.get("blood_glucose", 95.0)),
            step=1.0,
        )
        n_val = h_row2[1].text_input(
            "📝 Observations / Notes", value=ed_h.get("notes", "")
        )

        submit_health = st.form_submit_button(
            "🚨 Update Record" if ed_h else "💾 Save Vital Signs"
        )

        if submit_health:
            h_payload = {
                "date": str(datetime.now().date()),
                "time": datetime.now().strftime("%H:%M:%S"),
                "weight_lb": w_val,
                "blood_pressure_systolic": s_val,
                "blood_pressure_diastolic": d_val,
                "blood_glucose": g_val,
                "notes": n_val,
                "user_id": record_owner,
            }
            if ed_h:
                supabase.table("health_metrics").update(h_payload).eq(
                    "metric_id", ed_h["metric_id"]
                ).execute()
            else:
                supabase.table("health_metrics").insert(h_payload).execute()
            st.session_state.update({"edit_mode": None, "edit_data": {}})
            st.rerun()

    st.divider()

    # --- B. HIGH-PRECISION TREND CHARTS ---
    st.markdown("### 📊 Health Trends & Analytics")
    h_history = (
        supabase.table("health_metrics")
        .select("*")
        .eq("user_id", active_user)
        .order("date", desc=False)
        .execute()
        .data
    )

    if h_history:
        df_h = pd.DataFrame(h_history)
        df_h["timestamp"] = pd.to_datetime(
            df_h["date"].astype(str) + " " + df_h["time"].fillna("00:00:00").astype(str)
        )

        # Chart 1: Blood Pressure (Explicit scaling and stroke)
        bp_base = (
            alt.Chart(df_h)
            .transform_fold(
                ["blood_pressure_systolic", "blood_pressure_diastolic"],
                as_=["Measurement", "Value"],
            )
            .encode(
                x=alt.X(
                    "timestamp:T",
                    title=None,
                    axis=alt.Axis(format="%b %d %H:%M", grid=False, labelFlush=True),
                ),
                y=alt.Y("Value:Q", scale=alt.Scale(domain=[40, 200]), title="mmHg"),
                color=alt.Color(
                    "Measurement:N",
                    scale=alt.Scale(range=["#e74c3c", "#3498db"]),
                    legend=alt.Legend(orient="top-left"),
                ),
            )
        )
        bp_chart = bp_base.mark_line(
            strokeWidth=3, interpolate="monotone"
        ) + bp_base.mark_circle(size=60)

        # Chart 2: Glucose (Area Gradient)
        glu_chart = (
            alt.Chart(df_h)
            .mark_area(
                line={"color": "orange"},
                color=alt.Gradient(
                    gradient="linear",
                    stops=[
                        alt.GradientStop(color="white", offset=0),
                        alt.GradientStop(color="orange", offset=1),
                    ],
                    x1=1,
                    x2=1,
                    y1=1,
                    y2=0,
                ),
            )
            .encode(
                x=alt.X(
                    "timestamp:T", title=None, axis=alt.Axis(labels=False, ticks=False)
                ),
                y=alt.Y(
                    "blood_glucose:Q",
                    scale=alt.Scale(domain=[60, 250]),
                    title="Glucose",
                ),
            )
        )

        # Chart 3: Weight (Dynamic focus)
        w_min, w_max = df_h["weight_lb"].min() - 2, df_h["weight_lb"].max() + 2
        weight_chart = (
            alt.Chart(df_h)
            .mark_line(color="#27ae60", point=True)
            .encode(
                x=alt.X("timestamp:T", title="Measurement Timeline"),
                y=alt.Y(
                    "weight_lb:Q",
                    scale=alt.Scale(domain=[w_min, w_max]),
                    title="Weight (lbs)",
                ),
            )
        )

        st.altair_chart(
            alt.vconcat(bp_chart, glu_chart, weight_chart)
            .properties(spacing=10)
            .configure_view(strokeOpacity=0),
            use_container_width=True,
        )

# =================================================================
# TAB 3: ACTIVITY
# =================================================================
with tab3:
    st.subheader("🏃 Exercise & Training Log")
    ed_a = st.session_state.edit_data if st.session_state.edit_mode == "act" else {}

    # Restored Multi-Category Radio
    act_type = st.radio(
        "Training Type",
        ["Strength", "Cardio", "Endurance"],
        horizontal=True,
        index=["Strength", "Cardio", "Endurance"].index(
            ed_a.get("activity_category", "Strength")
        ),
    )

    with st.form("activity_master_form"):
        exe_name = st.text_input(
            "Exercise / Activity Name", value=ed_a.get("exercise_name", "")
        )

        ac1, ac2, ac3 = st.columns(3)
        if act_type == "Strength":
            sets = ac1.number_input("Sets", 0, 50, int(ed_a.get("sets", 0)))
            reps = ac2.number_input("Reps", 0, 500, int(ed_a.get("reps", 0)))
            weight_used = ac3.number_input(
                "Weight (lbs)", 0, 2000, int(ed_a.get("weight_lb", 0))
            )
            dur_min, dist_mi = 0, 0.0
        elif act_type == "Cardio":
            dur_min = ac1.number_input(
                "Duration (min)", 0, 1440, int(ed_a.get("duration_min", 0))
            )
            dist_mi = ac2.number_input(
                "Distance (miles)", 0.0, 500.0, float(ed_a.get("distance_miles", 0.0))
            )
            sets, reps, weight_used = 0, 0, 0
        else:  # Endurance
            dur_min = ac1.number_input(
                "Duration (min)", 0, 1440, int(ed_a.get("duration_min", 0))
            )
            sets = ac2.number_input("Sets (Rounds)", 0, 100, int(ed_a.get("sets", 0)))
            reps = ac3.number_input("Total Reps", 0, 5000, int(ed_a.get("reps", 0)))
            dist_mi, weight_used = 0.0, 0

        submit_act = st.form_submit_button(
            "📥 Update Activity" if ed_a else "🚀 Log Workout"
        )

        if submit_act:
            a_payload = {
                "log_date": str(datetime.now().date()),
                "exercise_name": exe_name,
                "activity_category": act_type,
                "sets": sets,
                "reps": reps,
                "weight_lb": weight_used,
                "duration_min": dur_min,
                "distance_miles": dist_mi,
                "user_id": record_owner,
            }
            if ed_a:
                supabase.table("activity_logs").update(a_payload).eq(
                    "id", ed_a["id"]
                ).execute()
            else:
                supabase.table("activity_logs").insert(a_payload).execute()
            st.session_state.update({"edit_mode": None, "edit_data": {}})
            st.rerun()

    # Activity History
    act_history = (
        supabase.table("activity_logs")
        .select("*")
        .eq("user_id", active_user)
        .order("log_date", desc=True)
        .limit(10)
        .execute()
        .data
    )
    if act_history:
        for a_row in act_history:
            ar1, ar2, ar3, ar4 = st.columns([4, 2, 1, 1])
            ar1.write(
                f"**{a_row['log_date']}**: {a_row['exercise_name']} ({a_row['activity_category']})"
            )
            if ar3.button("📝", key=f"edit_a_{a_row['id']}"):
                st.session_state.update({"edit_mode": "act", "edit_data": a_row})
                st.rerun()
            if ar4.button("🗑️", key=f"del_a_{a_row['id']}"):
                supabase.table("activity_logs").delete().eq("id", a_row["id"]).execute()
                st.rerun()

# =================================================================
# TAB 4: REPORTS
# =================================================================
with tab4:
    st.subheader("📊 Master System Export")

    target_table = st.selectbox(
        "Select Dataset to Export",
        ["daily_logs", "health_metrics", "activity_logs", "foods", "daily_variance"],
    )

    export_query = supabase.table(target_table).select("*")
    if target_table not in ["foods", "daily_variance"]:
        export_query = export_query.eq("user_id", active_user)

    data_to_export = export_query.execute().data
    if data_to_export:
        df_export = pd.DataFrame(data_to_export)
        st.dataframe(df_export, use_container_width=True)

        # Proper CSV Buffer for reliable downloads
        csv_buffer = io.StringIO()
        df_export.to_csv(csv_buffer, index=False)
        st.download_button(
            label=f"📥 Download {target_table.replace('_', ' ').title()} as CSV",
            data=csv_buffer.getvalue(),
            file_name=f"{target_table}_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )
    else:
        st.warning("No records found for the current selection.")
