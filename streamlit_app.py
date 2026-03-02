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

            c1.metric("Calories", f"{int(cals)}", f"{int(TARGET_CALORIES - cals)} Left")
            c2.metric(
                "Protein", f"{int(prot)}g", f"{int(prot - TARGET_PROTEIN)}g vs Goal"
            )
            c3.metric("Net Carbs", f"{int(net_c)}g", f"Limit: {TARGET_NET_CARBS}g")
            c4.metric("Fat", f"{int(fat)}g", f"Limit: {TARGET_FAT_MAX}g")
            c5.metric("Fiber", f"{int(fib)}g", f"Min: {TARGET_FIBER_MIN}g")
    except Exception as e:
        st.error(f"Nutrition Load Error: {e}")

    st.divider()
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("### 🔎 Search Food Library")
        f_query = supabase.table("foods").select("*").order("food_name").execute()
        if f_query.data:
            f_dict = {f["food_name"]: f for f in f_query.data}
            sel = st.selectbox("Select Item", options=list(f_dict.keys()), index=None)
            if sel:
                srv = st.number_input("Servings", 0.1, 10.0, 1.0)
                if st.button("Log Selected Food"):
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
        st.markdown("### ➕ Custom Food Item")
        if st.session_state.is_admin:
            with st.form("new_food_form"):
                n_name = st.text_input("Food Name")
                f_c1, f_c2, f_c3, f_c4, f_c5 = st.columns(5)
                new_c = f_c1.number_input("Cals", 0)
                new_p = f_c2.number_input("Prot", 0)
                new_f = f_c3.number_input("Fat", 0)
                new_nc = f_c4.number_input("NetC", 0)
                new_fib = f_c5.number_input("Fib", 0)
                if st.form_submit_button("Create & Log Item"):
                    res = (
                        supabase.table("foods")
                        .insert(
                            {
                                "food_name": n_name,
                                "calories": new_c,
                                "protein_g": new_p,
                                "fat_g": new_f,
                                "net_carbs_g": new_nc,
                                "fiber_g": new_fib,
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
            st.info("Custom food creation is available for Admin users.")

    st.divider()
    st.subheader("🗑️ Today's Entries")
    log_res = (
        supabase.table("daily_logs")
        .select("log_id, servings, foods(food_name, calories)")
        .eq("log_date", str(datetime.now().date()))
        .eq("user_id", active_user)
        .execute()
    )
    if log_res.data:
        for row in log_res.data:
            lc1, lc2, lc3 = st.columns([3, 1, 1])
            lc1.write(f"**{row['foods']['food_name']}**")
            lc2.write(f"{int(row['foods']['calories'] * row['servings'])} kcal")
            if lc3.button("🗑️", key=f"del_{row['log_id']}"):
                supabase.table("daily_logs").delete().eq(
                    "log_id", row["log_id"]
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

            # --- LATEST STATUS LOGIC ---
            # We find the last non-null entry for each metric independently
            last_w = (
                df.dropna(subset=["weight_lb"]).iloc[-1]
                if not df["weight_lb"].dropna().empty
                else None
            )
            last_bp = (
                df.dropna(subset=["blood_pressure_systolic"]).iloc[-1]
                if not df["blood_pressure_systolic"].dropna().empty
                else None
            )
            last_g = (
                df.dropna(subset=["blood_glucose"]).iloc[-1]
                if not df["blood_glucose"].dropna().empty
                else None
            )

            st.subheader("📋 Latest Health Status")
            s1, s2, s3 = st.columns(3)

            if last_w is not None:
                w_val = last_w["weight_lb"]
                w_icon = "🟢" if w_val < 200 else "🟡" if w_val < 220 else "🔴"
                s1.metric("Weight", f"{w_val} lbs", f"{w_icon} Target < 200")
                s1.caption(f"Logged: {last_w['display_time']}")

            if last_bp is not None:
                sys, dia = (
                    last_bp["blood_pressure_systolic"],
                    last_bp["blood_pressure_diastolic"],
                )
                bp_icon = (
                    "🟢"
                    if sys < 130 and dia < 85
                    else "🟡"
                    if sys < 140 and dia < 90
                    else "🔴"
                )
                s2.metric(
                    "Blood Pressure",
                    f"{int(sys)}/{int(dia)}",
                    f"{bp_icon} Target < 130/85",
                )
                s2.caption(f"Logged: {last_bp['display_time']}")

            if last_g is not None:
                glu = last_g["blood_glucose"]
                g_icon = "🟢" if glu < 100 else "🟡" if glu < 125 else "🔴"
                s3.metric("Glucose", f"{int(glu)} mg/dL", f"{g_icon} Target < 100")
                s3.caption(f"Logged: {last_g['display_time']}")

            st.divider()
            st.subheader("📊 Trends")

            def draw_static_chart(data, y_col, y_label, y_domain, color):
                base = alt.Chart(data).encode(
                    x=alt.X(
                        "ts:T",
                        title="Timeline",
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
                    base.mark_line(color=color, opacity=0.4)
                    + base.mark_point(color=color, size=60, filled=True)
                ).properties(height=250)

            if not df.dropna(subset=["weight_lb"]).empty:
                st.altair_chart(
                    draw_static_chart(
                        df.dropna(subset=["weight_lb"]),
                        "weight_lb",
                        "Lbs",
                        [100, 300],
                        "#3498db",
                    ),
                    use_container_width=True,
                )

            if not df.dropna(subset=["blood_glucose"]).empty:
                st.altair_chart(
                    draw_static_chart(
                        df.dropna(subset=["blood_glucose"]),
                        "blood_glucose",
                        "mg/dL",
                        [50, 250],
                        "#e74c3c",
                    ),
                    use_container_width=True,
                )

        st.divider()
        st.subheader("➕ Log Health Records")
        now = datetime.now()
        c_wt, c_bp, c_gl = st.columns(3)

        with c_wt:
            with st.expander("⚖️ Weight Entry", expanded=True):
                w_in = st.number_input("Weight", 0.0, 500.0, 0.0, key="w_in")
                w_d = st.date_input("Date", now, key="w_d")
                w_t = st.time_input("Time", now, key="w_t")
                if st.button("Save Weight"):
                    supabase.table("health_metrics").insert(
                        {
                            "date": str(w_d),
                            "time": w_t.strftime("%H:%M:%S"),
                            "weight_lb": w_in,
                            "user_id": record_owner,
                        }
                    ).execute()
                    st.rerun()
        with c_bp:
            with st.expander("❤️ BP Entry", expanded=True):
                sys_in = st.number_input("Systolic", 0, 250, 0, key="sys_in")
                dia_in = st.number_input("Diastolic", 0, 250, 0, key="dia_in")
                bp_d = st.date_input("Date", now, key="bp_d")
                bp_t = st.time_input("Time", now, key="bp_t")
                if st.button("Save BP"):
                    supabase.table("health_metrics").insert(
                        {
                            "date": str(bp_d),
                            "time": bp_t.strftime("%H:%M:%S"),
                            "blood_pressure_systolic": sys_in,
                            "blood_pressure_diastolic": dia_in,
                            "user_id": record_owner,
                        }
                    ).execute()
                    st.rerun()
        with c_gl:
            with st.expander("🩸 Glucose Entry", expanded=True):
                gl_in = st.number_input("Glucose", 0, 500, 0, key="gl_in")
                gl_d = st.date_input("Date", now, key="gl_d")
                gl_t = st.time_input("Time", now, key="gl_t")
                if st.button("Save Glucose"):
                    supabase.table("health_metrics").insert(
                        {
                            "date": str(gl_d),
                            "time": gl_t.strftime("%H:%M:%S"),
                            "blood_glucose": gl_in,
                            "user_id": record_owner,
                        }
                    ).execute()
                    st.rerun()
    except Exception as e:
        st.error(f"Health Tab Error: {e}")

# --- TAB 3: ACTIVITY ---
with tab3:
    st.subheader(f"🏃 Log Activity ({active_user.upper()})")
    act_cat = st.radio("Category", ["Strength", "Cardio", "Endurance"], horizontal=True)

    with st.form("act_log_form", clear_on_submit=True):
        f1, f2 = st.columns(2)
        d_val = f1.date_input("Date", datetime.now())
        n_val = f2.text_input("Exercise Name")

        c1, c2, c3, c4, c5 = st.columns(5)
        # Conditional logic for fields
        s_val = (
            c1.number_input("Sets", 0) if act_cat in ["Strength", "Endurance"] else 0
        )
        r_val = (
            c2.number_input("Reps", 0) if act_cat in ["Strength", "Endurance"] else 0
        )
        w_val = (
            c3.number_input("Weight", 0) if act_cat in ["Strength", "Endurance"] else 0
        )
        dur_val = (
            c4.number_input("Mins", 0) if act_cat in ["Cardio", "Endurance"] else 0
        )
        dis_val = (
            c5.number_input("Miles", 0.0) if act_cat in ["Cardio", "Endurance"] else 0
        )

        if st.form_submit_button("Log Activity"):
            supabase.table("activity_logs").insert(
                {
                    "log_date": str(d_val),
                    "exercise_name": n_val,
                    "activity_category": act_cat,
                    "sets": s_val,
                    "reps": r_val,
                    "weight_lb": w_val,
                    "duration_min": dur_val,
                    "distance_miles": dis_val,
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
        .limit(15)
        .execute()
    )
    if a_res.data:
        st.dataframe(pd.DataFrame(a_res.data), use_container_width=True)

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
                    file_name="health_data.csv",
                )
        except Exception as e:
            st.error(f"Export Error: {e}")
