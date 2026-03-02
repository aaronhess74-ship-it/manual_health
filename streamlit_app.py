import streamlit as st
from supabase import create_client
from datetime import datetime
import pandas as pd
import altair as alt

# 1. Setup Connection
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.set_page_config(
    page_title="Health Dashboard Pro", layout="wide", initial_sidebar_state="collapsed"
)


# --- ACCESS CONTROL ---
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.is_admin = False

    if not st.session_state.authenticated:
        st.title("🔒 Dashboard Access")
        col1, _ = st.columns([1, 1])
        with col1:
            with st.form("login_form"):
                pwd = st.text_input("Enter Access Code", type="password")
                if st.form_submit_button("Login"):
                    if pwd == st.secrets["ADMIN_PASSWORD"]:
                        st.session_state.authenticated = True
                        st.session_state.is_admin = True
                        st.rerun()
                    elif pwd == st.secrets.get("GUEST_PASSWORD"):
                        st.session_state.authenticated = True
                        st.session_state.is_admin = False
                        st.rerun()
                    else:
                        st.error("Invalid Code")
        return False
    return True


if not check_password():
    st.stop()

# --- DATA SCOPING ---
if st.session_state.is_admin:
    view_mode = st.sidebar.radio(
        "🔎 View Mode", ["My Data (Admin)", "Tester Data (Guest)"]
    )
    active_user = "admin" if "Admin" in view_mode else "guest"
else:
    active_user = "guest"

record_owner = "admin" if st.session_state.is_admin else "guest"

# --- TARGETS ---
TARGET_CALORIES, TARGET_PROTEIN = 1800, 160
TARGET_FAT_MAX, TARGET_FIBER_MIN = 60, 30
NC_LIMIT = 100

tab1, tab2, tab3, tab4 = st.tabs(
    ["🍴 Nutrition", "🩺 Health Metrics", "🏃 Activity", "📊 Reports"]
)

