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

# --- TAB 1: NUTRITION ---
with tab1:
    try:
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
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("### 🔎 Library Search")
        f_query = supabase.table("foods").select("*").order("food_name").execute()
        if f_query.data:
            f_dict = {f["food_name"]: f for f in f_query.data}
            sel = st.selectbox("Select Item", options=list(f_dict.keys()), index=None)
            if sel:
                srv = st.number_input("Servings", 0.1, 10.0, 1.0, step=0.1)
                if st.button("Log Food Entry"):
                    f_id = f_dict[sel].get("food_id") or f_dict[sel].get("id")
                    supabase.table("daily_logs").insert(
                        {
                            "food_id": f_id,
                            "servings": srv,
                            "log_date": str(datetime.now().date()),
                            "user_id": record_owner,
                        }
                    ).execute()
                    st.rerun()

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

    st.subheader("🗑️ Today's Logged Items")
    log_res = (
        supabase.table("daily_logs")
        .select("*, foods(food_name, calories)")
        .eq("log_date", str(datetime.now().date()))
        .eq("user_id", active_user)
        .execute()
    )
    if log_res.data:
        for r in log_res.data:
            lc1, lc2, lc3 = st.columns([3, 1, 1])
            f_info = r.get("foods") or {}
            lc1.write(f"**{f_info.get('food_name', 'Unknown')}**")
            lc2.write(f"{int(f_info.get('calories', 0) * r.get('servings', 1))} kcal")
            l_id = r.get("log_id") or r.get("id")
            if lc3.button("🗑️", key=f"del_log_{l_id}"):
                col_n = "log_id" if "log_id" in r else "id"
                supabase.table("daily_logs").delete().eq(col_n, l_id).execute()
                st.rerun()

# --- TAB 2: HEALTH METRICS (EDIT & DELETE WITH CORRECT SCHEMA) ---
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

        # --- PERFECTED CHARTS (UNTOUCHED) ---
        if not df_h.empty:
            df_h["ts"] = pd.to_datetime(
                df_h["date"].astype(str)
                + " "
                + df_h["time"].fillna("00:00:00").astype(str)
            )
            df_h["display_time"] = df_h["ts"].dt.strftime("%b %d, %I:%M %p")
            st.subheader("📊 Health Trends")

            w_chart = (
                alt.Chart(df_h.dropna(subset=["weight_lb"]))
                .mark_line(point=True, color="#3498db")
                .encode(
                    x=alt.X("ts:T", title="Timeline"),
                    y=alt.Y(
                        "weight_lb:Q", scale=alt.Scale(zero=False), title="Weight (lbs)"
                    ),
                    tooltip=[
                        alt.Tooltip("display_time", title="Logged At"),
                        alt.Tooltip("weight_lb", title="Weight"),
                    ],
                )
                .properties(height=220)
            )
            st.altair_chart(w_chart, use_container_width=True)
            # (Other charts for BP/Glucose follow same logic if data exists)

        st.divider()

        # --- INPUTS (STYLING PRESERVED + EDIT LOGIC) ---
        st.subheader("➕ Manual Entries")

        # Session State for Editing
        edit_id = st.session_state.get("editing_health_id", None)
        edit_vals = st.session_state.get("editing_health_vals", {})

        m_c1, m_c2, m_c3 = st.columns(3)
        with m_c1:
            st.info("⚖️ Weight")
            # Uses existing value if editing, otherwise 0.0
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

                # Correct Primary Key Mapping
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

# --- TAB 3: ACTIVITY (RESTORED DYNAMIC INPUTS) ---
with tab3:
    st.subheader(f"🏃 Activity Tracking ({active_user.upper()})")

    # 1. The Category Selector
    cat = st.radio("Workout Type", ["Strength", "Cardio", "Endurance"], horizontal=True)

    with st.form("activity_log_form", clear_on_submit=True):
        f1, f2 = st.columns(2)
        da = f1.date_input("Date", datetime.now())
        nm = f2.text_input("Exercise Name (e.g. Bench Press, Run)")

        st.markdown("---")
        # 2. Dynamic Input Grid based on Radio Selection
        c1, c2, c3, c4, c5 = st.columns(5)

        # Initialize variables to None/0
        v_sets, v_reps, v_weight, v_dur, v_dist = 0, 0, 0, 0, 0.0

        # Strength: Sets, Reps, Weight
        if cat == "Strength":
            v_sets = c1.number_input("Sets", min_value=0, step=1)
            v_reps = c2.number_input("Reps", min_value=0, step=1)
            v_weight = c3.number_input("Weight (lbs)", min_value=0, step=5)

        # Cardio: Duration, Distance
        elif cat == "Cardio":
            v_dur = c1.number_input("Duration (mins)", min_value=0, step=1)
            v_dist = c2.number_input("Distance (miles)", min_value=0.0, step=0.1)

        # Endurance: Sets, Reps, Duration
        elif cat == "Endurance":
            v_sets = c1.number_input("Sets", min_value=0, step=1)
            v_reps = c2.number_input("Reps", min_value=0, step=1)
            v_dur = c3.number_input("Duration (mins)", min_value=0, step=1)

        st.markdown(" ")
        if st.form_submit_button("Log Activity"):
            if nm:  # Simple check to ensure exercise name isn't blank
                supabase.table("activity_logs").insert(
                    {
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
                ).execute()
                st.rerun()
            else:
                st.warning("Please enter an exercise name.")

    # 3. Recent Activity History with Delete
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
            ac1, ac2, ac3 = st.columns([4, 2, 1])

            # Format the display string based on what data exists
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

            # Delete logic
            a_id = r.get("activity_id") or r.get("id")
            if ac3.button("🗑️", key=f"del_act_{a_id}"):
                col_n = "activity_id" if "activity_id" in r else "id"
                supabase.table("activity_logs").delete().eq(col_n, a_id).execute()
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
