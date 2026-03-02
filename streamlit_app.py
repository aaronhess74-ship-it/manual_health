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

            # CRITICAL FIX: The "or 0" prevents crashes if the database returns a blank/null cell
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
                f"Fat {fat_dot}",
                f"{int(fat)}g",
                f"{int(fat - TARGET_FAT_MAX)}g Over",
                delta_color="inverse",
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
            f_dict = {f.get("food_name", "Unknown"): f for f in f_query.data}
            sel = st.selectbox("Select Item", options=list(f_dict.keys()), index=None)
            if sel:
                srv = st.number_input("Servings", 0.1, 10.0, 1.0)
                if st.button("Log Food Entry"):
                    # Fallback to ID if food_id isn't present
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
        st.markdown("### ➕ Admin: Create Food")
        if st.session_state.is_admin:
            with st.form("add_food_full"):
                fn = st.text_input("New Food Name")
                f_c1, f_c2, f_c3, f_c4, f_c5 = st.columns(5)
                v_ca = f_c1.number_input("Cals", 0)
                v_pr = f_c2.number_input("Prot", 0)
                v_ft = f_c3.number_input("Fat", 0)
                v_nc = f_c4.number_input("NetC", 0)
                v_fb = f_c5.number_input("Fib", 0)
                if st.form_submit_button("Create & Log"):
                    res = (
                        supabase.table("foods")
                        .insert(
                            {
                                "food_name": fn,
                                "calories": v_ca,
                                "protein_g": v_pr,
                                "fat_g": v_ft,
                                "net_carbs_g": v_nc,
                                "fiber_g": v_fb,
                            }
                        )
                        .execute()
                    )
                    if res.data:
                        f_id = res.data[0].get("food_id") or res.data[0].get("id")
                        supabase.table("daily_logs").insert(
                            {
                                "food_id": f_id,
                                "servings": 1.0,
                                "log_date": str(datetime.now().date()),
                                "user_id": record_owner,
                            }
                        ).execute()
                        st.rerun()

    st.divider()
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
            food_info = r.get("foods") or {}
            fname = food_info.get("food_name", "Unknown")
            fcal = food_info.get("calories", 0)
            srv = r.get("servings", 1)

            lc1.write(f"**{fname}**")
            lc2.write(f"{int(fcal * srv)} kcal")

            l_id = r.get("log_id") or r.get("id")
            if l_id and lc3.button("🗑️", key=f"del_log_{l_id}"):
                col_name = "log_id" if "log_id" in r else "id"
                supabase.table("daily_logs").delete().eq(col_name, l_id).execute()
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
                w = last_w["weight_lb"]
                s1.metric(
                    "Weight", f"{w} lbs", f"{'🟢' if w < 200 else '🔴'} (Target < 200)"
                )
                s1.caption(f"Logged: {last_w['display_time']}")
            if last_bp is not None:
                sys, dia = (
                    last_bp["blood_pressure_systolic"],
                    last_bp["blood_pressure_diastolic"],
                )
                s2.metric(
                    "BP",
                    f"{int(sys)}/{int(dia)}",
                    f"{'🟢' if sys < 130 else '🔴'} (Target < 130/85)",
                )
                s2.caption(f"Logged: {last_bp['display_time']}")
            if last_g is not None:
                g = last_g["blood_glucose"]
                g_icon = "🟢" if 80 <= g <= 130 else "🔴"
                s3.metric("Glucose", f"{int(g)} mg/dL", f"{g_icon} (Target: 80-130)")
                s3.caption(f"Logged: {last_g['display_time']}")

            st.divider()
            st.subheader("📊 Health Trends")

            def static_chart(data, col, label, color):
                base = alt.Chart(data).encode(
                    x=alt.X("ts:T", axis=alt.Axis(format="%b %d")),
                    y=alt.Y(f"{col}:Q", scale=alt.Scale(zero=False), title=label),
                )
                st.altair_chart(
                    (
                        base.mark_line(color=color) + base.mark_point(color=color)
                    ).properties(height=200),
                    use_container_width=True,
                )

            if last_w is not None:
                static_chart(
                    df.dropna(subset=["weight_lb"]),
                    "weight_lb",
                    "Weight (lbs)",
                    "#3498db",
                )
            if last_bp is not None:
                bp_df = df.dropna(
                    subset=["blood_pressure_systolic", "blood_pressure_diastolic"]
                )
                bp_chart = (
                    alt.Chart(bp_df)
                    .transform_fold(
                        ["blood_pressure_systolic", "blood_pressure_diastolic"],
                        as_=["Metric", "Value"],
                    )
                    .encode(
                        x=alt.X("ts:T", axis=alt.Axis(format="%b %d")),
                        y=alt.Y(
                            "Value:Q",
                            scale=alt.Scale(zero=False),
                            title="Blood Pressure",
                        ),
                        color="Metric:N",
                    )
                )
                st.altair_chart(
                    (bp_chart.mark_line() + bp_chart.mark_point()).properties(
                        height=200
                    ),
                    use_container_width=True,
                )
            if last_g is not None:
                static_chart(
                    df.dropna(subset=["blood_glucose"]),
                    "blood_glucose",
                    "Glucose (mg/dL)",
                    "#e74c3c",
                )

        st.divider()
        st.subheader("➕ Manual Health Entries")
        c1, c2, c3 = st.columns(3)
        now = datetime.now()
        with c1:
            with st.expander("⚖️ Weight", expanded=True):
                wv = st.number_input("Lbs", 0.0, key="man_w")
                wd, wt = (
                    st.date_input("Date", now, key="wd_w"),
                    st.time_input("Time", now, key="wt_w"),
                )
                if st.button("Save Weight"):
                    supabase.table("health_metrics").insert(
                        {
                            "date": str(wd),
                            "time": wt.strftime("%H:%M:%S"),
                            "weight_lb": wv,
                            "user_id": record_owner,
                        }
                    ).execute()
                    st.rerun()
        with c2:
            with st.expander("❤️ Blood Pressure", expanded=True):
                bs, bd = (
                    st.number_input("Sys", 0, key="man_bs"),
                    st.number_input("Dia", 0, key="man_bd"),
                )
                bpd, bpt = (
                    st.date_input("Date", now, key="wd_bp"),
                    st.time_input("Time", now, key="wt_bp"),
                )
                if st.button("Save BP"):
                    supabase.table("health_metrics").insert(
                        {
                            "date": str(bpd),
                            "time": bpt.strftime("%H:%M:%S"),
                            "blood_pressure_systolic": bs,
                            "blood_pressure_diastolic": bd,
                            "user_id": record_owner,
                        }
                    ).execute()
                    st.rerun()
        with c3:
            with st.expander("🩸 Glucose", expanded=True):
                gv = st.number_input("mg/dL", 0, key="man_g")
                gd, gt = (
                    st.date_input("Date", now, key="wd_g"),
                    st.time_input("Time", now, key="wt_g"),
                )
                if st.button("Save Glucose"):
                    supabase.table("health_metrics").insert(
                        {
                            "date": str(gd),
                            "time": gt.strftime("%H:%M:%S"),
                            "blood_glucose": gv,
                            "user_id": record_owner,
                        }
                    ).execute()
                    st.rerun()

        # RESTORED HISTORY VIEW FOR HEALTH TAB
        st.divider()
        st.subheader("📜 Recent Health Logs")
        h_res = (
            supabase.table("health_metrics")
            .select("*")
            .eq("user_id", active_user)
            .order("date", desc=True)
            .limit(5)
            .execute()
        )
        if h_res.data:
            for r in h_res.data:
                hc1, hc2, hc3 = st.columns([4, 1, 1])
                parts = []
                if r.get("weight_lb"):
                    parts.append(f"Weight: {r['weight_lb']}lbs")
                if r.get("blood_pressure_systolic"):
                    parts.append(
                        f"BP: {r['blood_pressure_systolic']}/{r['blood_pressure_diastolic']}"
                    )
                if r.get("blood_glucose"):
                    parts.append(f"Glucose: {r['blood_glucose']}mg/dL")

                hc1.write(
                    f"**{r.get('date', '')} {r.get('time', '')}**: {', '.join(parts)}"
                )

                h_id = r.get("metric_id") or r.get("id")
                if h_id and hc3.button("🗑️", key=f"del_h_{h_id}"):
                    col_name = "metric_id" if "metric_id" in r else "id"
                    supabase.table("health_metrics").delete().eq(
                        col_name, h_id
                    ).execute()
                    st.rerun()

    except Exception as e:
        st.error(f"Health Error: {e}")

