import streamlit as st
from supabase import create_client
from datetime import datetime
import pandas as pd
import altair as alt

# 1. Setup Connection
# Uses Streamlit Secrets for security
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.set_page_config(
    page_title="Health Dashboard Pro", layout="wide", initial_sidebar_state="collapsed"
)


# --- 1. ACCESS CONTROL ---
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.is_admin = False

    if not st.session_state.authenticated:
        st.title("🔒 Dashboard Access")
        col1, col2 = st.columns([1, 1])
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

# --- 2. DATA SCOPING LOGIC ---
# This determines which rows are fetched and which 'user_id' is stamped on new logs.
if st.session_state.is_admin:
    view_mode = st.sidebar.radio(
        "🔎 View Mode", ["My Data (Admin)", "Tester Data (Guest)"]
    )
    active_user = "admin" if "Admin" in view_mode else "guest"
else:
    active_user = "guest"

# Admin can toggle views, but they always record as 'admin' if that's who they logged in as.
record_owner = "admin" if st.session_state.is_admin else "guest"

# --- 3. TARGET CONSTANTS ---
TARGET_CALORIES = 1800
TARGET_PROTEIN = 160
TARGET_FAT_MAX = 60
TARGET_FIBER_MIN = 30
NC_LIMIT = 100

tab1, tab2, tab3, tab4 = st.tabs(
    ["🍴 Nutrition", "🩺 Health Metrics", "🏃 Activity", "📊 Reports"]
)

# --- TAB 1: NUTRITION ---
with tab1:
    try:
        # Fetch the calculated daily variance for the active user
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
                f"Status for {latest.get('date', 'Today')} ({active_user.upper()})"
            )
            c1, c2, c3, c4, c5 = st.columns(5)

            # Numeric Safety
            cals = float(latest.get("total_calories") or 0)
            prot = float(latest.get("total_protein") or 0)
            net_c = float(latest.get("total_net_carbs") or 0)
            fat = float(latest.get("total_fat") or 0)
            fib = float(latest.get("total_fiber") or 0)

            # Logic Indicators
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
        st.error(f"Nutrition Summary Error: {e}")

    st.divider()
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("🍴 Log from Library")
        f_query = supabase.table("foods").select("*").order("food_name").execute()
        if f_query.data:
            f_dict = {f["food_name"]: f for f in f_query.data}
            sel = st.selectbox("Search Foods", options=list(f_dict.keys()), index=None)
            if sel:
                food = f_dict[sel]
                srv = st.number_input("Servings", 0.1, 10.0, 1.0, step=0.1)
                if st.button("Log Selection"):
                    supabase.table("daily_logs").insert(
                        {
                            "food_id": food.get("food_id") or food.get("id"),
                            "servings": srv,
                            "log_date": str(datetime.now().date()),
                            "user_id": record_owner,
                        }
                    ).execute()
                    st.rerun()

    with col_b:
        if st.session_state.is_admin:
            st.subheader("🆕 Admin: Add New Food")
            with st.form("new_food_form", clear_on_submit=True):
                n_name = st.text_input("Name")
                n_c, n_p, n_f = st.columns(3)
                v_c = n_c.number_input("Cals", 0)
                v_p = n_p.number_input("Prot", 0)
                v_f = n_f.number_input("Fat", 0)
                if st.form_submit_button("Save to Database"):
                    res = (
                        supabase.table("foods")
                        .insert(
                            {
                                "food_name": n_name,
                                "calories": v_c,
                                "protein_g": v_p,
                                "fat_g": v_f,
                            }
                        )
                        .execute()
                    )
                    st.success("Food added to master library.")

    st.subheader("📜 Today's History")
    h_res = (
        supabase.table("daily_logs")
        .select("*, foods(food_name, calories)")
        .eq("log_date", str(datetime.now().date()))
        .eq("user_id", active_user)
        .execute()
    )
    if h_res.data:
        for item in h_res.data:
            hc1, hc2, hc3 = st.columns([3, 1, 1])
            f_node = item.get("foods") or {}
            hc1.write(f"**{f_node.get('food_name', 'Unknown')}**")
            hc2.write(f"{int(f_node.get('calories', 0) * item['servings'])} kcal")
            l_id = item.get("log_id") or item.get("id")
            if hc3.button("🗑️", key=f"del_{l_id}"):
                supabase.table("daily_logs").delete().eq("log_id", l_id).execute()
                st.rerun()

