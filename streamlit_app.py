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
    st.sidebar.success("Logged in as Guest: Data isolation active.")

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
            st.warning("Only Admin can add new items to global library.")

    st.subheader(f"🗑️ {active_user.title()} Today's Entries")
    h_res = (
        supabase.table("daily_logs")
        .select("log_id, servings, foods(food_name, calories)")
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
            # Create a combined label for the X-axis: "Oct 24 14:30"
            # We use this as an Ordinal string so the chart only shows points with data
            df_v["ts"] = pd.to_datetime(
                df_v["date"].astype(str)
                + " "
                + df_v["time"].fillna("00:00:00").astype(str)
            )
            df_v["log_time"] = df_v["ts"].dt.strftime("%b %d %H:%M")
            df_v["tooltip_time"] = df_v["ts"].dt.strftime("%b %d, %I:%M %p")

            st.subheader(f"📊 {active_user.title()} Health Trends")

            # 1. WEIGHT TREND
            w_df = df_v.dropna(subset=["weight_lb"])
            if not w_df.empty:
                w_chart = (
                    alt.Chart(w_df)
                    .mark_line(point=True, color="#3498db")
                    .encode(
                        # Changing :T to :O (Ordinal) removes the empty day gaps
                        x=alt.X(
                            "log_time:O",
                            title="Log Entries (Sorted)",
                            axis=alt.Axis(labelAngle=-45),
                        ),
                        y=alt.Y(
                            "weight_lb:Q",
                            scale=alt.Scale(domain=[100, 300]),
                            title="Lbs",
                        ),
                        tooltip=[
                            alt.Tooltip("tooltip_time:N", title="Exact Time"),
                            alt.Tooltip("weight_lb:Q"),
                        ],
                    )
                    .properties(height=250)
                )
                st.altair_chart(w_chart, use_container_width=True)

            # 2. BP TREND
            bp_df = df_v.dropna(
                subset=["blood_pressure_systolic", "blood_pressure_diastolic"]
            )
            if not bp_df.empty:
                bp_melted = bp_df.melt(
                    id_vars=["log_time", "tooltip_time"],
                    value_vars=["blood_pressure_systolic", "blood_pressure_diastolic"],
                )
                bp_chart = (
                    alt.Chart(bp_melted)
                    .mark_line(point=True)
                    .encode(
                        x=alt.X(
                            "log_time:O",
                            title="Log Entries",
                            axis=alt.Axis(labelAngle=-45),
                        ),
                        y=alt.Y(
                            "value:Q", scale=alt.Scale(domain=[40, 200]), title="mmHg"
                        ),
                        color="variable:N",
                        tooltip=[
                            alt.Tooltip("tooltip_time:N", title="Exact Time"),
                            alt.Tooltip("value:Q"),
                        ],
                    )
                    .properties(height=250)
                )
                st.altair_chart(bp_chart, use_container_width=True)

            # 3. GLUCOSE TREND
            g_df = df_v.dropna(subset=["blood_glucose"])
            if not g_df.empty:
                g_chart = (
                    alt.Chart(g_df)
                    .mark_line(point=True, color="#e74c3c")
                    .encode(
                        x=alt.X(
                            "log_time:O",
                            title="Log Entries",
                            axis=alt.Axis(labelAngle=-45),
                        ),
                        y=alt.Y(
                            "blood_glucose:Q",
                            scale=alt.Scale(domain=[50, 250]),
                            title="mg/dL",
                        ),
                        tooltip=[
                            alt.Tooltip("tooltip_time:N", title="Exact Time"),
                            alt.Tooltip("blood_glucose:Q"),
                        ],
                    )
                    .properties(height=250)
                )
                st.altair_chart(g_chart, use_container_width=True)

        st.divider()
        # ... (Metrics logging logic remains same)
    except Exception as e:
        st.error(f"Health Error: {e}")

# --- TAB 3: ACTIVITY ---
with tab3:
    st.subheader(f"🏃 Log {active_user.title()} Activity")
    act_type = st.radio("Type", ["Strength", "Cardio", "Endurance"], horizontal=True)
    with st.form("act_form", clear_on_submit=True):
        a_date, a_name = st.date_input("Date"), st.text_input("Exercise Name")
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
