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


# --- ACCESS CONTROL FUNCTION ---
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.is_admin = False

    if not st.session_state.authenticated:
        st.markdown("### 🔐 Health Dashboard Access")
        with st.form("login_form"):
            password = st.text_input("Enter Access Code", type="password")
            if st.form_submit_button("Login"):
                if password == st.secrets["ADMIN_PASSWORD"]:
                    st.session_state.authenticated, st.session_state.is_admin = (
                        True,
                        True,
                    )
                    st.rerun()
                elif password == st.secrets["GUEST_PASSWORD"]:
                    st.session_state.authenticated, st.session_state.is_admin = (
                        False,
                        False,
                    )  # Guest
                    st.session_state.authenticated = True  # Allow entry
                    st.rerun()
                else:
                    st.error("Invalid Access Code")
        return False
    return True


if not check_password():
    st.stop()

# --- STEP 3: MASTER TOGGLE (SIDEBAR) ---
# Determine which data to show based on login and toggle
view_mode = "admin"
if st.session_state.is_admin:
    view_mode = st.sidebar.radio(
        "🔎 View Data For:", ["My Data (Admin)", "Guest Data"], index=0
    )
    view_mode = "admin" if "Admin" in view_mode else "guest"
else:
    view_mode = "guest"
    st.sidebar.info("Logged in as Guest (Read-Only Mode)")

# Global User Tag for Writing
user_tag = "admin" if st.session_state.is_admin else "guest"

st.title("💪 My Health Dashboard")

# --- TARGETS ---
TARGET_CALORIES, TARGET_PROTEIN = 1800, 160
TARGET_FAT_MAX, TARGET_NET_CARBS, TARGET_FIBER_MIN = 60, 60, 30

tab1, tab2, tab3, tab4 = st.tabs(
    ["🍴 Nutrition", "🩺 Health Metrics", "🏃 Activity", "📊 Reports"]
)

# --- TAB 1: NUTRITION ---
with tab1:
    try:
        # STEP 2: Filter View by user_id
        response = (
            supabase.table("daily_variance")
            .select("*")
            .eq("user_id", view_mode)
            .order("date", desc=True)
            .limit(1)
            .execute()
        )
        if response.data:
            latest = response.data[0]
            st.subheader(f"Status for {latest['date']} ({view_mode.title()})")
            c1, c2, c3, c4, c5 = st.columns(5)
            cals, prot, net_c = (
                float(latest.get("total_calories", 0)),
                float(latest.get("total_protein", 0)),
                float(latest.get("total_net_carbs", 0)),
            )

            def get_lbl(curr, target, ceil=True):
                if ceil:
                    return "🔴 OVER" if curr > target else "🟢 OK"
                return "🟢 GOAL" if curr >= target else "🔴 LOW"

            c1.metric(f"Calories {get_lbl(cals, TARGET_CALORIES)}", f"{int(cals)}")
            c2.metric(
                f"Protein {get_lbl(prot, TARGET_PROTEIN, False)}", f"{int(prot)}g"
            )
            c3.metric(f"Net Carbs {get_lbl(net_c, TARGET_NET_CARBS)}", f"{int(net_c)}g")
            c4.metric("Fat", f"{int(latest.get('total_fat', 0))}g")
            c5.metric("Fiber", f"{int(latest.get('total_fiber', 0))}g")
    except Exception as e:
        st.error(f"Nutrition Error: {e}")

    st.divider()

    if st.session_state.is_admin:
        st.subheader("⚡ Quick Log")
        try:
            # Note: daily_logs needs the user_id tag on write
            recent_res = (
                supabase.table("daily_logs")
                .select("food_id, foods(food_name)")
                .eq("user_id", "admin")
                .order("log_id", desc=True)
                .limit(20)
                .execute()
            )
            if recent_res.data:
                seen = {r["food_id"] for r in recent_res.data if r["foods"]}
                quick_foods = [
                    {"id": r["food_id"], "name": r["foods"]["food_name"]}
                    for r in recent_res.data
                    if r["foods"]
                ][:5]
                cols = st.columns(len(quick_foods))
                for i, f in enumerate(quick_foods):
                    if cols[i].button(f"➕ {f['name']}", key=f"q_{f['id']}"):
                        supabase.table("daily_logs").insert(
                            {
                                "food_id": f["id"],
                                "servings": 1.0,
                                "log_date": str(datetime.now().date()),
                                "user_id": "admin",
                            }
                        ).execute()
                        st.rerun()
        except:
            pass

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("🍴 Log Existing Food")
        if st.session_state.is_admin:
            f_query = supabase.table("foods").select("*").order("food_name").execute()
            f_dict = {f["food_name"]: f for f in f_query.data}
            sel = st.selectbox(
                "Search Library...", options=list(f_dict.keys()), index=None
            )
            if sel:
                srv = st.number_input("Servings", 0.1, 10.0, 1.0)
                if st.button("Log Meal Entry"):
                    supabase.table("daily_logs").insert(
                        {
                            "food_id": f_dict[sel]["food_id"],
                            "servings": srv,
                            "log_date": str(datetime.now().date()),
                            "user_id": "admin",
                        }
                    ).execute()
                    st.rerun()
        else:
            st.info("Logging disabled for Guest.")

    with col_b:
        st.subheader("🆕 Create New Food")
        if st.session_state.is_admin:
            with st.form("new_f", clear_on_submit=True):
                n_name = st.text_input("Food Name")
                nc, np = st.number_input("Calories", 0), st.number_input("Protein", 0)
                if st.form_submit_button("Save & Log"):
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
                                "user_id": "admin",
                            }
                        ).execute()
                        st.rerun()

    st.subheader(f"📜 {view_mode.title()} History")
    h_res = (
        supabase.table("daily_logs")
        .select("log_id, servings, foods(food_name, calories)")
        .eq("log_date", str(datetime.now().date()))
        .eq("user_id", view_mode)
        .execute()
    )
    if h_res.data:
        for item in h_res.data:
            hc1, hc2, hc3 = st.columns([3, 1, 1])
            hc1.write(f"**{item['foods']['food_name']}**")
            hc2.write(f"{int(item['foods']['calories'] * item['servings'])} kcal")
            if st.session_state.is_admin and hc3.button(
                "🗑️", key=f"del_nut_{item['log_id']}"
            ):
                supabase.table("daily_logs").delete().eq(
                    "log_id", item["log_id"]
                ).execute()
                st.rerun()

