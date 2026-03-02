import streamlit as st
from supabase import create_client
from datetime import datetime
import pandas as pd
import altair as alt
import numpy as np

# 1. Setup Connection
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.set_page_config(
    page_title="Health Dashboard Pro", layout="wide", initial_sidebar_state="collapsed"
)

# --- CSS STYLING ---
st.markdown(
    """
    <style>
    .metric-card {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
        border: 1px solid #efefef;
    }
    .stMetric { background-color: #f8f9fa; padding: 10px; border-radius: 8px; }
    </style>
    """,
    unsafe_allow_html=True,
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

# --- DATA SCOPING (STEP 3) ---
# Admin can toggle views; Guest is locked to 'guest' data
if st.session_state.is_admin:
    view_mode = st.sidebar.radio(
        "🔎 View Mode", ["My Data (Admin)", "Tester Data (Guest)"]
    )
    active_user = "admin" if "Admin" in view_mode else "guest"
else:
    active_user = "guest"
    st.sidebar.success("Logged in as Guest: Data isolation active.")

# The ID used for any new records created during this session
record_owner = "admin" if st.session_state.is_admin else "guest"

st.title("💪 My Health Dashboard")

# --- TARGETS ---
TARGET_CALORIES, TARGET_PROTEIN = 1800, 160
TARGET_FAT_MAX, TARGET_NET_CARBS, TARGET_FIBER_MIN = 60, 60, 30

tab1, tab2, tab3, tab4 = st.tabs(
    ["🍴 Nutrition", "🩺 Health Metrics", "🏃 Activity", "📊 Reports & Master Export"]
)

# --- TAB 1: NUTRITION ---
with tab1:
    try:
        # Filtered by the active_user (admin or guest)
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

            def get_status(curr, target, ceil=True):
                if ceil:
                    return "🔴 OVER" if curr > target else "🟢 OK"
                return "🟢 GOAL" if curr >= target else "🔴 LOW"

            c1.metric(
                f"Calories {get_status(cals, TARGET_CALORIES)}",
                f"{int(cals)}",
                f"{int(TARGET_CALORIES - cals)} Left",
            )
            c2.metric(
                f"Protein {get_status(prot, TARGET_PROTEIN, False)}", f"{int(prot)}g"
            )
            c3.metric(
                f"Net Carbs {get_status(net_c, TARGET_NET_CARBS)}", f"{int(net_c)}g"
            )
            c4.metric("Total Fat", f"{int(latest.get('total_fat', 0))}g")
            c5.metric("Fiber", f"{int(latest.get('total_fiber', 0))}g")
        else:
            st.info(f"No nutrition data found for {active_user.upper()} today.")
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
                if st.button("Add to My Log"):
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
        # GUESTS can add records, but only ADMIN can permanently add to the main Food Library
        if st.session_state.is_admin:
            with st.form("new_food_form"):
                n_name = st.text_input("Name")
                nc, np = st.number_input("Cals", 0), st.number_input("Prot", 0)
                if st.form_submit_button("Create & Log"):
                    res = (
                        supabase.table("foods")
                        .insert({"food_name": n_name, "calories": nc, "protein_g": np})
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
            st.warning("Only Admin can add new items to the global Food Library.")

    st.divider()
    st.subheader(f"🗑️ {active_user.title()} Today's Entries")
    h_res = (
        supabase.table("daily_logs")
        .select("log_id, servings, user_id, foods(food_name, calories)")
        .eq("log_date", str(datetime.now().date()))
        .eq("user_id", active_user)
        .execute()
    )
    if h_res.data:
        for item in h_res.data:
            hc1, hc2, hc3 = st.columns([3, 1, 1])
            hc1.write(f"**{item['foods']['food_name']}**")
            hc2.write(f"{int(item['foods']['calories'] * item['servings'])} kcal")
            if hc3.button("🗑️", key=f"del_nut_{item['log_id']}"):
                supabase.table("daily_logs").delete().eq(
                    "log_id", item["log_id"]
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
        df_v = pd.DataFrame(res.data) if res.data else pd.DataFrame()

        if not df_v.empty:
            df_v["ts"] = pd.to_datetime(
                df_v["date"].astype(str)
                + " "
                + df_v["time"].fillna("00:00:00").astype(str)
            )

            st.subheader(f"📊 {active_user.title()} Weight Trend")
            w_df = df_v.dropna(subset=["weight_lb"])
            if not w_df.empty:
                w_chart = (
                    alt.Chart(w_df)
                    .mark_line(point=True, color="#3498db")
                    .encode(
                        x="ts:T", y=alt.Y("weight_lb:Q", scale=alt.Scale(zero=False))
                    )
                    .properties(height=350)
                )
                st.altair_chart(w_chart, use_container_width=True)

        st.divider()
        st.subheader("➕ Log New Metrics")
        c_bp, c_wt, c_gl = st.columns(3)
        now = datetime.now()

        with c_bp:
            with st.expander("❤️ Blood Pressure", expanded=True):
                sys, dia = (
                    st.number_input("Sys", 0, 250, 120),
                    st.number_input("Dia", 0, 150, 80),
                )
                if st.button("Log BP"):
                    supabase.table("health_metrics").insert(
                        {
                            "date": str(now.date()),
                            "time": now.strftime("%H:%M:%S"),
                            "blood_pressure_systolic": sys,
                            "blood_pressure_diastolic": dia,
                            "user_id": record_owner,
                        }
                    ).execute()
                    st.rerun()

        with c_wt:
            with st.expander("⚖️ Weight", expanded=True):
                wt_val = st.number_input("Lbs", 0.0, 500.0, 180.0)
                if st.button("Log Weight"):
                    supabase.table("health_metrics").insert(
                        {
                            "date": str(now.date()),
                            "time": now.strftime("%H:%M:%S"),
                            "weight_lb": wt_val,
                            "user_id": record_owner,
                        }
                    ).execute()
                    st.rerun()

        with c_gl:
            with st.expander("🩸 Glucose", expanded=True):
                gl_val = st.number_input("mg/dL", 0, 500, 100)
                if st.button("Log Glucose"):
                    supabase.table("health_metrics").insert(
                        {
                            "date": str(now.date()),
                            "time": now.strftime("%H:%M:%S"),
                            "blood_glucose": gl_val,
                            "user_id": record_owner,
                        }
                    ).execute()
                    st.rerun()
    except Exception as e:
        st.error(f"Health Load Error: {e}")

# --- TAB 3: ACTIVITY ---
with tab3:
    st.subheader(f"🏃 Log {active_user.title()} Activity")
    act_type = st.radio("Type", ["Strength", "Cardio"], horizontal=True)

    with st.form("act_form", clear_on_submit=True):
        a_date = st.date_input("Date")
        a_name = st.text_input("Exercise Name")
        c1, c2, c3 = st.columns(3)

        sets, reps, weight_val, dur, dist = 0, 0, 0, 0, 0
        if act_type == "Strength":
            sets, reps, weight_val = (
                c1.number_input("Sets", 0),
                c2.number_input("Reps", 0),
                c3.number_input("Weight", 0),
            )
        else:
            dur, dist = c1.number_input("Min", 0), c2.number_input("Miles", 0.0)

        if st.form_submit_button("Record Entry"):
            supabase.table("activity_logs").insert(
                {
                    "log_date": str(a_date),
                    "exercise_name": a_name,
                    "activity_category": act_type,
                    "sets": sets,
                    "reps": reps,
                    "weight_lb": weight_val,
                    "duration_min": dur,
                    "distance_miles": dist,
                    "user_id": record_owner,
                }
            ).execute()
            st.rerun()

    st.divider()
    st.subheader("📜 Recent History")
    a_res = (
        supabase.table("activity_logs")
        .select("*")
        .eq("user_id", active_user)
        .order("log_date", desc=True)
        .limit(10)
        .execute()
    )
    if a_res.data:
        st.dataframe(pd.DataFrame(a_res.data), use_container_width=True)

# --- TAB 4: REPORTS & MASTER VIEWER ---
with tab4:
    st.subheader("📊 Master Table Viewer")
    view_tbl = st.selectbox(
        "Select Table",
        ["daily_variance", "health_metrics", "activity_logs", "daily_logs", "foods"],
    )

    try:
        # Tables that have user_id get filtered by active_user
        query = supabase.table(view_tbl).select("*")
        if view_tbl != "foods":
            query = query.eq("user_id", active_user)

        # Determine sort column
        sc = (
            "date"
            if "date" in view_tbl or "variance" in view_tbl
            else "log_date"
            if "log" in view_tbl
            else "food_name"
        )
        tbl_res = query.order(sc, desc=True).limit(50).execute()

        if tbl_res.data:
            st.dataframe(pd.DataFrame(tbl_res.data), use_container_width=True)
        else:
            st.write("No records found for this user in this table.")
    except Exception as e:
        st.error(f"Viewer Error: {e}")

    st.divider()
    st.subheader("🚀 Master Export")
    if st.button(f"Generate Export for {active_user.upper()}"):
        try:
            nut = (
                supabase.table("daily_logs")
                .select("log_date, foods(food_name, calories)")
                .eq("user_id", active_user)
                .execute()
                .data
            )
            met = (
                supabase.table("health_metrics")
                .select("date, weight_lb, blood_glucose")
                .eq("user_id", active_user)
                .execute()
                .data
            )

            rows = []
            for n in nut:
                rows.append(
                    {
                        "Date": n["log_date"],
                        "Type": "Food",
                        "Label": n["foods"]["food_name"],
                        "Value": n["foods"]["calories"],
                    }
                )
            for m in met:
                if m["weight_lb"]:
                    rows.append(
                        {
                            "Date": m["date"],
                            "Type": "Weight",
                            "Label": "Weight",
                            "Value": m["weight_lb"],
                        }
                    )

            if rows:
                df_exp = pd.DataFrame(rows).sort_values("Date", ascending=False)
                st.download_button(
                    "📥 Download CSV",
                    df_exp.to_csv(index=False),
                    f"health_export_{active_user}.csv",
                )
                st.dataframe(df_exp)
        except Exception as e:
            st.error(f"Export Error: {e}")
