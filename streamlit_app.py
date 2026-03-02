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
NC_LOW, NC_HIGH = 50, 100  # Net Carb Green Range

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
            st.subheader(f"Daily Status: {latest['date']} ({active_user.upper()})")
            c1, c2, c3, c4, c5 = st.columns(5)
            cals, prot = (
                float(latest.get("total_calories", 0)),
                float(latest.get("total_protein", 0)),
            )
            net_c = float(latest.get("total_net_carbs", 0))
            fat, fib = (
                float(latest.get("total_fat", 0)),
                float(latest.get("total_fiber", 0)),
            )

            nc_status = "🟢" if NC_LOW <= net_c <= NC_HIGH else "🔴"

            c1.metric("Calories", f"{int(cals)}", f"{int(TARGET_CALORIES - cals)} Left")
            c2.metric(
                "Protein", f"{int(prot)}g", f"{int(prot - TARGET_PROTEIN)}g vs Goal"
            )
            c3.metric(
                f"Net Carbs {nc_status}",
                f"{int(net_c)}g",
                f"Target: {NC_LOW}-{NC_HIGH}g",
            )
            c4.metric("Fat", f"{int(fat)}g", f"Max: {TARGET_FAT_MAX}g")
            c5.metric("Fiber", f"{int(fib)}g", f"Min: {TARGET_FIBER_MIN}g")
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
        st.markdown("### ➕ Admin: Create Food")
        if st.session_state.is_admin:
            with st.form("add_food_macro"):
                fn = st.text_input("New Food Name")
                f_c1, f_c2, f_c3, f_c4 = st.columns(4)
                v_ca = f_c1.number_input("Cals", 0)
                v_pr = f_c2.number_input("Prot", 0)
                v_nc = f_c3.number_input("NetC", 0)
                v_fb = f_c4.number_input("Fib", 0)
                if st.form_submit_button("Create & Log"):
                    res = (
                        supabase.table("foods")
                        .insert(
                            {
                                "food_name": fn,
                                "calories": v_ca,
                                "protein_g": v_pr,
                                "net_carbs_g": v_nc,
                                "fiber_g": v_fb,
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
            st.info("Custom food entry is locked for Guest.")

    st.divider()
    st.subheader("🗑️ Today's Logged Items")
    log_res = (
        supabase.table("daily_logs")
        .select("log_id, servings, foods(food_name, calories)")
        .eq("log_date", str(datetime.now().date()))
        .eq("user_id", active_user)
        .execute()
    )
    if log_res.data:
        for r in log_res.data:
            lc1, lc2, lc3 = st.columns([3, 1, 1])
            lc1.write(f"**{r['foods']['food_name']}**")
            lc2.write(f"{int(r['foods']['calories'] * r['servings'])} kcal")
            if lc3.button("🗑️", key=f"del_{r['log_id']}"):
                supabase.table("daily_logs").delete().eq(
                    "log_id", r["log_id"]
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
                # Glucose Green Zone: 80 - 130
                g_icon = "🟢" if 80 <= g <= 130 else "🔴"
                s3.metric("Glucose", f"{int(g)} mg/dL", f"{g_icon} (Target: 80-130)")
                s3.caption(f"Logged: {last_g['display_time']}")

            st.divider()

            def static_chart(data, col, color):
                base = alt.Chart(data).encode(
                    x=alt.X("ts:T", axis=alt.Axis(format="%b %d")),
                    y=alt.Y(f"{col}:Q", scale=alt.Scale(zero=False)),
                )
                st.altair_chart(
                    (
                        base.mark_line(color=color) + base.mark_point(color=color)
                    ).properties(height=200),
                    use_container_width=True,
                )

            if last_w is not None:
                static_chart(df.dropna(subset=["weight_lb"]), "weight_lb", "#3498db")
            if last_g is not None:
                static_chart(
                    df.dropna(subset=["blood_glucose"]), "blood_glucose", "#e74c3c"
                )

        st.divider()
        st.subheader("➕ Manual Entry Logs")
        c1, c2, c3 = st.columns(3)
        now = datetime.now()
        with c1:
            with st.expander("⚖️ Log Weight", expanded=True):
                wv = st.number_input("Weight lbs", 0.0, key="manual_w")
                wd = st.date_input("Date", now, key="wd_w")
                wt = st.time_input("Time", now, key="wt_w")
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
            with st.expander("❤️ Log BP", expanded=True):
                bs, bd = (
                    st.number_input("Sys", 0, key="manual_bs"),
                    st.number_input("Dia", 0, key="manual_bd"),
                )
                bpd, bpt = (
                    st.date_input("Date", now, key="wd_bp"),
                    st.time_input("Time", now, key="wt_bp"),
                )
                if st.button("Save Blood Pressure"):
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
            with st.expander("🩸 Log Glucose", expanded=True):
                gv = st.number_input("mg/dL", 0, key="manual_g")
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
    except Exception as e:
        st.error(f"Error: {e}")

# --- TAB 3: ACTIVITY ---
with tab3:
    st.subheader(f"🏃 Activity Tracking ({active_user.upper()})")
    cat = st.radio("Category", ["Strength", "Cardio", "Endurance"], horizontal=True)
    with st.form("act_log"):
        f1, f2 = st.columns(2)
        da, nm = f1.date_input("Date", datetime.now()), f2.text_input("Exercise Name")
        c1, c2, c3, c4, c5 = st.columns(5)
        # Endurance unlocks all inputs
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
        .limit(10)
        .execute()
    )
    if act_res.data:
        st.dataframe(pd.DataFrame(act_res.data), use_container_width=True)

# --- TAB 4: REPORTS ---
with tab4:
    st.subheader("📊 Master Table Access")
    tbl = st.selectbox(
        "View Data From", ["health_metrics", "activity_logs", "daily_logs", "foods"]
    )
    if tbl:
        q = supabase.table(tbl).select("*")
        if tbl != "foods":
            q = q.eq("user_id", active_user)
        sort = (
            "date" if "health" in tbl else "log_date" if "log" in tbl else "food_name"
        )
        res = q.order(sort, desc=True).limit(50).execute()
        if res.data:
            st.dataframe(pd.DataFrame(res.data), use_container_width=True)