# --- TAB 3: ACTIVITY ---
with tab3:
    st.subheader(f"🏃 Activity Tracking ({active_user.upper()})")
    cat = st.radio("Category", ["Strength", "Cardio", "Endurance"], horizontal=True)
    with st.form("act_log"):
        f1, f2 = st.columns(2)
        da, nm = f1.date_input("Date", datetime.now()), f2.text_input("Exercise Name")
        c1, c2, c3, c4, c5 = st.columns(5)
        s = c1.number_input("Sets", 0) if cat in ["Strength", "Endurance"] else 0
        r = c2.number_input("Reps", 0) if cat in ["Strength", "Endurance"] else 0
        w = c3.number_input("Weight", 0) if cat in ["Strength", "Endurance"] else 0
        du = c4.number_input("Mins", 0) if cat in ["Cardio", "Endurance"] else 0
        di = c5.number_input("Miles", 0.0) if cat in ["Cardio", "Endurance"] else 0
        if st.form_submit_button("Log Activity"):
            supabase.table("activity_logs").insert(
                {
                    "log_date": str(da),
                    "exercise_name": nm,
                    "activity_category": cat,
                    "sets": s,
                    "reps": r,
                    "weight_lb": w,
                    "duration_min": du,
                    "distance_miles": di,
                    "user_id": record_owner,
                }
            ).execute()
            st.rerun()

    st.divider()
    st.subheader("📜 Recent History")
    act_res = (
        supabase.table("activity_logs")
        .select("*")
        .eq("user_id", active_user)
        .order("log_date", desc=True)
        .limit(20)
        .execute()
    )
    if act_res.data:
        for r in act_res.data:
            ac1, ac2, ac3 = st.columns([4, 1, 1])
            ac1.write(
                f"**{r.get('log_date', '')}**: {r.get('exercise_name', 'Unknown')} ({r.get('activity_category', '')})"
            )

            a_id = r.get("activity_id") or r.get("id")
            if a_id and ac3.button("🗑️", key=f"del_act_{a_id}"):
                col_name = "activity_id" if "activity_id" in r else "id"
                supabase.table("activity_logs").delete().eq(col_name, a_id).execute()
                st.rerun()

