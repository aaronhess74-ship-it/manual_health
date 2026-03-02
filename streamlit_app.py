import streamlit as st
from supabase import create_client
from datetime import datetime
import pandas as pd
import altair as alt

# 1. Setup Connection
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.set_page_config(page_title="Health Dashboard Pro", layout="wide")
st.title("💪 My Health Dashboard")

# --- TARGET CONSTANTS ---
TARGET_CALORIES = 1800
TARGET_PROTEIN = 160
TARGET_FAT_MAX = 60
TARGET_NET_CARBS = 60
TARGET_FIBER_MIN = 30

# Colors for Trends
C_RED, C_YELLOW, C_GREEN = "#e74c3c", "#f1c40f", "#2ecc71"

tab1, tab2, tab3, tab4 = st.tabs(
    ["🍴 Nutrition", "🩺 Health Metrics", "🏃 Activity", "📊 Reports & Master Export"]
)

# --- TAB 1: NUTRITION ---
with tab1:
    try:
        # daily_variance (VIEW) uses 'date'
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

            cals = float(latest.get("total_calories", 0))
            prot = float(latest.get("total_protein", 0))
            net_c = float(latest.get("total_net_carbs", 0))
            fat = float(latest.get("total_fat", 0))
            fib = float(latest.get("total_fiber", 0))

            def get_status_icon(curr, target, is_ceiling=True):
                if is_ceiling:
                    if curr > target:
                        return "🔴 OVER"
                    if curr >= (target * 0.90):
                        return "🟡 NEAR"
                    return "🟢 OK"
                return "🟢 GOAL" if curr >= target else "🔴 LOW"

            c1.metric(
                f"Calories {get_status_icon(cals, TARGET_CALORIES)}",
                f"{int(cals)}",
                f"{int(TARGET_CALORIES - cals)} Left",
            )
            c2.metric(
                f"Protein {get_status_icon(prot, TARGET_PROTEIN, False)}",
                f"{int(prot)}g",
                f"{int(prot - TARGET_PROTEIN)} vs Target",
            )
            c3.metric(
                f"Net Carbs {get_status_icon(net_c, TARGET_NET_CARBS)}",
                f"{int(net_c)}g",
                f"{int(TARGET_NET_CARBS - net_c)} Left",
            )
            c4.metric("Total Fat", f"{int(fat)}g", f"{int(TARGET_FAT_MAX - fat)} Left")
            c5.metric(
                "Fiber", f"{int(fib)}g", f"{int(fib - TARGET_FIBER_MIN)} vs Target"
            )
    except Exception as e:
        st.error(f"Daily summary error: {e}")

    st.divider()
    st.subheader("⚡ Quick Log")
    try:
        recent_res = (
            supabase.table("daily_logs")
            .select("food_id, foods(food_name)")
            .order("log_id", desc=True)
            .limit(30)
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
        st.subheader("🍴 Log Existing")
        f_query = supabase.table("foods").select("*").order("food_name").execute()
        if f_query.data:
            f_dict = {f["food_name"]: f for f in f_query.data}
            sel = st.selectbox(
                "Search Food Library...", options=list(f_dict.keys()), index=None
            )
            if sel:
                food = f_dict[sel]
                srv = st.number_input("Servings", min_value=0.1, value=1.0, step=0.1)
                if st.button("Log Meal"):
                    supabase.table("daily_logs").insert(
                        {
                            "food_id": food["food_id"],
                            "servings": srv,
                            "log_date": str(datetime.now().date()),
                        }
                    ).execute()
                    st.rerun()

    with col_b:
        st.subheader("🆕 New Food")
        with st.form("new_f", clear_on_submit=True):
            n_name = st.text_input("Name")
            c_c, c_p, c_cb = st.columns(3)
            nc, np, ncb = (
                c_c.number_input("Cal", 0),
                c_p.number_input("Prot", 0),
                c_cb.number_input("Carb", 0),
            )
            nf, nfi = st.number_input("Fat", 0), st.number_input("Fib", 0)
            if st.form_submit_button("Save & Log"):
                if n_name:
                    res = (
                        supabase.table("foods")
                        .insert(
                            {
                                "food_name": n_name,
                                "calories": nc,
                                "protein_g": np,
                                "carbs_g": ncb,
                                "fat_g": nf,
                                "fiber_g": nfi,
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

    st.subheader("🗑️ Today's Log History")
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
            hc2.write(f"{int(item['foods']['calories'] * item['servings'])} cal")
            if hc3.button("🗑️", key=f"del_nut_{item['log_id']}"):
                supabase.table("daily_logs").delete().eq(
                    "log_id", item["log_id"]
                ).execute()
                st.rerun()

# --- TAB 2: HEALTH METRICS ---
with tab2:
    try:
        # health_metrics (TABLE) uses 'date'
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

            st.subheader("📊 Trends")
            # Weight Chart
            w_chart = (
                alt.Chart(df_v.dropna(subset=["weight_lb"]))
                .mark_line(point=True, color="#3498db")
                .encode(
                    x=alt.X("ts:T", title="Date/Time"),
                    y=alt.Y(
                        "weight_lb:Q", title="Weight (lbs)", scale=alt.Scale(zero=False)
                    ),
                    tooltip=["ts", "weight_lb"],
                )
                .properties(height=300)
            )
            st.altair_chart(w_chart, use_container_width=True)

            # Latest Status with Color Coding
            st.subheader("🩺 Latest Vitals")
            m1, m2, m3 = st.columns(3)

            latest_row = df_v.iloc[-1]
            # Glucose check
            glu = latest_row.get("blood_glucose")
            glu_color = (
                "🟢" if glu and glu < 100 else "🟡" if glu and glu < 125 else "🔴"
            )
            m1.metric("Latest Glucose", f"{glu_color} {glu} mg/dL" if glu else "N/A")

            # BP Check
            sys = latest_row.get("blood_pressure_systolic")
            dia = latest_row.get("blood_pressure_diastolic")
            bp_status = "🟢" if sys and sys < 120 else "🔴"
            m2.metric("Latest BP", f"{bp_status} {sys}/{dia}" if sys else "N/A")

            m3.metric("Latest Weight", f"⚖️ {latest_row.get('weight_lb')} lbs")

        st.divider()
        st.subheader("➕ New Entry")
        with st.form("h_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            new_w = c1.number_input("Weight (lb)", 0.0, 500.0, step=0.1)
            new_g = c2.number_input("Glucose (mg/dL)", 0, 500)
            c3.write("")  # Spacer
            cs1, cs2 = st.columns(2)
            new_sys = cs1.number_input("Systolic", 0, 250)
            new_dia = cs2.number_input("Diastolic", 0, 150)
            if st.form_submit_button("Save Vitals"):
                supabase.table("health_metrics").insert(
                    {
                        "date": str(datetime.now().date()),
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "weight_lb": new_w if new_w > 0 else None,
                        "blood_glucose": new_g if new_g > 0 else None,
                        "blood_pressure_systolic": new_sys if new_sys > 0 else None,
                        "blood_pressure_diastolic": new_dia if new_dia > 0 else None,
                    }
                ).execute()
                st.rerun()

        if not df_v.empty:
            with st.expander("🗑️ Manage Recent Entries"):
                for _, row in (
                    df_v.sort_values("ts", ascending=False).head(5).iterrows()
                ):
                    col1, col2, col3 = st.columns([3, 3, 1])
                    col1.write(f"**{row['ts'].strftime('%b %d, %H:%M')}**")
                    col2.write(f"W: {row['weight_lb']} | G: {row['blood_glucose']}")
                    if col3.button("🗑️", key=f"del_met_{row['metric_id']}"):
                        supabase.table("health_metrics").delete().eq(
                            "metric_id", row["metric_id"]
                        ).execute()
                        st.rerun()
    except Exception as e:
        st.error(f"Health Metrics Tab Error: {e}")

# --- TAB 3: ACTIVITY ---
with tab3:
    st.subheader("🏃 Activity Log")
    # RADIO BUTTONS restored
    act_cat = st.radio("Category", ["Strength", "Cardio", "Endurance"], horizontal=True)

    with st.form("act_form", clear_on_submit=True):
        a_date = st.date_input("Date", datetime.now().date())
        name = st.text_input("Exercise Name (e.g. Bench Press, Run)")
        c1, c2, c3 = st.columns(3)

        if act_cat == "Strength":
            sets = c1.number_input("Sets", 0, 50, 3)
            reps = c2.number_input("Reps", 0, 100, 10)
            weight = c3.number_input("Weight (lbs)", 0, 1000, 0)
            dur, dist = 0, 0
        else:
            dur = c1.number_input("Duration (min)", 0, 500, 30)
            dist = c2.number_input("Distance (miles)", 0.0, 100.0, 0.0, step=0.1)
            sets, reps, weight = 0, 0, 0

        if st.form_submit_button("Log Activity"):
            if name:
                # activity_logs (TABLE) uses 'log_date'
                supabase.table("activity_logs").insert(
                    {
                        "log_date": str(a_date),
                        "exercise_name": name,
                        "activity_category": act_cat,
                        "duration_min": dur,
                        "distance_miles": dist,
                        "sets": sets,
                        "reps": reps,
                        "weight_lbs": weight,
                    }
                ).execute()
                st.rerun()

    st.divider()
    st.subheader("📜 History")
    try:
        # activity_logs (TABLE) uses 'log_date'
        a_res = (
            supabase.table("activity_logs")
            .select("*")
            .order("log_date", desc=True)
            .execute()
        )
        if a_res.data:
            df_act = pd.DataFrame(a_res.data)
            # Display formatted table
            st.dataframe(
                df_act[
                    [
                        "log_date",
                        "exercise_name",
                        "activity_category",
                        "sets",
                        "reps",
                        "weight_lbs",
                        "duration_min",
                    ]
                ],
                use_container_width=True,
            )

            # Deletion logic for activity
            with st.expander("🗑️ Delete Activities"):
                for _, row in df_act.head(5).iterrows():
                    dcol1, dcol2 = st.columns([5, 1])
                    dcol1.write(f"{row['log_date']} - {row['exercise_name']}")
                    if dcol2.button("🗑️", key=f"del_act_{row['id']}"):
                        supabase.table("activity_logs").delete().eq(
                            "id", row["id"]
                        ).execute()
                        st.rerun()
    except Exception as e:
        st.error(f"Activity load error: {e}")

# --- TAB 4: MASTER EXPORT & REPORTS ---
with tab4:
    st.subheader("📂 Master Data Export")
    if st.button("🚀 Generate Master CSV"):
        try:
            # Consolidate all data
            l_data = (
                supabase.table("daily_logs")
                .select("log_date, foods(food_name, calories)")
                .execute()
                .data
            )
            h_data = (
                supabase.table("health_metrics")
                .select("date, weight_lb, blood_glucose")
                .execute()
                .data
            )
            a_data = (
                supabase.table("activity_logs")
                .select("log_date, exercise_name, duration_min")
                .execute()
                .data
            )

            master_list = []
            for i in l_data:
                master_list.append(
                    {
                        "Date": i["log_date"],
                        "Type": "Nutrition",
                        "Metric": i["foods"]["food_name"],
                        "Value": i["foods"]["calories"],
                    }
                )
            for i in h_data:
                if i["weight_lb"]:
                    master_list.append(
                        {
                            "Date": i["date"],
                            "Type": "Health",
                            "Metric": "Weight",
                            "Value": i["weight_lb"],
                        }
                    )
                if i["blood_glucose"]:
                    master_list.append(
                        {
                            "Date": i["date"],
                            "Type": "Health",
                            "Metric": "Glucose",
                            "Value": i["blood_glucose"],
                        }
                    )
            for i in a_data:
                master_list.append(
                    {
                        "Date": i["log_date"],
                        "Type": "Activity",
                        "Metric": i["exercise_name"],
                        "Value": i["duration_min"],
                    }
                )

            if master_list:
                m_df = pd.DataFrame(master_list).sort_values("Date", ascending=False)
                st.download_button(
                    "📥 Download Master CSV",
                    m_df.to_csv(index=False).encode("utf-8"),
                    "health_master_export.csv",
                    "text/csv",
                )
                st.dataframe(m_df)
        except Exception as e:
            st.error(f"Export Error: {e}")

    st.divider()
    st.subheader("📊 Table Viewer")
    tbl = st.selectbox(
        "Select View",
        ["daily_variance", "health_metrics", "activity_logs", "detailed_health_trends"],
    )
    # Determine correct sort column based on your schema
    sort_col = (
        "date"
        if tbl in ["daily_variance", "health_metrics", "detailed_health_trends"]
        else "log_date"
    )

    try:
        res_tbl = (
            supabase.table(tbl)
            .select("*")
            .order(sort_col, desc=True)
            .limit(50)
            .execute()
        )
        if res_tbl.data:
            st.dataframe(pd.DataFrame(res_tbl.data), use_container_width=True)
    except Exception as e:
        st.error(f"Viewer Error: {e}")
