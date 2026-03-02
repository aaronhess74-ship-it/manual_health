import streamlit as st
from supabase import create_client
from datetime import datetime
import pandas as pd
import altair as alt

# 1. Setup Connection
# Ensure these are in your .streamlit/secrets.toml
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
# If Admin: They can toggle between their data and guest data
if st.session_state.is_admin:
    view_mode = st.sidebar.radio(
        "🔎 View Mode", ["My Data (Admin)", "Tester Data (Guest)"]
    )
    active_user = "admin" if "Admin" in view_mode else "guest"
else:
    # If Guest: They only ever see 'guest' data
    active_user = "guest"

# When writing new data, Admin writes to 'admin', Guest writes to 'guest'
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
        # Fetch latest variance for the active user
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
            st.subheader(
                f"Daily Status: {latest.get('date', 'Today')} ({active_user.upper()})"
            )
            c1, c2, c3, c4, c5 = st.columns(5)

            # Convert to float safely
            cals = float(latest.get("total_calories") or 0)
            prot = float(latest.get("total_protein") or 0)
            net_c = float(latest.get("total_net_carbs") or 0)
            fat = float(latest.get("total_fat") or 0)
            fib = float(latest.get("total_fiber") or 0)

            # Status Dots
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
            f_dict = {f.get("food_name"): f for f in f_query.data}
            sel = st.selectbox("Select Item", options=list(f_dict.keys()), index=None)
            if sel:
                srv = st.number_input("Servings", 0.1, 10.0, 1.0)
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
            with st.form("add_food"):
                fn = st.text_input("Food Name")
                f_c1, f_c2, f_c3 = st.columns(3)
                v_ca = f_c1.number_input("Cals", 0)
                v_pr = f_c2.number_input("Prot", 0)
                v_nc = f_c3.number_input("NetC", 0)
                if st.form_submit_button("Create & Log"):
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
                        f_id = res.data[0].get("id")
                        supabase.table("daily_logs").insert(
                            {
                                "food_id": f_id,
                                "servings": 1.0,
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

            # Trend Chart
            st.subheader("📈 Weight Trend")
            w_chart = (
                alt.Chart(df.dropna(subset=["weight_lb"]))
                .mark_line(point=True)
                .encode(
                    x="ts:T",
                    y=alt.Y("weight_lb:Q", scale=alt.Scale(zero=False)),
                    tooltip=["date", "weight_lb"],
                )
                .properties(height=250)
            )
            st.altair_chart(w_chart, use_container_width=True)

            # Manual Entry
            st.divider()
            st.subheader("➕ New Entry")
            with st.form("health_form"):
                h_c1, h_c2, h_c3 = st.columns(3)
                new_w = h_c1.number_input("Weight (lbs)", 0.0)
                new_sys = h_c2.number_input("BP Systolic", 0)
                new_dia = h_c3.number_input("BP Diastolic", 0)
                if st.form_submit_button("Save Metric"):
                    supabase.table("health_metrics").insert(
                        {
                            "date": str(datetime.now().date()),
                            "time": datetime.now().strftime("%H:%M:%S"),
                            "weight_lb": new_w if new_w > 0 else None,
                            "blood_pressure_systolic": new_sys if new_sys > 0 else None,
                            "blood_pressure_diastolic": new_dia
                            if new_dia > 0
                            else None,
                            "user_id": record_owner,
                        }
                    ).execute()
                    st.rerun()
    except Exception as e:
        st.error(f"Health Error: {e}")

# --- TAB 3: ACTIVITY ---
with tab3:
    st.subheader(f"🏃 Activity Logs ({active_user.upper()})")
    with st.form("act_form"):
        f_c1, f_c2 = st.columns(2)
        ex_name = f_c1.text_input("Exercise Name")
        ex_cat = f_c2.selectbox("Category", ["Strength", "Cardio", "Endurance"])

        m1, m2, m3 = st.columns(3)
        sets = m1.number_input("Sets", 0)
        reps = m2.number_input("Reps", 0)
        weight = m3.number_input("Weight (lbs)", 0)

        if st.form_submit_button("Log Activity"):
            supabase.table("activity_logs").insert(
                {
                    "log_date": str(datetime.now().date()),
                    "exercise_name": ex_name,
                    "activity_category": ex_cat,
                    "sets": sets,
                    "reps": reps,
                    "weight_lb": weight,
                    "user_id": record_owner,
                }
            ).execute()
            st.rerun()

# --- TAB 4: REPORTS ---
with tab4:
    st.subheader("📊 Data Explorer")
    tbl = st.selectbox(
        "Select Table", ["daily_logs", "health_metrics", "activity_logs", "foods"]
    )

    query = supabase.table(tbl).select("*")
    if tbl != "foods":
        query = query.eq("user_id", active_user)

    report_res = query.order("created_at", desc=True).limit(50).execute()
    if report_res.data:
        st.dataframe(pd.DataFrame(report_res.data), use_container_width=True)
