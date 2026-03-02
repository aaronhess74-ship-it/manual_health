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

# Record Owner ensures that even if Admin views Guest data, they write to their own account
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

# --- TAB 2: HEALTH METRICS ---
with tab2:
    try:
        h_res = (
            supabase.table("health_metrics")
            .select("*")
            .eq("user_id", active_user)
            .order("date", desc=False)
            .execute()
        )
        df_h = pd.DataFrame(h_res.data) if h_res.data else pd.DataFrame()

        if not df_h.empty:
            df_h["ts"] = pd.to_datetime(
                df_h["date"].astype(str)
                + " "
                + df_h["time"].fillna("00:00:00").astype(str)
            )

            st.subheader("📊 Trends & Progress")
            # FIXED HEIGHT CHARTS
            w_chart = (
                alt.Chart(df_h.dropna(subset=["weight_lb"]))
                .mark_line(point=True, color="#3498db")
                .encode(
                    x=alt.X("ts:T", title="Timeline"),
                    y=alt.Y(
                        "weight_lb:Q", scale=alt.Scale(zero=False), title="Weight (lbs)"
                    ),
                    tooltip=["date", "weight_lb"],
                )
                .properties(height=250)
            )
            st.altair_chart(w_chart, use_container_width=True)

        st.divider()
        st.subheader("➕ Manual Health Entry")
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
    except Exception as e:
        st.error(f"Health Tab Error: {e}")

# --- TAB 3: ACTIVITY ---
with tab3:
    st.subheader(f"🏃 Activity Logs ({active_user.upper()})")
    with st.form("activity_form", clear_on_submit=True):
        f1, f2 = st.columns(2)
        ex_name = f1.text_input("Exercise Name")
        ex_cat = f2.selectbox("Category", ["Strength", "Cardio", "Endurance"])

        m1, m2, m3, m4 = st.columns(4)
        v_sets = m1.number_input("Sets", 0)
        v_reps = m2.number_input("Reps", 0)
        v_weight = m3.number_input("Weight", 0)
        v_dist = m4.number_input("Miles/Mins", 0.0)

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

# --- TAB 4: REPORTS & EXPORT ---
with tab4:
    st.subheader("📥 Master Report & Data Export")

    report_tbl = st.selectbox(
        "Select Data Source", ["health_metrics", "daily_logs", "activity_logs", "foods"]
    )

    # Logic to filter or show all
    q = supabase.table(report_tbl).select("*")
    if report_tbl != "foods":
        q = q.eq("user_id", active_user)

    rep_res = q.order("created_at", desc=True).execute()

    if rep_res.data:
        df_final = pd.DataFrame(rep_res.data)
        st.dataframe(df_final, use_container_width=True)

        # MASTER EXPORT BUTTON
        csv = df_final.to_csv(index=False).encode("utf-8")
        st.download_button(
            label=f"💾 Download {report_tbl.replace('_', ' ').title()} as CSV",
            data=csv,
            file_name=f"{active_user}_{report_tbl}_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )
    else:
        st.info("No data found for this selection.")
