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
            st.subheader(
                f"Daily Status: {latest.get('date', 'Today')} ({active_user.upper()})"
            )
            c1, c2, c3, c4, c5 = st.columns(5)

            # Safe numeric conversion
            cals, prot, net_c = (
                float(latest.get("total_calories") or 0),
                float(latest.get("total_protein") or 0),
                float(latest.get("total_net_carbs") or 0),
            )
            fat, fib = (
                float(latest.get("total_fat") or 0),
                float(latest.get("total_fiber") or 0),
            )

            # Status Indicators
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
        st.error(f"Nutrition Error: {e}")

    st.divider()
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("### 🔎 Library Search")
        f_query = supabase.table("foods").select("*").order("food_name").execute()
        if f_query.data:
            f_dict = {f["food_name"]: f for f in f_query.data}
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
                fn = st.text_input("New Food Name")
                f_c1, f_c2, f_c3 = st.columns(3)
                v_ca, v_pr, v_nc = (
                    f_c1.number_input("Cals", 0),
                    f_c2.number_input("Prot", 0),
                    f_c3.number_input("NetC", 0),
                )
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

            st.subheader("📊 Trends")
            # Fixed height avoids resizing on scroll
            w_chart = (
                alt.Chart(df.dropna(subset=["weight_lb"]))
                .mark_line(point=True, color="#3498db")
                .encode(x="ts:T", y=alt.Y("weight_lb:Q", scale=alt.Scale(zero=False)))
                .properties(height=250)
            )
            st.altair_chart(w_chart, use_container_width=True)

        st.divider()
        st.subheader("➕ Manual Entries")
        m_c1, m_c2, m_c3 = st.columns(3)
        with m_c1:
            wv = st.number_input("Weight (lbs)", 0.0)
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
            bs, bd = st.number_input("Systolic", 0), st.number_input("Diastolic", 0)
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
            gv = st.number_input("Glucose", 0)
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
        st.error(f"Health Error: {e}")

# --- TAB 3: ACTIVITY ---
with tab3:
    st.subheader(f"🏃 Workout Log")
    with st.form("activity_form"):
        f1, f2 = st.columns(2)
        nm, cat = (
            f1.text_input("Exercise"),
            f2.selectbox("Type", ["Strength", "Cardio", "Endurance"]),
        )
        s, r, w = st.columns(3)
        v_s, v_r, v_w = (
            s.number_input("Sets", 0),
            r.number_input("Reps", 0),
            w.number_input("Weight", 0),
        )
        if st.form_submit_button("Log Activity"):
            supabase.table("activity_logs").insert(
                {
                    "log_date": str(datetime.now().date()),
                    "exercise_name": nm,
                    "activity_category": cat,
                    "sets": v_s,
                    "reps": v_r,
                    "weight_lb": v_w,
                    "user_id": record_owner,
                }
            ).execute()
            st.rerun()

# --- TAB 4: REPORTS ---
with tab4:
    st.subheader("📥 Data Management")
    tbl_name = st.selectbox(
        "Select Table", ["health_metrics", "daily_logs", "activity_logs", "foods"]
    )

    query = supabase.table(tbl_name).select("*")
    if tbl_name != "foods":
        query = query.eq("user_id", active_user)

    rep_data = query.order("created_at", desc=True).execute()
    if rep_data.data:
        df_rep = pd.DataFrame(rep_data.data)
        st.dataframe(df_rep, use_container_width=True)

        # WORKING CSV EXPORT
        csv = df_rep.to_csv(index=False).encode("utf-8")
        st.download_button(
            label=f"Export {tbl_name} to CSV",
            data=csv,
            file_name=f"{active_user}_{tbl_name}_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )
