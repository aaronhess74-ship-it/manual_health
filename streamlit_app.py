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

# --- TAB 2: HEALTH METRICS (RESTORED ALL PERFECTED CHARTS) ---
with tab2:
    try:
        # Fetch data for active user
        h_res = (
            supabase.table("health_metrics")
            .select("*")
            .eq("user_id", active_user)
            .order("date", desc=False)
            .execute()
        )
        df_h = pd.DataFrame(h_res.data) if h_res.data else pd.DataFrame()

        if not df_h.empty:
            # 1. Standardize Timestamp and Tooltip String
            df_h["ts"] = pd.to_datetime(
                df_h["date"].astype(str)
                + " "
                + df_h["time"].fillna("00:00:00").astype(str)
            )
            df_h["display_time"] = df_h["ts"].dt.strftime("%b %d, %I:%M %p")

            st.subheader("📊 Health Trends")

            # --- WEIGHT CHART ---
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

            # --- BLOOD PRESSURE CHART (Systolic & Diastolic) ---
            df_bp = df_h.dropna(
                subset=["blood_pressure_systolic", "blood_pressure_diastolic"]
            )
            if not df_bp.empty:
                # Transform data to show two lines on one chart
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

            # --- GLUCOSE CHART ---
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

        # --- INPUTS (LOCKED - NO CHANGES) ---
        st.subheader("➕ Manual Entries")
        m_c1, m_c2, m_c3 = st.columns(3)
        with m_c1:
            st.info("⚖️ Weight")
            wv = st.number_input("Lbs", 0.0, key="w_in")
            if st.button("Save Weight"):
                supabase.table("health_metrics").insert(
                    {
                        "date": str(datetime.now().date()),
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "weight_lb": wv,
                        "user_id": record_owner,
                    }
                ).execute()
                st.rerun()
        with m_c2:
            st.error("❤️ Blood Pressure")
            bs = st.number_input("Systolic", 0, key="sys_in")
            bd = st.number_input("Diastolic", 0, key="dia_in")
            if st.button("Save BP"):
                supabase.table("health_metrics").insert(
                    {
                        "date": str(datetime.now().date()),
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "blood_pressure_systolic": bs,
                        "blood_pressure_diastolic": bd,
                        "user_id": record_owner,
                    }
                ).execute()
                st.rerun()
        with m_c3:
            st.success("🩸 Glucose")
            gv = st.number_input("mg/dL", 0, key="glu_in")
            if st.button("Save Glucose"):
                supabase.table("health_metrics").insert(
                    {
                        "date": str(datetime.now().date()),
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "blood_glucose": gv,
                        "user_id": record_owner,
                    }
                ).execute()
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
                hc1, hc2, hc3 = st.columns([4, 1, 1])
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

                h_id = r.get("metric_id") or r.get("id")
                if hc3.button("🗑️", key=f"del_h_{h_id}"):
                    col_n = "metric_id" if "metric_id" in r else "id"
                    supabase.table("health_metrics").delete().eq(col_n, h_id).execute()
                    st.rerun()
    except Exception as e:
        st.error(f"Health Tab Error: {e}")

# --- TAB 3: ACTIVITY ---
with tab3:
    st.subheader(f"🏃 Workout Log")
    with st.form("activity_form", clear_on_submit=True):
        f1, f2 = st.columns(2)
        ex_name = f1.text_input("Exercise Name")
        ex_cat = f2.selectbox("Category", ["Strength", "Cardio", "Endurance"])
        m1, m2, m3, m4 = st.columns(4)
        v_sets, v_reps, v_weight, v_dist = (
            m1.number_input("Sets", 0),
            m2.number_input("Reps", 0),
            m3.number_input("Weight", 0),
            m4.number_input("Miles/Mins", 0.0),
        )
        if st.form_submit_button("Log Activity"):
            supabase.table("activity_logs").insert(
                {
                    "log_date": str(datetime.now().date()),
                    "exercise_name": ex_name,
                    "activity_category": ex_cat,
                    "sets": v_sets,
                    "reps": v_reps,
                    "weight_lb": v_weight,
                    "distance_miles": v_dist,
                    "user_id": record_owner,
                }
            ).execute()
            st.rerun()

# --- TAB 4: REPORTS (STABLE REVERT) ---
with tab4:
    st.subheader("📊 Data Explorer & Master Export")
    report_tbl = st.selectbox(
        "Select Data Source", ["health_metrics", "daily_logs", "activity_logs", "foods"]
    )

    q = supabase.table(report_tbl).select("*")
    if report_tbl != "foods":
        q = q.eq("user_id", active_user)

    # Reverted to table-specific sorting that worked
    if report_tbl == "health_metrics":
        rep_res = q.order("date", desc=True).execute()
    elif "logs" in report_tbl:
        rep_res = q.order("log_date", desc=True).execute()
    else:
        rep_res = q.execute()

    if rep_res.data:
        df_rep = pd.DataFrame(rep_res.data)
        st.dataframe(df_rep, use_container_width=True)
        csv = df_rep.to_csv(index=False).encode("utf-8")
        st.download_button(
            label=f"💾 Download {report_tbl.replace('_', ' ').title()} as CSV",
            data=csv,
            file_name=f"{active_user}_{report_tbl}.csv",
            mime="text/csv",
        )