# --- TAB 1: NUTRITION (FULLY RESTORED + EDIT & UNIQUE KEYS) ---
with tab1:
    try:
        # 1. Daily Status Metrics
        response = (
            supabase.table("daily_variance")
            .select("*")
            .eq("user_id", active_user)
            .order("date", desc=True)
            .limit(1)
            .execute()
        )
        if response.data:
            latest = response.data[0]
            st.subheader(f"Daily Status: {latest.get('date')} ({active_user.upper()})")
            c1, c2, c3, c4, c5 = st.columns(5)

            cals = float(latest.get("total_calories") or 0)
            prot = float(latest.get("total_protein") or 0)
            net_c = float(latest.get("total_net_carbs") or 0)
            fat = float(latest.get("total_fat") or 0)
            fib = float(latest.get("total_fiber") or 0)

            nc_dot = "🟢" if net_c <= NC_LIMIT else "🔴"
            fat_dot = "🟢" if fat <= TARGET_FAT_MAX else "🔴"
            fib_dot = "🟢" if fib >= TARGET_FIBER_MIN else "🔴"

            c1.metric("Calories", f"{int(cals)}", f"{int(TARGET_CALORIES - cals)} Left")
            c2.metric(
                "Protein", f"{int(prot)}g", f"{int(prot - TARGET_PROTEIN)}g vs Goal"
            )
            c3.metric(
                f"Net Carbs {nc_dot}",
                f"{int(net_c)}g",
                f"{int(net_c - NC_LIMIT)}g Over",
                delta_color="inverse",
            )
            c4.metric(
                f"Fat {fat_dot}", f"{int(fat)}g", f"{int(TARGET_FAT_MAX - fat)}g Left"
            )
            c5.metric(
                f"Fiber {fib_dot}",
                f"{int(fib)}g",
                f"{int(fib - TARGET_FIBER_MIN)}g vs Min",
            )
    except Exception as e:
        st.error(f"Nutrition Load Error: {e}")

    st.divider()

    # Session State for Editing Nutrition Log
    edit_log_id = st.session_state.get("editing_log_id", None)
    edit_log_vals = st.session_state.get("editing_log_vals", {})

    col_a, col_b = st.columns(2)

    # 2. Library Search / Edit Form
    with col_a:
        st.markdown(
            "### 🔎 Library Search" if not edit_log_id else "### ✏️ Edit Log Entry"
        )
        f_query = supabase.table("foods").select("*").order("food_name").execute()
        if f_query.data:
            f_dict = {f["food_name"]: f for f in f_query.data}

            # If editing, find the current food name
            cur_food = (
                edit_log_vals.get("foods", {}).get("food_name") if edit_log_id else None
            )
            sel = st.selectbox(
                "Select Item",
                options=list(f_dict.keys()),
                index=list(f_dict.keys()).index(cur_food)
                if cur_food in f_dict
                else None,
            )

            if sel:
                # If editing, use existing servings as default
                def_srv = (
                    float(edit_log_vals.get("servings", 1.0)) if edit_log_id else 1.0
                )
                srv = st.number_input("Servings", 0.1, 10.0, def_srv, step=0.1)

                btn_label = "Update Log Entry" if edit_log_id else "Log Food Entry"
                if st.button(btn_label):
                    f_id = f_dict[sel].get("food_id") or f_dict[sel].get("id")
                    payload = {
                        "food_id": f_id,
                        "servings": srv,
                        "log_date": edit_log_vals.get(
                            "log_date", str(datetime.now().date())
                        ),
                        "user_id": record_owner,
                    }
                    if edit_log_id:
                        supabase.table("daily_logs").update(payload).eq(
                            "log_id", edit_log_id
                        ).execute()
                        st.session_state.editing_log_id = None
                        st.session_state.editing_log_vals = {}
                    else:
                        supabase.table("daily_logs").insert(payload).execute()
                    st.rerun()

                if edit_log_id:
                    if st.button("Cancel Edit"):
                        st.session_state.editing_log_id = None
                        st.session_state.editing_log_vals = {}
                        st.rerun()

    # 3. Admin: Create Food (Preserved)
    with col_b:
        if st.session_state.is_admin:
            st.markdown("### ➕ Admin: Create Food")
            with st.form("add_food_form", clear_on_submit=True):
                fn = st.text_input("New Food Name")
                f_c1, f_c2, f_c3 = st.columns(3)
                v_ca = f_c1.number_input("Cals", 0)
                v_pr = f_c2.number_input("Prot", 0)
                v_nc = f_c3.number_input("NetC", 0)
                if st.form_submit_button("Create & Log Item"):
                    res = (
                        supabase.table("foods")
                        .insert(
                            {
                                "food_name": fn,
                                "calories": v_ca,
                                "protein_g": v_pr,
                                "net_carbs_g": v_nc,
                            }
                        )
                        .execute()
                    )
                    if res.data:
                        f_id = res.data[0].get("id") or res.data[0].get("food_id")
                        supabase.table("daily_logs").insert(
                            {
                                "food_id": f_id,
                                "servings": 1.0,
                                "log_date": str(datetime.now().date()),
                                "user_id": record_owner,
                            }
                        ).execute()
                        st.rerun()

    # 4. History List (Unique Keys + Edit Button)
    st.subheader("🗑️ Today's Logged Items")
    log_res = (
        supabase.table("daily_logs")
        .select("*, foods(food_name, calories)")
        .eq("log_date", str(datetime.now().date()))
        .eq("user_id", active_user)
        .execute()
    )
    if log_res.data:
        for idx, r in enumerate(log_res.data):
            lc1, lc2, lc3, lc4 = st.columns([3, 1, 0.5, 0.5])
            f_info = r.get("foods") or {}
            lc1.write(f"**{f_info.get('food_name', 'Unknown')}**")
            lc2.write(f"{int(f_info.get('calories', 0) * r.get('servings', 1))} kcal")

            l_id = r.get("log_id") or r.get("id") or idx

            # Edit Button (idx added to key to prevent Streamlit error)
            if lc3.button("✏️", key=f"ed_log_{l_id}_{idx}"):
                st.session_state.editing_log_id = l_id
                st.session_state.editing_log_vals = r
                st.rerun()

            # Delete Button (idx added to key to prevent Streamlit error)
            if lc4.button("🗑️", key=f"del_log_{l_id}_{idx}"):
                col_n = "log_id" if "log_id" in r else "id"
                supabase.table("daily_logs").delete().eq(col_n, l_id).execute()
                st.rerun()

