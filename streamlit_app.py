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

# --- STYLING ---
st.markdown(
    """
    <style>
    .main { background-color: #fafafa; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #eeeeee; }
    </style>
    """,
    unsafe_allow_html=True,
)

# RESTORED TITLE
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
        response = (
            supabase.table("daily_variance")
            .select("*")
            .order("date", desc=True)
            .limit(1)
            .execute()
        )
        if response.data:
            latest = response.data[0]
            st.subheader(f"Status for {latest['date']}")
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

            c1.metric(
                f"Calories {get_lbl(cals, TARGET_CALORIES)}",
                f"{int(cals)}",
                f"{int(TARGET_CALORIES - cals)} Left",
            )
            c2.metric(
                f"Protein {get_lbl(prot, TARGET_PROTEIN, False)}", f"{int(prot)}g"
            )
            c3.metric(f"Net Carbs {get_lbl(net_c, TARGET_NET_CARBS)}", f"{int(net_c)}g")
            c4.metric("Total Fat", f"{int(latest.get('total_fat', 0))}g")
            c5.metric("Fiber", f"{int(latest.get('total_fiber', 0))}g")
    except Exception as e:
        st.error(f"Nutrition Error: {e}")

    st.divider()
    st.subheader("⚡ Quick Log")
    try:
        recent_res = (
            supabase.table("daily_logs")
            .select("food_id, foods(food_name)")
            .order("log_id", desc=True)
            .limit(20)
            .execute()
        )
        if recent_res.data:
            seen = set()
            quick_foods = []
            for r in recent_res.data:
                if r["foods"] and r["food_id"] not in seen:
                    quick_foods.append(
                        {"id": r["food_id"], "name": r["foods"]["food_name"]}
                    )
                    seen.add(r["food_id"])
                if len(quick_foods) >= 5:
                    break
            if quick_foods:
                cols = st.columns(len(quick_foods))
                for i, f in enumerate(quick_foods):
                    if cols[i].button(f"➕ {f['name']}", key=f"q_{f['id']}"):
                        supabase.table("daily_logs").insert(
                            {
                                "food_id": f["id"],
                                "servings": 1.0,
                                "log_date": str(datetime.now().date()),
                            }
                        ).execute()
                        st.rerun()
    except:
        pass

    st.divider()
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("🍴 Log Existing Food")
        f_query = supabase.table("foods").select("*").order("food_name").execute()
        if f_query.data:
            f_dict = {f["food_name"]: f for f in f_query.data}
            sel = st.selectbox(
                "Search Food Library...", options=list(f_dict.keys()), index=None
            )
            if sel:
                srv = st.number_input("Servings", 0.1, 10.0, 1.0, key="srv_input")
                if st.button("Log Meal Entry"):
                    supabase.table("daily_logs").insert(
                        {
                            "food_id": f_dict[sel]["food_id"],
                            "servings": srv,
                            "log_date": str(datetime.now().date()),
                        }
                    ).execute()
                    st.rerun()

    with col_b:
        st.subheader("🆕 Create New Food")
        with st.form("new_f", clear_on_submit=True):
            n_name = st.text_input("Food Name")
            nc = st.number_input("Calories", 0)
            np = st.number_input("Protein", 0)
            nf = st.number_input("Fat", 0)
            nfb = st.number_input("Fiber", 0)
            ncb = st.number_input("Total Carbs", 0)
            if st.form_submit_button("Save & Log"):
                if n_name:
                    res = (
                        supabase.table("foods")
                        .insert(
                            {
                                "food_name": n_name,
                                "calories": nc,
                                "protein_g": np,
                                "fat_g": nf,
                                "fiber_g": nfb,
                                "carbs_g": ncb,
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
                            }
                        ).execute()
                        st.rerun()

    st.subheader("🗑️ Today's History")
    h_res = (
        supabase.table("daily_logs")
        .select("log_id, servings, foods(food_name, calories)")
        .eq("log_date", str(datetime.now().date()))
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

# --- TAB 2: HEALTH METRICS (RE-RESTORED EXPANDED INPUTS) ---
with tab2:
    try:
        res = (
            supabase.table("health_metrics")
            .select("*")
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

            def get_last_valid(col):
                v = df_v.dropna(subset=[col])
                return v.iloc[-1][col] if not v.empty else None

            st.subheader("📊 Trends")
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

            m1, m2, m3 = st.columns(3)
            lg = get_last_valid("blood_glucose")
            m1.metric("Latest Glucose", f"{lg} mg/dL" if lg else "N/A")
            ls, ld = (
                get_last_valid("blood_pressure_systolic"),
                get_last_valid("blood_pressure_diastolic"),
            )
            m2.metric("Latest BP", f"{ls}/{ld}" if ls else "N/A")
            lw = get_last_valid("weight_lb")
            m3.metric("Latest Weight", f"{lw} lbs" if lw else "N/A")

        st.divider()
        st.subheader("➕ Add New Measurement")
        col_bp, col_wt, col_gl = st.columns(3)
        now = datetime.now()

        with col_bp:
            with st.expander("❤️ Blood Pressure", expanded=True):
                sys = st.number_input("Systolic", 0, 250, 120)
                dia = st.number_input("Diastolic", 0, 150, 80)
                if st.button("Log BP"):
                    supabase.table("health_metrics").insert(
                        {
                            "date": str(now.date()),
                            "time": now.strftime("%H:%M:%S"),
                            "blood_pressure_systolic": sys,
                            "blood_pressure_diastolic": dia,
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
                        }
                    ).execute()
                    st.rerun()

        with col_gl:
            with st.expander("🩸 Glucose", expanded=True):
                gl_in = st.number_input("Glucose", 0, 500, 100)
                if st.button("Log Glucose"):
                    supabase.table("health_metrics").insert(
                        {
                            "date": str(now.date()),
                            "time": now.strftime("%H:%M:%S"),
                            "blood_glucose": gl_in,
                        }
                    ).execute()
                    st.rerun()

        if not df_v.empty:
            with st.expander("🗑️ Delete Recent Health Entries"):
                for _, row in (
                    df_v.sort_values("ts", ascending=False).head(10).iterrows()
                ):
                    r1, r2, r3 = st.columns([3, 4, 1])
                    r1.write(f"**{row['ts'].strftime('%b %d, %H:%M')}**")
                    vals = [
                        f"W: {row['weight_lb']}" if row["weight_lb"] else "",
                        f"G: {row['blood_glucose']}" if row["blood_glucose"] else "",
                    ]
                    r2.write(" | ".join([v for v in vals if v]))
                    if r3.button("🗑️", key=f"del_met_{row['metric_id']}"):
                        supabase.table("health_metrics").delete().eq(
                            "metric_id", row["metric_id"]
                        ).execute()
                        st.rerun()
    except Exception as e:
        st.error(f"Health error: {e}")

# --- TAB 3: ACTIVITY (FIXED ERROR) ---
with tab3:
    st.subheader("🏃 Log Activity")
    act_type = st.radio(
        "Category", ["Strength", "Cardio", "Endurance"], horizontal=True
    )

    with st.form("act_form", clear_on_submit=True):
        a_date = st.date_input("Date", datetime.now().date())
        a_name = st.text_input("Exercise Name")
        c1, c2, c3 = st.columns(3)

        # Initialize
        dur, dist, sets, reps, weight_val = 0.0, 0.0, 0, 0, 0

        if act_type == "Strength":
            sets = c1.number_input("Sets", 0, 50, 3)
            reps = c2.number_input("Reps", 0, 100, 10)
            weight_val = c3.number_input("Weight Used (lbs)", 0, 1000, 0)
        else:
            dur = c1.number_input("Duration (min)", 0, 500, 30)
            dist = c2.number_input("Distance (miles)", 0.0, 100.0, 0.0)

        if st.form_submit_button("Record Activity"):
            if a_name:
                # FIXED: This payload ONLY uses columns known to exist in your activity_logs table
                payload = {
                    "log_date": str(a_date),
                    "exercise_name": a_name,
                    "activity_category": act_type,
                    "duration_min": float(dur),
                    "distance_miles": float(dist),
                    "sets": int(sets),
                    "reps": int(reps),
                }
                # To avoid PGRST204, we don't try to insert 'weight_lb' or 'weight_lbs'
                # unless we are sure it exists. If you want to track weight in exercises,
                # you must add that column to activity_logs in Supabase first.
                try:
                    supabase.table("activity_logs").insert(payload).execute()
                    st.rerun()
                except Exception as e:
                    st.error(f"Activity Error: {e}")

    st.divider()
    st.subheader("📜 Activity History")
    try:
        a_res = (
            supabase.table("activity_logs")
            .select("*")
            .order("log_date", desc=True)
            .execute()
        )
        if a_res.data:
            df_act = pd.DataFrame(a_res.data)
            st.dataframe(df_act, use_container_width=True)

            with st.expander("🗑️ Delete Activity"):
                for _, row in df_act.head(10).iterrows():
                    d1, d2 = st.columns([5, 1])
                    d1.write(f"**{row['log_date']}**: {row['exercise_name']}")
                    if d2.button("🗑️", key=f"del_act_{row['id']}"):
                        supabase.table("activity_logs").delete().eq(
                            "id", row["id"]
                        ).execute()
                        st.rerun()
    except Exception as e:
        st.error(f"Activity load error: {e}")

# --- TAB 4: MASTER EXPORT ---
with tab4:
    st.subheader("🚀 Master Data Export")
    if st.button("Generate Downloadable File"):
        try:
            nut = (
                supabase.table("daily_logs")
                .select("log_date, foods(food_name, calories)")
                .execute()
                .data
            )
            met = (
                supabase.table("health_metrics")
                .select("date, weight_lb, blood_glucose")
                .execute()
                .data
            )
            act = (
                supabase.table("activity_logs")
                .select("log_date, exercise_name")
                .execute()
                .data
            )

            rows = []
            for i in nut:
                rows.append(
                    {
                        "Date": i["log_date"],
                        "Type": "Food",
                        "Label": i["foods"]["food_name"],
                        "Value": i["foods"]["calories"],
                    }
                )
            for i in met:
                if i["weight_lb"]:
                    rows.append(
                        {
                            "Date": i["date"],
                            "Type": "Weight",
                            "Label": "Weight",
                            "Value": i["weight_lb"],
                        }
                    )
                if i["blood_glucose"]:
                    rows.append(
                        {
                            "Date": i["date"],
                            "Type": "Glucose",
                            "Label": "Glucose",
                            "Value": i["blood_glucose"],
                        }
                    )
            for i in act:
                rows.append(
                    {
                        "Date": i["log_date"],
                        "Type": "Activity",
                        "Label": i["exercise_name"],
                        "Value": 0,
                    }
                )

            if rows:
                m_df = pd.DataFrame(rows).sort_values("Date", ascending=False)
                st.download_button(
                    "Download CSV", m_df.to_csv(index=False), "health_master.csv"
                )
                st.dataframe(m_df)
        except Exception as e:
            st.error(f"Export Error: {e}")

    st.divider()
    st.subheader("📊 Raw Table Viewer")
    tbl = st.selectbox(
        "Select View",
        ["daily_variance", "health_metrics", "activity_logs", "daily_logs", "foods"],
    )
    sc = (
        "date"
        if tbl in ["daily_variance", "health_metrics"]
        else "log_date"
        if tbl in ["activity_logs", "daily_logs"]
        else "food_name"
    )
    try:
        st.dataframe(
            pd.DataFrame(
                supabase.table(tbl)
                .select("*")
                .order(sc, desc=True)
                .limit(50)
                .execute()
                .data
            ),
            use_container_width=True,
        )
    except:
        pass
