import streamlit as st
from supabase import create_client
from datetime import datetime, timedelta
import pandas as pd
import altair as alt
import io

# --- 1. DATABASE CONNECTION ---
# Using the specific secrets keys established for your Supabase instance
url, key = st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

# --- 2. PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Health & Nutrition Master System",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --- 3. SESSION STATE MANAGEMENT ---
# Essential for maintaining edit states and multi-step forms
if "edit_mode" not in st.session_state:
    st.session_state.edit_mode = None
if "edit_data" not in st.session_state:
    st.session_state.edit_data = {}
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# --- 4. AUTHENTICATION GATING ---
if not st.session_state.authenticated:
    st.title("🔒 Private Health Cloud Access")
    with st.form("system_auth"):
        access_key = st.text_input("System Access Key", type="password")
        if st.form_submit_button("Authenticate"):
            if access_key == st.secrets["ADMIN_PASSWORD"]:
                st.session_state.update({"authenticated": True, "is_admin": True})
                st.rerun()
            elif access_key == st.secrets["GUEST_PASSWORD"]:
                st.session_state.update({"authenticated": True, "is_admin": False})
                st.rerun()
            else:
                st.error("Access Denied.")
    st.stop()

# --- 5. DYNAMIC USER SCOPING ---
# Admin can toggle between views; Guests are locked to their own data
if st.session_state.is_admin:
    view_option = st.sidebar.radio("🔎 System View", ["Admin Records", "Guest Records"])
    active_user = "admin" if view_option == "Admin Records" else "guest"
else:
    active_user = "guest"

# The person currently SAVING the data
record_owner = "admin" if st.session_state.is_admin else "guest"

# --- 6. NAVIGATION ---
tab1, tab2, tab3, tab4 = st.tabs(
    ["🍴 Nutrition", "🩺 Health Metrics", "🏃 Activity", "📊 Master Reports"]
)