# --- TAB 2: HEALTH METRICS ---
with tab2:
    try:
        # STEP 2: Filter Trends by user_id
        res = (
            supabase.table("health_metrics")
            .select("*")
            .eq("user_id", view_mode)
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
            st.subheader(f"📊 {view_mode.title()} Trends")
            w_df = df_v.dropna(subset=["weight_lb"])
            if not w_df.empty:
                w_chart = (
                    alt.Chart(w_df)
                    .mark_line(point=True)
                    .encode(
                        x="ts:T", y=alt.Y("weight_lb:Q", scale=alt.Scale(zero=False))
                    )
                    .properties(height=350)
                )
                st.altair_chart(w_chart, use_container_width=True)

        st.divider()
        if st.session_state.is_admin:
            st.subheader("➕ Add New Measurement")
            col_bp, col_wt, col_gl = st.columns(3)
            now = datetime.now()
            with col_bp:
                with st.expander("❤️ BP", expanded=True):
                    sys, dia = (
                        st.number_input("Systolic", 0, 250, 120),
                        st.number_input("Diastolic", 0, 150, 80),
                    )
                    if st.button("Log BP"):
                        supabase.table("health_metrics").insert(
                            {
                                "date": str(now.date()),
                                "time": now.strftime("%H:%M:%S"),
                                "blood_pressure_systolic": sys,
                                "blood_pressure_diastolic": dia,
                                "user_id": "admin",
                            }
                        ).execute()
                        st.rerun()
            with col_wt:
                with st.expander("⚖️ Weight", expanded=True):
                    wt_in = st.number_input("Weight (lbs)", 0.0, 500.0, 180.0)
                    if st.button("Log Weight"):
                        supabase.table("health_metrics").insert(
                            {
                                "date": str(now.date()),
                                "time": now.strftime("%H:%M:%S"),
                                "weight_lb": wt_in,
                                "user_id": "admin",
                            }
                        ).execute()
                        st.rerun()
            # ... (similar for glucose)
    except Exception as e:
        st.error(f"Health error: {e}")

# --- TAB 3: ACTIVITY ---
with tab3:
    st.subheader("🏃 Log Activity")
    if st.session_state.is_admin:
        act_type = st.radio("Category", ["Strength", "Cardio"], horizontal=True)
        with st.form("act_form", clear_on_submit=True):
            a_date, a_name = st.date_input("Date"), st.text_input("Exercise")
            c1, c2, c3 = st.columns(3)
            sets, reps, weight_val = (
                c1.number_input("Sets", 0),
                c2.number_input("Reps", 0),
                c3.number_input("Weight", 0),
            )
            if st.form_submit_button("Record"):
                # STEP 2: Tag with user_id
                payload = {
                    "log_date": str(a_date),
                    "exercise_name": a_name,
                    "activity_category": act_type,
                    "sets": int(sets),
                    "reps": int(reps),
                    "weight_lb": int(weight_val),
                    "user_id": "admin",
                }
                supabase.table("activity_logs").insert(payload).execute()
                st.rerun()

    st.subheader(f"📜 {view_mode.title()} History")
    a_res = (
        supabase.table("activity_logs")
        .select("*")
        .eq("user_id", view_mode)
        .order("log_date", desc=True)
        .execute()
    )
    if a_res.data:
        st.dataframe(pd.DataFrame(a_res.data), use_container_width=True)

# --- TAB 4: REPORTS ---
with tab4:
    st.subheader("🚀 Export Data")
    if st.session_state.is_admin:
        # Only export the CURRENT view mode's data
        if st.button(f"Download {view_mode.title()} CSV"):
            # ... (existing export logic filtered by view_mode)
            st.info("Exporting filtered data...")