# --- TAB 2: HEALTH METRICS (EDIT + ALL 3 CHARTS RESTORED) ---
with tab2:
    try:
        # 1. Fetch data
        h_res = (
            supabase.table("health_metrics")
            .select("*")
            .eq("user_id", active_user)
            .order("date", desc=False)
            .execute()
        )
        df_h = pd.DataFrame(h_res.data) if h_res.data else pd.DataFrame()

        # --- ALL 3 PERFECTED CHARTS ---
        if not df_h.empty:
            # Standardize Timestamp and Tooltip String for all charts
            df_h["ts"] = pd.to_datetime(
                df_h["date"].astype(str)
                + " "
                + df_h["time"].fillna("00:00:00").astype(str)
            )
            df_h["display_time"] = df_h["ts"].dt.strftime("%b %d, %I:%M %p")

            st.subheader("📊 Health Trends")

            # A. Weight Chart
            df_w = df_h.dropna(subset=["weight_lb"])
            if not df_w.empty:
                w_chart = (
                    alt.Chart(df_w)
                    .mark_line(point=True, color="#3498db")
                    .encode(
                        x=alt.X("ts:T", title="Timeline"),
                        y=alt.Y(
                            "weight_lb:Q",
                            scale=alt.Scale(zero=False),
                            title="Weight (lbs)",
                        ),
                        tooltip=[
                            alt.Tooltip("display_time", title="Logged At"),
                            alt.Tooltip("weight_lb", title="Weight"),
                        ],
                    )
                    .properties(height=220)
                )
                st.altair_chart(w_chart, use_container_width=True)

            # B. Blood Pressure Chart (Systolic & Diastolic)
            df_bp = df_h.dropna(
                subset=["blood_pressure_systolic", "blood_pressure_diastolic"]
            )
            if not df_bp.empty:
                bp_base = alt.Chart(df_bp).encode(x=alt.X("ts:T", title="Timeline"))
                sys_line = bp_base.mark_line(point=True, color="#e74c3c").encode(
                    y=alt.Y("blood_pressure_systolic:Q", title="Blood Pressure"),
                    tooltip=[
                        alt.Tooltip("display_time", title="Logged At"),
                        alt.Tooltip("blood_pressure_systolic", title="Systolic"),
                    ],
                )
                dia_line = bp_base.mark_line(point=True, color="#c0392b").encode(
                    y="blood_pressure_diastolic:Q",
                    tooltip=[
                        alt.Tooltip("display_time", title="Logged At"),
                        alt.Tooltip("blood_pressure_diastolic", title="Diastolic"),
                    ],
                )
                st.altair_chart(
                    (sys_line + dia_line).properties(height=220),
                    use_container_width=True,
                )

            # C. Glucose Chart
            df_g = df_h.dropna(subset=["blood_glucose"])
            if not df_g.empty:
                g_chart = (
                    alt.Chart(df_g)
                    .mark_line(point=True, color="#27ae60")
                    .encode(
                        x=alt.X("ts:T", title="Timeline"),
                        y=alt.Y(
                            "blood_glucose:Q",
                            scale=alt.Scale(zero=False),
                            title="Glucose (mg/dL)",
                        ),
                        tooltip=[
                            alt.Tooltip("display_time", title="Logged At"),
                            alt.Tooltip("blood_glucose", title="Glucose"),
                        ],
                    )
                    .properties(height=220)
                )
                st.altair_chart(g_chart, use_container_width=True)

        st.divider()

        # --- INPUTS (WITH EDIT LOGIC) ---
        st.subheader("➕ Manual Entries")

        edit_id = st.session_state.get("editing_health_id", None)
        edit_vals = st.session_state.get("editing_health_vals", {})

        m_c1, m_c2, m_c3 = st.columns(3)
        with m_c1:
            st.info("⚖️ Weight")
            wv = st.number_input(
                "Lbs", 0.0, value=float(edit_vals.get("weight_lb") or 0.0), key="w_in"
            )
            if st.button("Save Weight"):
                payload = {"weight_lb": wv, "user_id": record_owner}
                if edit_id:
                    supabase.table("health_metrics").update(payload).eq(
                        "metric_id", edit_id
                    ).execute()
                    st.session_state.editing_health_id = None
                    st.session_state.editing_health_vals = {}
                else:
                    payload.update(
                        {
                            "date": str(datetime.now().date()),
                            "time": datetime.now().strftime("%H:%M:%S"),
                        }
                    )
                    supabase.table("health_metrics").insert(payload).execute()
                st.rerun()

        with m_c2:
            st.error("❤️ Blood Pressure")
            bs = st.number_input(
                "Systolic",
                0,
                value=int(edit_vals.get("blood_pressure_systolic") or 0),
                key="sys_in",
            )
            bd = st.number_input(
                "Diastolic",
                0,
                value=int(edit_vals.get("blood_pressure_diastolic") or 0),
                key="dia_in",
            )
            if st.button("Save BP"):
                payload = {
                    "blood_pressure_systolic": bs,
                    "blood_pressure_diastolic": bd,
                    "user_id": record_owner,
                }
                if edit_id:
                    supabase.table("health_metrics").update(payload).eq(
                        "metric_id", edit_id
                    ).execute()
                    st.session_state.editing_health_id = None
                    st.session_state.editing_health_vals = {}
                else:
                    payload.update(
                        {
                            "date": str(datetime.now().date()),
                            "time": datetime.now().strftime("%H:%M:%S"),
                        }
                    )
                    supabase.table("health_metrics").insert(payload).execute()
                st.rerun()

        with m_c3:
            st.success("🩸 Glucose")
            gv = st.number_input(
                "mg/dL", 0, value=int(edit_vals.get("blood_glucose") or 0), key="glu_in"
            )
            if st.button("Save Glucose"):
                payload = {"blood_glucose": gv, "user_id": record_owner}
                if edit_id:
                    supabase.table("health_metrics").update(payload).eq(
                        "metric_id", edit_id
                    ).execute()
                    st.session_state.editing_health_id = None
                    st.session_state.editing_health_vals = {}
                else:
                    payload.update(
                        {
                            "date": str(datetime.now().date()),
                            "time": datetime.now().strftime("%H:%M:%S"),
                        }
                    )
                    supabase.table("health_metrics").insert(payload).execute()
                st.rerun()

        if edit_id:
            if st.button("Cancel Edit"):
                st.session_state.editing_health_id = None
                st.session_state.editing_health_vals = {}
                st.rerun()

        st.divider()
        st.subheader("📜 Recent Health History")
        hist_res = (
            supabase.table("health_metrics")
            .select("*")
            .eq("user_id", active_user)
            .order("date", desc=True)
            .limit(10)
            .execute()
        )
        if hist_res.data:
            for r in hist_res.data:
                hc1, hc2, hc3, hc4 = st.columns([4, 2, 0.5, 0.5])
                parts = []
                if r.get("weight_lb"):
                    parts.append(f"W: {r['weight_lb']}lbs")
                if r.get("blood_pressure_systolic"):
                    parts.append(
                        f"BP: {r['blood_pressure_systolic']}/{r['blood_pressure_diastolic']}"
                    )
                if r.get("blood_glucose"):
                    parts.append(f"G: {r['blood_glucose']}mg/dL")

                hc1.write(f"**{r.get('date')}** | {', '.join(parts)}")

                m_id = r.get("metric_id")

                if hc3.button("✏️", key=f"ed_{m_id}"):
                    st.session_state.editing_health_id = m_id
                    st.session_state.editing_health_vals = r
                    st.rerun()

                if hc4.button("🗑️", key=f"de_{m_id}"):
                    supabase.table("health_metrics").delete().eq(
                        "metric_id", m_id
                    ).execute()
                    st.rerun()
    except Exception as e:
        st.error(f"Health Tab Error: {e}")