# =================================================================
# TAB 1: NUTRITION (REBUILT WITH FULL LOGIC & RECENT LOGS)
# =================================================================
with tab1:
    # A. Daily Variance Summary
    try:
        dv_query = (
            supabase.table("daily_variance")
            .select("*")
            .eq("user_id", active_user)
            .order("date", desc=True)
            .limit(1)
            .execute()
        )
        if dv_query.data:
            d = dv_query.data[0]
            st.subheader(f"Nutrition Snapshot: {d['date']}")
            m1, m2, m3, m4, m5 = st.columns(5)

            # Metric Calculation Logic
            cal_val = d.get("total_calories", 0) or 0
            pro_val = d.get("total_protein", 0) or 0
            carb_val = d.get("total_net_carbs", 0) or 0
            fat_val = d.get("total_fat", 0) or 0
            fib_val = d.get("total_fiber", 0) or 0

            m1.metric("Calories", f"{int(cal_val)}", f"{int(1800 - cal_val)} Left")
            m2.metric("Protein", f"{int(pro_val)}g", f"{int(pro_val - 160)}g Goal")
            m3.metric(
                "Net Carbs",
                f"{int(carb_val)}g",
                f"{int(carb_val - 100)}g Over",
                delta_color="inverse",
            )
            m4.metric("Fat", f"{int(fat_val)}g", f"{int(60 - fat_val)}g Left")
            m5.metric("Fiber", f"{int(fib_val)}g", f"{int(fib_val - 30)}g Min")
    except Exception as e:
        st.info("Metrics will populate once food is logged today.")

    st.divider()

    # B. Detailed Entry Form
    st.markdown("### 📝 Detailed Food Entry")
    ed_n = st.session_state.edit_data if st.session_state.edit_mode == "nutr" else {}

    log_method = st.radio(
        "Logging Method", ["Database Search", "Manual Macro Entry"], horizontal=True
    )

    with st.form("nutrition_master_form"):
        if log_method == "Database Search":
            food_db = (
                supabase.table("foods").select("*").order("food_name").execute().data
            )
            food_names = [f["food_name"] for f in food_db]
            default_idx = (
                food_names.index(ed_n["food_name"])
                if "food_name" in ed_n and ed_n["food_name"] in food_names
                else 0
            )

            selected_food_name = st.selectbox(
                "Select Item", options=food_names, index=default_idx
            )
            servings_count = st.number_input(
                "Servings", 0.1, 20.0, float(ed_n.get("servings", 1.0)), step=0.1
            )
        else:
            custom_food_name = st.text_input(
                "New Item Name", value=ed_n.get("food_name", "")
            )
            c1, c2, c3, c4, c5 = st.columns(5)
            val_cal = c1.number_input("Calories", 0, 3000, 0)
            val_pro = c2.number_input("Protein (g)", 0, 300, 0)
            val_net = c3.number_input("Net Carbs (g)", 0, 300, 0)
            val_fat = c4.number_input("Fat (g)", 0, 300, 0)
            val_fib = c5.number_input("Fiber (g)", 0, 100, 0)

        meal_cat = st.text_input(
            "Meal Name (e.g., Breakfast)", value=ed_n.get("meal_name", "")
        )

        if st.form_submit_button("Update Log Entry" if ed_n else "💾 Save Entry"):
            if log_method == "Database Search":
                f_match = next(
                    item for item in food_db if item["food_name"] == selected_food_name
                )
                final_food_id = f_match["food_id"]
                final_servings = servings_count
            else:
                # Add new food to library using specific target keys
                new_f_res = (
                    supabase.table("foods")
                    .insert(
                        {
                            "food_name": custom_food_name,
                            "calories": val_cal,
                            "protein_g": val_pro,
                            "carbs_g": val_net,
                            "fat_g": val_fat,
                            "fiber_g": val_fib,
                            "is_custom": True,
                        }
                    )
                    .execute()
                )
                final_food_id = new_f_res.data[0]["food_id"]
                final_servings = 1.0

            n_payload = {
                "food_id": final_food_id,
                "servings": final_servings,
                "log_date": str(datetime.now().date()),
                "user_id": record_owner,
                "meal_name": meal_cat,
            }

            if ed_n:
                supabase.table("daily_logs").update(n_payload).eq(
                    "log_id", ed_n["log_id"]
                ).execute()
            else:
                supabase.table("daily_logs").insert(n_payload).execute()

            st.session_state.update({"edit_mode": None, "edit_data": {}})
            st.rerun()

    # C. Today's Log List
    st.markdown("#### Today's Records")
    day_logs = (
        supabase.table("daily_logs")
        .select("*, foods(*)")
        .eq("log_date", str(datetime.now().date()))
        .eq("user_id", active_user)
        .order("log_id", desc=True)
        .execute()
        .data
    )
    if day_logs:
        for row in day_logs:
            cols = st.columns([4, 2, 1, 1])
            cols[0].write(
                f"**{row['meal_name'] or 'Entry'}**: {row['foods']['food_name']}"
            )
            cols[1].write(f"{int(row['foods']['calories'] * row['servings'])} kcal")
            if cols[2].button("📝", key=f"ed_nut_{row['log_id']}"):
                st.session_state.update(
                    {
                        "edit_mode": "nutr",
                        "edit_data": {**row, "food_name": row["foods"]["food_name"]},
                    }
                )
                st.rerun()
            if cols[3].button("🗑️", key=f"del_nut_{row['log_id']}"):
                supabase.table("daily_logs").delete().eq(
                    "log_id", row["log_id"]
                ).execute()
                st.rerun()