# --- TAB 4: REPORTS ---
with tab4:
    st.subheader("📊 Master Table Viewer")
    tbl = st.selectbox(
        "Select Table", ["health_metrics", "activity_logs", "daily_logs", "foods"]
    )
    if tbl:
        try:
            q = supabase.table(tbl).select("*")
            if tbl != "foods":
                q = q.eq("user_id", active_user)
            sort_col = (
                "date"
                if "health" in tbl
                else "log_date"
                if "log" in tbl
                else "food_name"
            )
            res = q.order(sort_col, desc=True).limit(100).execute()
            if res.data:
                st.dataframe(pd.DataFrame(res.data), use_container_width=True)
            else:
                st.info("No data found for this table.")
        except Exception as e:
            st.error(f"Error loading table: {e}")

    # FIXED: Standalone Export block (Removed the wrapping st.button)
    st.divider()
    st.subheader("📥 Master Data Export")
    try:
        exp = (
            supabase.table("health_metrics")
            .select("*")
            .eq("user_id", active_user)
            .execute()
            .data
        )
        if exp:
            csv_data = pd.DataFrame(exp).to_csv(index=False).encode("utf-8")
            st.download_button(
                "Download Health CSV",
                data=csv_data,
                file_name=f"{active_user}_health_export.csv",
                mime="text/csv",
            )
        else:
            st.info("No records available to export.")
    except Exception as e:
        st.error(f"Export Error: {e}")