# --- TAB 3: ACTIVITY (EDIT + DYNAMIC RADIO PRESERVED) ---
with tab3:
    st.subheader(f"🏃 Activity Tracking ({active_user.upper()})")

    # 1. Session State for Editing
    edit_act_id = st.session_state.get("editing_act_id", None)
    edit_act_vals = st.session_state.get("editing_act_vals", {})

    # Determine default category index for the radio button
    cat_options = ["Strength", "Cardio", "Endurance"]
    default_cat_idx = 0
    if edit_act_id and edit_act_vals.get("activity_category") in cat_options:
        default_cat_idx = cat_options.index(edit_act_vals.get("activity_category"))

    # 2. The Category Selector (Preserved)
    cat = st.radio("Workout Type", cat_options, index=default_cat_idx, horizontal=True)

    with st.form("activity_log_form", clear_on_submit=True):
        f1, f2 = st.columns(2)
        # Handle Date: use existing date if editing, otherwise today
        default_date = datetime.now()
        if edit_act_id and edit_act_vals.get("log_date"):
            default_date = pd.to_datetime(edit_act_vals.get("log_date"))

        da = f1.date_input("Date", default_date)
        nm = f2.text_input(
            "Exercise Name", value=edit_act_vals.get("exercise_name", "")
        )

        st.markdown("---")
        # 3. Dynamic Input Grid (Preserved & Pre-filled)
        c1, c2, c3, c4, c5 = st.columns(5)
        v_sets, v_reps, v_weight, v_dur, v_dist = 0, 0, 0, 0, 0.0

        if cat == "Strength":
            v_sets = c1.number_input(
                "Sets", min_value=0, value=int(edit_act_vals.get("sets") or 0)
            )
            v_reps = c2.number_input(
                "Reps", min_value=0, value=int(edit_act_vals.get("reps") or 0)
            )
            v_weight = c3.number_input(
                "Weight (lbs)",
                min_value=0,
                value=int(edit_act_vals.get("weight_lb") or 0),
            )

        elif cat == "Cardio":
            v_dur = c1.number_input(
                "Duration (mins)",
                min_value=0,
                value=int(edit_act_vals.get("duration_min") or 0),
            )
            v_dist = c2.number_input(
                "Distance (miles)",
                min_value=0.0,
                value=float(edit_act_vals.get("distance_miles") or 0.0),
            )

        elif cat == "Endurance":
            v_sets = c1.number_input(
                "Sets", min_value=0, value=int(edit_act_vals.get("sets") or 0)
            )
            v_reps = c2.number_input(
                "Reps", min_value=0, value=int(edit_act_vals.get("reps") or 0)
            )
            v_dur = c3.number_input(
                "Duration (mins)",
                min_value=0,
                value=int(edit_act_vals.get("duration_min") or 0),
            )

        st.markdown(" ")
        btn_label = "Update Activity" if edit_act_id else "Log Activity"
        if st.form_submit_button(btn_label):
            if nm:
                payload = {
                    "log_date": str(da),
                    "exercise_name": nm,
                    "activity_category": cat,
                    "sets": v_sets if v_sets > 0 else None,
                    "reps": v_reps if v_reps > 0 else None,
                    "weight_lb": v_weight if v_weight > 0 else None,
                    "duration_min": v_dur if v_dur > 0 else None,
                    "distance_miles": v_dist if v_dist > 0 else None,
                    "user_id": record_owner,
                }

                if edit_act_id:
                    supabase.table("activity_logs").update(payload).eq(
                        "activity_id", edit_act_id
                    ).execute()
                    st.session_state.editing_act_id = None
                    st.session_state.editing_act_vals = {}
                else:
                    supabase.table("activity_logs").insert(payload).execute()
                st.rerun()
            else:
                st.warning("Please enter an exercise name.")

    if edit_act_id:
        if st.button("Cancel Edit"):
            st.session_state.editing_act_id = None
            st.session_state.editing_act_vals = {}
            st.rerun()

    # 4. History with Edit/Delete
    st.divider()
    st.subheader("📜 Recent Workouts")
    act_res = (
        supabase.table("activity_logs")
        .select("*")
        .eq("user_id", active_user)
        .order("log_date", desc=True)
        .limit(10)
        .execute()
    )

    if act_res.data:
        for r in act_res.data:
            ac1, ac2, ac3, ac4 = st.columns([4, 2, 0.5, 0.5])

            details = []
            if r.get("sets"):
                details.append(f"{r['sets']} sets")
            if r.get("reps"):
                details.append(f"{r['reps']} reps")
            if r.get("weight_lb"):
                details.append(f"{r['weight_lb']} lbs")
            if r.get("duration_min"):
                details.append(f"{r['duration_min']} mins")
            if r.get("distance_miles"):
                details.append(f"{r['distance_miles']} miles")

            ac1.write(
                f"**{r['log_date']}** | {r['exercise_name']} ({r['activity_category']})"
            )
            ac2.write(", ".join(details))

            a_id = r.get("activity_id")

            if ac3.button("✏️", key=f"ed_act_{a_id}"):
                st.session_state.editing_act_id = a_id
                st.session_state.editing_act_vals = r
                st.rerun()

            if ac4.button("🗑️", key=f"de_act_{a_id}"):
                supabase.table("activity_logs").delete().eq(
                    "activity_id", a_id
                ).execute()
                st.rerun()