# =================================================================
# TAB 2: HEALTH METRICS (RESTORING INDIVIDUAL INPUTS & STABLE CHARTS)
# =================================================================
with tab2:
    st.subheader("🩺 Clinical Vital Logs")
    ed_h = st.session_state.edit_data if st.session_state.edit_mode == "health" else {}

    # Restored: Individual Inputs with precise symbols and descriptions
    with st.form("health_precision_form"):
        r1_c1, r1_c2 = st.columns(2)
        weight_input = r1_c1.number_input(
            "⚖️ Body Weight (lb)",
            50.0,
            500.0,
            float(ed_h.get("weight_lb", 185.0)),
            step=0.1,
        )
        glucose_input = r1_c2.number_input(
            "🧪 Blood Glucose (mg/dL)",
            0.0,
            600.0,
            float(ed_h.get("blood_glucose", 95.0)),
            step=1.0,
        )

        st.markdown("---")
        st.markdown("#### **Blood Pressure Reading**")
        r2_c1, r2_c2 = st.columns(2)
        systolic_input = r2_c1.number_input(
            "🩸 Systolic (High)", 50, 250, int(ed_h.get("blood_pressure_systolic", 120))
        )
        diastolic_input = r2_c2.number_input(
            "🩸 Diastolic (Low)", 30, 160, int(ed_h.get("blood_pressure_diastolic", 80))
        )

        notes_input = st.text_input(
            "📝 Observation Notes",
            value=ed_h.get("notes", ""),
            placeholder="e.g., Post-workout, Fasting, etc.",
        )

        if st.form_submit_button("🚨 Update Record" if ed_h else "💾 Save Vitals"):
            h_payload = {
                "date": str(datetime.now().date()),
                "time": datetime.now().strftime("%H:%M:%S"),
                "weight_lb": weight_input,
                "blood_glucose": glucose_input,
                "blood_pressure_systolic": systolic_input,
                "blood_pressure_diastolic": diastolic_input,
                "notes": notes_input,
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

    # Restored: Trend Charts with Locked Y-Axis (Prevents Navigation Resizing)
    st.markdown("### 📊 Precision Analytical Trends")
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
        df_h["ts"] = pd.to_datetime(
            df_h["date"].astype(str) + " " + df_h["time"].fillna("00:00:00").astype(str)
        )

        # 1. Blood Pressure: Fixed [40-200] range
        bp_base = (
            alt.Chart(df_h)
            .transform_fold(
                ["blood_pressure_systolic", "blood_pressure_diastolic"],
                as_=["Metric", "Value"],
            )
            .encode(
                x=alt.X("ts:T", title="Timeline", axis=alt.Axis(format="%m/%d %H:%M")),
                y=alt.Y(
                    "Value:Q",
                    scale=alt.Scale(domain=[40, 200], clamp=True),
                    title="BP (mmHg)",
                ),
                color=alt.Color(
                    "Metric:N",
                    scale=alt.Scale(range=["#FF4B4B", "#1C83E1"]),
                    legend=alt.Legend(orient="top-left"),
                ),
            )
        )
        bp_chart = bp_base.mark_line(
            strokeWidth=3, interpolate="monotone"
        ) + bp_base.mark_circle(size=60)

        # 2. Glucose: Fixed [60-250] range
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
                x=alt.X("ts:T", title=None, axis=alt.Axis(labels=False)),
                y=alt.Y(
                    "blood_glucose:Q",
                    scale=alt.Scale(domain=[50, 250], clamp=True),
                    title="Glucose",
                ),
            )
        )

        # 3. Weight: Dynamic Window
        w_min, w_max = df_h["weight_lb"].min() - 3, df_h["weight_lb"].max() + 3
        weight_chart = (
            alt.Chart(df_h)
            .mark_line(color="#2ECC71", point=True)
            .encode(
                x=alt.X("ts:T", title="Measurement History"),
                y=alt.Y(
                    "weight_lb:Q",
                    scale=alt.Scale(domain=[w_min, w_max], clamp=True),
                    title="Weight (lbs)",
                ),
            )
        )

        # VConcat with bind_y=False to ensure scrolling doesn't break chart sizing
        st.altair_chart(
            alt.vconcat(bp_chart, glu_chart, weight_chart)
            .properties(spacing=15)
            .interactive(bind_y=False),
            use_container_width=True,
        )

