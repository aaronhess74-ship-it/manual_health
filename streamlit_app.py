import streamlit as st
from supabase import create_client
from datetime import datetime, timedelta
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

# --- DATA SCOPING & SIDEBAR ---
if st.session_state.is_admin:
    view_mode = st.sidebar.radio(
        "🔎 View Mode", ["My Data (Admin)", "Tester Data (Guest)"]
    )
    active_user = "admin" if "Admin" in view_mode else "guest"
else:
    active_user = "guest"
    st.sidebar.success("Logged in as Guest")

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
            cals, prot, net_c = (
                float(latest.get("total_calories", 0)),
                float(latest.get("total_protein", 0)),
                float(latest.get("total_net_carbs", 0)),
            )
            fat, fib = (
                float(latest.get("total_fat", 0)),
                float(latest.get("total_fiber", 0)),
            )

            def get_status(curr, target, ceil=True):
                if ceil:
                    return "🔴" if curr > target else "🟢"
                return "🟢" if curr >= target else "🔴"

            c1.metric(
                f"Calories {get_status(cals, TARGET_CALORIES)}",
                f"{int(cals)}",
                f"Goal: {TARGET_CALORIES}",
            )
            c2.metric(
                f"Protein {get_status(prot, TARGET_PROTEIN, False)}",
                f"{int(prot)}g",
                f"Goal: {TARGET_PROTEIN}g",
            )
            c3.metric(
                f"Net Carbs {get_status(net_c, TARGET_NET_CARBS)}",
                f"{int(net_c)}g",
                f"Limit: {TARGET_NET_CARBS}g",
            )
            c4.metric(f"Fat {get_status(fat, TARGET_FAT_MAX)}", f"{int(fat)}g")
            c5.metric(
                f"Fiber {get_status(fib, TARGET_FIBER_MIN, False)}", f"{int(fib)}g"
            )
    except Exception as e:
        st.error(f"Nutrition Error: {e}")

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
    with col_b:
        st.markdown("### Add Custom Item")
        if st.session_state.is_admin:
            with st.form("new_food_form"):
                n_name = st.text_input("Name")
                nc, np, nf, ncar, nfib = st.columns(5)
                c_val = nc.number_input("Cals", 0)
                p_val = np.number_input("Prot", 0)
                f_val = nf.number_input("Fat", 0)
                car_val = ncar.number_input("NetC", 0)
                fib_val = nfib.number_input("Fiber", 0)
                if st.form_submit_button("Create & Log"):
                    res = (
                        supabase.table("foods")
                        .insert(
                            {
                                "food_name": n_name,
                                "calories": c_val,
                                "protein_g": p_val,
                                "fat_g": f_val,
                                "net_carbs_g": car_val,
                                "fiber_g": fib_val,
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
                                "user_id": record_owner,
                            }
                        ).execute()
                        st.rerun()
        else:
            st.warning("Admin only: Custom food creation.")

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
            st.subheader(f"📋 Latest Status (Logged: {latest['display_time']})")
            s1, s2, s3 = st.columns(3)

            if not pd.isna(latest.get("weight_lb")):
                w = latest["weight_lb"]
                w_status = "🟢" if w < 200 else "🟡" if w < 220 else "🔴"
                s1.metric("Weight", f"{w} lbs", f"{w_status} Target < 200")

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
                    "BP", f"{int(sys)}/{int(dia)}", f"{bp_status} Target < 130/85"
                )

            if not pd.isna(latest.get("blood_glucose")):
                glu = latest["blood_glucose"]
                g_status = "🟢" if glu < 100 else "🟡" if glu < 125 else "🔴"
                s3.metric("Glucose", f"{int(glu)} mg/dL", f"{g_status} Target < 100")

            st.divider()
            st.subheader("📊 Trends (Click/Drag to Zoom)")
            brush = alt.selection_interval(encodings=["x"])

            def create_chart(data, y_col, y_label, y_domain, color):
                base = alt.Chart(data).encode(
                    x=alt.X(
                        "ts:T",
                        title="Date",
                        axis=alt.Axis(format="%b %d", tickCount="day"),
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
                return (
                    (
                        base.mark_line(color=color, opacity=0.4)
                        + base.mark_point(color=color, size=60, filled=True)
                    )
                    .add_params(brush)
                    .transform_filter(brush)
                    .properties(height=250)
                )

            # Charts
            w_df = df.dropna(subset=["weight_lb"])
            if not w_df.empty:
                st.write("**Weight**")
                st.altair_chart(
                    create_chart(w_df, "weight_lb", "Lbs", [100, 300], "#3498db"),
                    use_container_width=True,
                )

            bp_df = df.dropna(subset=["blood_pressure_systolic"])
            if not bp_df.empty:
                st.write("**Blood Pressure**")
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
                    .add_params(brush)
                    .transform_filter(brush)
                    .properties(height=250)
                    .interactive()
                )
                st.altair_chart(bp_chart, use_container_width=True)

            g_df = df.dropna(subset=["blood_glucose"])
            if not g_df.empty:
                st.write("**Glucose**")
                st.altair_chart(
                    create_chart(g_df, "blood_glucose", "mg/dL", [50, 250], "#e74c3c"),
                    use_container_width=True,
                )

        st.divider()
        st.subheader("➕ Manual Entry (Backdating Supported)")
        with st.form("metric_form_final", clear_on_submit=True):
            f1, f2 = st.columns(2)
            log_date, log_time = (
                f1.date_input("Date", datetime.now()),
                f2.time_input("Time", datetime.now()),
            )
            c1, c2, c3, c4 = st.columns(4)
            wt, sys, dia, gl = (
                c1.number_input("Weight", 0.0),
                c2.number_input("Sys", 0),
                c3.number_input("Dia", 0),
                c4.number_input("Gluc", 0),
            )
            if st.form_submit_button("Save Health Record"):
                payload = {
                    "date": str(log_date),
                    "time": log_time.strftime("%H:%M:%S"),
                    "user_id": record_owner,
                }
                if wt > 0:
                    payload["weight_lb"] = wt
                if sys > 0:
                    payload["blood_pressure_systolic"] = sys
                if dia > 0:
                    payload["blood_pressure_diastolic"] = dia
                if gl > 0:
                    payload["blood_glucose"] = gl
                supabase.table("health_metrics").insert(payload).execute()
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
    st.divider()
    a_res = (
        supabase.table("activity_logs")
        .select("*")
        .eq("user_id", active_user)
        .order("log_date", desc=True)
        .limit(15)
        .execute()
    )
    if a_res.data:
        st.dataframe(pd.DataFrame(a_res.data), use_container_width=True)

# --- TAB 4: REPORTS & FIXED MASTER VIEWER ---
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

        # Correct Sorting Keys
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

    st.divider()
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
                csv = pd.DataFrame(met).to_csv(index=False).encode("utf-8")
                st.download_button(
                    "📥 Download", data=csv, file_name=f"export_{active_user}.csv"
                )
        except Exception as e:
            st.error(f"Export Error: {e}")