# --- TAB 4: REPORTS & EXPORTS (FIXED MASTER EXPORT) ---
with tab4:
    st.subheader("📥 Data Management & Master Export")

    # 1. Individual Table Viewer
    report_tbl = st.selectbox(
        "View Individual Table",
        ["health_metrics", "daily_logs", "activity_logs", "foods"],
    )

    q = supabase.table(report_tbl).select("*")
    if report_tbl != "foods":
        q = q.eq("user_id", active_user)

    if report_tbl == "health_metrics":
        rep_res = q.order("date", desc=True).execute()
    elif "logs" in report_tbl:
        rep_res = q.order("log_date", desc=True).execute()
    else:
        rep_res = q.execute()

    if rep_res.data:
        df_view = pd.DataFrame(rep_res.data)
        st.dataframe(df_view, use_container_width=True)

    st.divider()

    # 2. THE MASTER EXPORT (Fixed Column Selection)
    st.subheader("🚀 Master CSV Export")
    if st.button("Generate Master Dataset"):
        try:
            # Fetch tables
            h_data = (
                supabase.table("health_metrics")
                .select("*")
                .eq("user_id", active_user)
                .execute()
            )
            # We only pull food_name and calories to ensure compatibility with your DB schema
            n_data = (
                supabase.table("daily_logs")
                .select("*, foods(food_name, calories)")
                .eq("user_id", active_user)
                .execute()
            )
            a_data = (
                supabase.table("activity_logs")
                .select("*")
                .eq("user_id", active_user)
                .execute()
            )

            df_h = pd.DataFrame(h_data.data)
            if not df_h.empty:
                df_h["source_table"] = "health_metrics"

            df_n = pd.json_normalize(n_data.data)
            if not df_n.empty:
                df_n["source_table"] = "nutrition_logs"

            df_a = pd.DataFrame(a_data.data)
            if not df_a.empty:
                df_a["source_table"] = "activity_logs"

            # Merge
            master_df = pd.concat([df_h, df_n, df_a], axis=0, ignore_index=True)

            # Create Unified Date Column
            if "date" in master_df.columns and "log_date" in master_df.columns:
                master_df["unified_date"] = master_df["date"].fillna(
                    master_df["log_date"]
                )
            elif "date" in master_df.columns:
                master_df["unified_date"] = master_df["date"]
            elif "log_date" in master_df.columns:
                master_df["unified_date"] = master_df["log_date"]

            csv_master = master_df.to_csv(index=False).encode("utf-8")

            st.success("Master Dataset Prepared!")
            st.download_button(
                label="💾 Download All Data (Master CSV)",
                data=csv_master,
                file_name=f"MASTER_EXPORT_{active_user}_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )
        except Exception as e:
            st.error(f"Export Error: {e}")
