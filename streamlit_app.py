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
        with st.form("login_form"):
            pwd = st.text_input("Enter Access Code", type="password")
            if st.form_submit_button("Login"):
                if pwd == st.secrets["ADMIN_PASSWORD"]:
                    st.session_state.authenticated, st.session_state.is_admin = (
                        True,
                        True,
                    )
                    st.rerun()
                elif pwd == st.secrets["GUEST_PASSWORD"]:
                    st.session_state.authenticated, st.session_state.is_admin = (
                        True,
                        False,
                    )
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
TARGET_FAT_MAX, TARGET_NET_CARBS, TARGET_FIBER_MIN = 60, 60, 30

tab1, tab2, tab3, tab4 = st.tabs(
    ["🍴 Nutrition", "🩺 Health Metrics", "🏃 Activity", "📊 Reports & Master Export"]
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
            st.subheader(f"Daily Status: {latest['date']} ({active_user.upper()})")
            c1, c2, c3, c4, c5 = st.columns(5)
            cals = float(latest.get("total_calories", 0))
            prot = float(latest.get("total_protein", 0))
            net_c = float(latest.get("total_net_carbs", 0))
            fat = float(latest.get("total_fat", 0))
            fib = float(latest.get("total_fiber", 0))

            c1.metric("Calories", f"{int(cals)}", f"{int(TARGET_CALORIES - cals)} Left")
            c2.metric(
                "Protein", f"{int(prot)}g", f"{int(prot - TARGET_PROTEIN)} vs Goal"
            )
            c3.metric("Net Carbs", f"{int(net_c)}g", f"Limit: {TARGET_NET_CARBS}")
            c4.metric("Fat", f"{int(fat)}g")
            c5.metric("Fiber", f"{int(fib)}g")
    except Exception as e:
        st.error(f"Nutrition Load Error: {e}")

    st.divider()
    st.subheader("🍴 Log a Meal")
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("### Search Food Library")
        f_query = supabase.table("foods").select("*").order("food_name").execute()
        if f_query.data:
            f_dict = {f["food_name"]: f for f in f_query.data}
            sel = st.selectbox("Select Item", options=list(f_dict.keys()), index=None)
            if sel:
                srv = st.number_input("Servings", 0.1, 10.0, 1.0)
                if st.button("Add to Log"):
                    supabase.table("daily_logs").insert(
                        {
                            "food_id": f_dict[sel]["food_id"],
                            "servings": srv,
                            "log_date": str(datetime.now().date()),
                            "user_id": record_owner,
                        }
                    ).execute()
                    st.rerun()

# --- TAB 2: HEALTH METRICS ---
with tab2:
    try:
        res = (
            supabase.table("health_metrics")
            .select("*")
            .eq("user_id", active_user)
            .order("date", desc=False)
            .execute()
        )
        df = pd.DataFrame(res.data) if res.data else pd.DataFrame()

        if not df.empty:
            df["ts"] = pd.to_datetime(
                df["date"].astype(str) + " " + df["time"].fillna("00:00:00").astype(str)
            )
            df["display_time"] = df["ts"].dt.strftime("%b %d, %I:%M %p")

            # --- STATUS CARDS ---
            latest = df.iloc[-1]
            st.subheader(f"📋 Latest Health Status (Logged: {latest['display_time']})")
            s1, s2, s3 = st.columns(3)

            if not pd.isna(latest.get("weight_lb")):
                w = latest["weight_lb"]
                w_status = "🟢" if w < 200 else "🟡" if w < 220 else "🔴"
                s1.metric("Current Weight", f"{w} lbs", f"{w_status} Target < 200")

            if not pd.isna(latest.get("blood_pressure_systolic")):
                sys, dia = (
                    latest["blood_pressure_systolic"],
                    latest["blood_pressure_diastolic"],
                )
                bp_status = (
                    "🟢"
                    if sys < 130 and dia < 85
                    else "🟡"
                    if sys < 140 and dia < 90
                    else "🔴"
                )
                s2.metric(
                    "Blood Pressure",
                    f"{int(sys)}/{int(dia)}",
                    f"{bp_status} Target < 130/85",
                )

            if not pd.isna(latest.get("blood_glucose")):
                glu = latest["blood_glucose"]
                g_status = "🟢" if glu < 100 else "🟡" if glu < 125 else "🔴"
                s3.metric(
                    "Blood Glucose", f"{int(glu)} mg/dL", f"{g_status} Target < 100"
                )

            st.divider()

            # --- TREND CHARTS (ZOOM DISABLED FOR BETTER PAGE SCROLLING) ---
            def create_static_chart(data, y_col, y_label, y_domain, color):
                base = alt.Chart(data).encode(
                    x=alt.X(
                        "ts:T",
                        title="Timeline",
                        axis=alt.Axis(format="%b %d", labelAngle=-45, tickCount="day"),
                    ),
                    y=alt.Y(
                        f"{y_col}:Q",
                        scale=alt.Scale(domain=y_domain, zero=False),
                        title=y_label,
                    ),
                    tooltip=[
                        alt.Tooltip("display_time:N", title="Logged"),
                        alt.Tooltip(f"{y_col}:Q", title=y_label),
                    ],
                )
                # Static lines/points - no scrolling hijacking
                return (
                    base.mark_line(color=color, opacity=0.4)
                    + base.mark_point(color=color, size=60, filled=True)
                ).properties(height=250)

            # Weight Chart
            w_df = df.dropna(subset=["weight_lb"])
            if not w_df.empty:
                st.write("**Weight Trend**")
                st.altair_chart(
                    create_static_chart(
                        w_df, "weight_lb", "Lbs", [100, 300], "#3498db"
                    ),
                    use_container_width=True,
                )

            # Blood Pressure Chart
            bp_df = df.dropna(subset=["blood_pressure_systolic"])
            if not bp_df.empty:
                st.write("**Blood Pressure Trend**")
                bp_melted = bp_df.melt(
                    id_vars=["ts", "display_time"],
                    value_vars=["blood_pressure_systolic", "blood_pressure_diastolic"],
                )
                bp_chart = (
                    alt.Chart(bp_melted)
                    .mark_line(point=True)
                    .encode(
                        x=alt.X("ts:T", axis=alt.Axis(format="%b %d", tickCount="day")),
                        y=alt.Y(
                            "value:Q", scale=alt.Scale(domain=[40, 200]), title="mmHg"
                        ),
                        color=alt.Color(
                            "variable:N", legend=alt.Legend(title="Metric")
                        ),
                        tooltip=[
                            alt.Tooltip("display_time:N", title="Logged"),
                            alt.Tooltip("value:Q"),
                        ],
                    )
                    .properties(height=250)
                )
                st.altair_chart(bp_chart, use_container_width=True)

            # Glucose Chart
            g_df = df.dropna(subset=["blood_glucose"])
            if not g_df.empty:
                st.write("**Glucose Trend**")
                st.altair_chart(
                    create_static_chart(
                        g_df, "blood_glucose", "mg/dL", [50, 250], "#e74c3c"
                    ),
                    use_container_width=True,
                )

        st.divider()
        st.subheader("➕ Log Health Records")
        now = datetime.now()

        # --- RESTORED SEPARATE INPUTS ---
        c_wt, c_bp, c_gl = st.columns(3)

        with c_wt:
            with st.expander("⚖️ Weight Entry", expanded=True):
                w_val = st.number_input("Weight (lbs)", 0.0, 500.0, 0.0, key="wt_in")
                w_d = st.date_input("Date", now, key="wt_date")
                w_t = st.time_input("Time", now, key="wt_time")
                if st.button("Save Weight"):
                    if w_val > 0:
                        supabase.table("health_metrics").insert(
                            {
                                "date": str(w_d),
                                "time": w_t.strftime("%H:%M:%S"),
                                "weight_lb": w_val,
                                "user_id": record_owner,
                            }
                        ).execute()
                        st.rerun()

        with c_bp:
            with st.expander("❤️ BP Entry", expanded=True):
                sys = st.number_input("Systolic", 0, 250, 0, key="bp_sys")
                dia = st.number_input("Diastolic", 0, 250, 0, key="bp_dia")
                bp_d = st.date_input("Date", now, key="bp_date")
                bp_t = st.time_input("Time", now, key="bp_time")
                if st.button("Save BP"):
                    if sys > 0 and dia > 0:
                        supabase.table("health_metrics").insert(
                            {
                                "date": str(bp_d),
                                "time": bp_t.strftime("%H:%M:%S"),
                                "blood_pressure_systolic": sys,
                                "blood_pressure_diastolic": dia,
                                "user_id": record_owner,
                            }
                        ).execute()
                        st.rerun()

        with c_gl:
            with st.expander("🩸 Glucose Entry", expanded=True):
                gl_val = st.number_input("Glucose", 0, 500, 0, key="glu_in")
                gl_d = st.date_input("Date", now, key="glu_date")
                gl_t = st.time_input("Time", now, key="glu_time")
                if st.button("Save Glucose"):
                    if gl_val > 0:
                        supabase.table("health_metrics").insert(
                            {
                                "date": str(gl_d),
                                "time": gl_t.strftime("%H:%M:%S"),
                                "blood_glucose": gl_val,
                                "user_id": record_owner,
                            }
                        ).execute()
                        st.rerun()

    except Exception as e:
        st.error(f"Health Tab Error: {e}")

# --- TAB 3: ACTIVITY ---
with tab3:
    st.subheader(f"🏃 Log Activity ({active_user.title()})")
    act_type = st.radio(
        "Category", ["Strength", "Cardio", "Endurance"], horizontal=True
    )
    with st.form("act_form", clear_on_submit=True):
        f1, f2 = st.columns(2)
        a_date, a_name = (
            f1.date_input("Date", datetime.now()),
            f2.text_input("Exercise Name"),
        )
        c1, c2, c3 = st.columns(3)
        s, r, w, d, mi = 0, 0, 0, 0, 0
        if act_type == "Strength":
            s, r, w = (
                c1.number_input("Sets", 0),
                c2.number_input("Reps", 0),
                c3.number_input("Weight", 0),
            )
        else:
            d, mi = c1.number_input("Min", 0), c2.number_input("Miles", 0.0)
        if st.form_submit_button("Log Activity"):
            supabase.table("activity_logs").insert(
                {
                    "log_date": str(a_date),
                    "exercise_name": a_name,
                    "activity_category": act_type,
                    "sets": s,
                    "reps": r,
                    "weight_lb": w,
                    "duration_min": d,
                    "distance_miles": mi,
                    "user_id": record_owner,
                }
            ).execute()
            st.rerun()

# --- TAB 4: REPORTS ---
with tab4:
    st.subheader("📊 Master Table Viewer")
    view_tbl = st.selectbox(
        "Select Table",
        ["daily_variance", "health_metrics", "activity_logs", "daily_logs", "foods"],
    )
    try:
        query = supabase.table(view_tbl).select("*")
        if view_tbl != "foods":
            query = query.eq("user_id", active_user)

        if view_tbl in ["health_metrics", "daily_variance"]:
            sort_col = "date"
        elif view_tbl in ["activity_logs", "daily_logs"]:
            sort_col = "log_date"
        else:
            sort_col = "food_name"

        tbl_res = query.order(sort_col, desc=True).limit(100).execute()
        if tbl_res.data:
            st.dataframe(pd.DataFrame(tbl_res.data), use_container_width=True)
    except Exception as e:
        st.error(f"Viewer Error: {e}")

    if st.button("Prepare CSV Export"):
        try:
            met = (
                supabase.table("health_metrics")
                .select("*")
                .eq("user_id", active_user)
                .execute()
                .data
            )
            if met:
                st.download_button(
                    "📥 Download",
                    data=pd.DataFrame(met).to_csv(index=False).encode("utf-8"),
                    file_name="export.csv",
                )
        except Exception as e:
            st.error(f"Export Error: {e}")