# =================================================================
# TAB 3: ACTIVITY (RESTORED CONDITIONAL UI)
# =================================================================
with tab3:
    st.subheader("🏃 Training Log")
    ed_a = st.session_state.edit_data if st.session_state.edit_mode == "act" else {}

    act_type = st.radio(
        "Activity Category",
        ["Strength", "Cardio", "Endurance"],
        horizontal=True,
        index=["Strength", "Cardio", "Endurance"].index(
            ed_a.get("activity_category", "Strength")
        ),
    )

    with st.form("activity_master_form"):
        exe_label = st.text_input("Exercise Name", value=ed_a.get("exercise_name", ""))
        ac1, ac2, ac3 = st.columns(3)

        if act_type == "Strength":
            sets_val = ac1.number_input("Sets", 0, 50, int(ed_a.get("sets", 0)))
            reps_val = ac2.number_input("Reps", 0, 500, int(ed_a.get("reps", 0)))
            wgt_val = ac3.number_input(
                "Weight (lbs)", 0, 2000, int(ed_h.get("weight_lb", 0))
            )
            dur_val, dst_val = 0, 0.0
        elif act_type == "Cardio":
            dur_val = ac1.number_input(
                "Duration (min)", 0, 1440, int(ed_a.get("duration_min", 0))
            )
            dst_val = ac2.number_input(
                "Distance (mi)", 0.0, 500.0, float(ed_a.get("distance_miles", 0.0))
            )
            sets_val, reps_val, wgt_val = 0, 0, 0
        else:  # Endurance
            dur_val = ac1.number_input(
                "Duration (min)", 0, 1440, int(ed_a.get("duration_min", 0))
            )
            sets_val = ac2.number_input("Sets/Rounds", 0, 100, int(ed_a.get("sets", 0)))
            reps_val = ac3.number_input("Total Reps", 0, 5000, int(ed_a.get("reps", 0)))
            dst_val, wgt_val = 0.0, 0

        if st.form_submit_button("Save Activity"):
            a_payload = {
                "log_date": str(datetime.now().date()),
                "exercise_name": exe_label,
                "activity_category": act_type,
                "sets": sets_val,
                "reps": reps_val,
                "weight_lb": wgt_val,
                "duration_min": dur_val,
                "distance_miles": dst_val,
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

# =================================================================
# TAB 4: TRUE MASTER REPORTS (PULLS ALL DATA FROM ALL TABLES)
# =================================================================
with tab4:
    st.subheader("📂 Global System Database Export")
    st.write("Extracting full row history for all system tables.")

    # Restored: The "Deep Pull" Loop
    all_system_tables = [
        "daily_logs",
        "health_metrics",
        "activity_logs",
        "foods",
        "daily_variance",
    ]

    for tbl_name in all_system_tables:
        with st.expander(f"📥 Master View: {tbl_name.replace('_', ' ').upper()}"):
            # Query pulls ALL rows. If not a system table, it filters by active_user
            m_query = supabase.table(tbl_name).select("*")
            if tbl_name not in ["foods", "daily_variance"]:
                m_query = m_query.eq("user_id", active_user)

            m_res = m_query.execute()
            if m_res.data:
                m_df = pd.DataFrame(m_res.data)
                st.dataframe(m_df, use_container_width=True)

                # Master Download Button for each table
                csv_buffer = io.StringIO()
                m_df.to_csv(csv_buffer, index=False)
                st.download_button(
                    label=f"Download Full {tbl_name} Dataset",
                    data=csv_buffer.getvalue(),
                    file_name=f"MASTER_EXPORT_{tbl_name}_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    key=f"dl_master_{tbl_name}",
                )
            else:
                st.info("Table is currently empty.")