# --- TAB 2: HEALTH METRICS ---
with tab2:
    try:
        m_res = (
            supabase.table("health_metrics")
            .select("*")
            .eq("user_id", active_user)
            .order("date", desc=False)
            .execute()
        )
        df_h = pd.DataFrame(m_res.data) if m_res.data else pd.DataFrame()

        if not df_h.empty:
            df_h["ts"] = pd.to_datetime(
                df_h["date"].astype(str)
                + " "
                + df_h["time"].fillna("00:00:00").astype(str)
            )

            st.subheader("📉 Weight Trend")
            w_chart = (
                alt.Chart(df_h.dropna(subset=["weight_lb"]))
                .mark_line(point=True, color="#3498db")
                .encode(
                    x=alt.X("ts:T", title="Time"),
                    y=alt.Y("weight_lb:Q", scale=alt.Scale(zero=False), title="Lbs"),
                    tooltip=["date", "weight_lb"],
                )
                .properties(height=300)
            )
            st.altair_chart(w_chart, use_container_width=True)

        st.divider()
        st.subheader("➕ Manual Metric Entry")
        with st.form("metric_form"):
            c1, c2, c3 = st.columns(3)
            in_w = c1.number_input("Weight", 0.0)
            in_sys = c2.number_input("Systolic", 0)
            in_dia = c3.number_input("Diastolic", 0)
            if st.form_submit_button("Record Metrics"):
                supabase.table("health_metrics").insert(
                    {
                        "date": str(datetime.now().date()),
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "weight_lb": in_w if in_w > 0 else None,
                        "blood_pressure_systolic": in_sys if in_sys > 0 else None,
                        "blood_pressure_diastolic": in_dia if in_dia > 0 else None,
                        "user_id": record_owner,
                    }
                ).execute()
                st.rerun()
    except Exception as e:
        st.error(f"Health Tab Error: {e}")

# --- TAB 3: ACTIVITY ---
with tab3:
    st.subheader(f"🏃 Workout Log ({active_user.upper()})")
    with st.form("workout_form"):
        w_c1, w_c2 = st.columns(2)
        ex_name = w_c1.text_input("Exercise")
        ex_cat = w_c2.selectbox("Type", ["Strength", "Cardio", "Endurance"])

        m1, m2, m3 = st.columns(3)
        w_sets = m1.number_input("Sets", 0)
        w_reps = m2.number_input("Reps", 0)
        w_lbs = m3.number_input("Weight (lbs)", 0)

        if st.form_submit_button("Log Workout"):
            supabase.table("activity_logs").insert(
                {
                    "log_date": str(datetime.now().date()),
                    "exercise_name": ex_name,
                    "activity_category": ex_cat,
                    "sets": w_sets,
                    "reps": w_reps,
                    "weight_lb": w_lbs,
                    "user_id": record_owner,
                }
            ).execute()
            st.rerun()

# --- TAB 4: REPORTS ---
with tab4:
    st.subheader("📂 Historical Data")
    report_tbl = st.selectbox(
        "Select View", ["daily_logs", "health_metrics", "activity_logs"]
    )

    # Filter by user
    raw_res = (
        supabase.table(report_tbl)
        .select("*")
        .eq("user_id", active_user)
        .order("created_at", desc=True)
        .limit(100)
        .execute()
    )
    if raw_res.data:
        st.dataframe(pd.DataFrame(raw_res.data), use_container_width=True)
    else:
        st.info("No records found for this user.")
