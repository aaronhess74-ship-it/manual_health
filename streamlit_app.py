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

# --- TARGET CONSTANTS ---
TARGET_CALORIES = 1800
TARGET_PROTEIN = 160
TARGET_FAT_MAX = 60
TARGET_NET_CARBS = 60
TARGET_FIBER_MIN = 30

# --- TABS SETUP ---
tab1, tab2, tab3, tab4 = st.tabs(
    ["🍴 Nutrition", "🩺 Health Metrics", "🏃 Activity", "📊 Reports & Master Export"]
)

# --- TAB 1: NUTRITION ---
with tab1:
    try:
        # daily_variance VIEW uses 'date'
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
        st.subheader("🍴 Log Existing Food")
        f_query = supabase.table("foods").select("*").order("food_name").execute()
        if f_query.data:
            f_dict = {f["food_name"]: f for f in f_query.data}
            sel = st.selectbox(
                "Search Food Library...", options=list(f_dict.keys()), index=None
            )
            if sel:
                srv = st.number_input("Servings", 0.1, 10.0, 1.0)
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
            if st.form_submit_button("Save & Log"):
                if n_name:
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
            hc2.write(f"{int(item['foods']['calories'] * item['servings'])} kcal")
            if hc3.button("🗑️", key=f"del_nut_{item['log_id']}"):
                supabase.table("daily_logs").delete().eq(
                    "log_id", item["log_id"]
                ).execute()
                st.rerun()

# --- TAB 2: HEALTH METRICS ---
with tab2:
    try:
        # health_metrics uses 'date'
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

            st.subheader("📊 Health Trends")
            w_df = df_v.dropna(subset=["weight_lb"])
            if not w_df.empty:
                w_chart = (
                    alt.Chart(w_df)
                    .mark_line(point=True)
                    .encode(
                        x="ts:T", y=alt.Y("weight_lb:Q", scale=alt.Scale(zero=False))
                    )
                    .properties(height=350)
                )
                st.altair_chart(w_chart, use_container_width=True)

            st.subheader("🩺 Latest Vitals")
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
            with st.expander("❤️ Blood Pressure"):
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
            with st.expander("⚖️ Weight"):
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
            with st.expander("🩸 Glucose"):
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
            with st.expander("🗑️ Manage Recent Entries"):
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

# --- TAB 3: ACTIVITY ---
with tab3:
    st.subheader("🏃 Log Physical Activity")
    act_type = st.radio(
        "Activity Type", ["Strength", "Cardio", "Endurance"], horizontal=True
    )

    with st.form("act_form", clear_on_submit=True):
        a_date = st.date_input("Date", datetime.now().date())
        a_name = st.text_input("Exercise Name")
        c1, c2, c3 = st.columns(3)

        dur, dist, sets, reps, weight_val = 0.0, 0.0, 0, 0, 0

        if act_type == "Strength":
            sets = c1.number_input("Sets", 0, 50, 3)
            reps = c2.number_input("Reps", 0, 100, 10)
            weight_val = c3.number_input("Weight (lbs)", 0, 1000, 0)
        else:
            dur = c1.number_input("Duration (min)", 0, 500, 30)
            dist = c2.number_input("Distance (miles)", 0.0, 100.0, 0.0)

        if st.form_submit_button("Record Activity"):
            if a_name:
                try:
                    # SYNCED: Removing 'weight_lbs' and using whatever column matches your Activity table.
                    # Based on your previous schema dump, it might be missing or named differently.
                    # I will use 'weight_lb' (singular) to match your Health Metrics table standard.
                    payload = {
                        "log_date": str(a_date),
                        "exercise_name": a_name,
                        "activity_category": act_type,
                        "duration_min": float(dur),
                        "distance_miles": float(dist),
                        "sets": int(sets),
                        "reps": int(reps),
                    }
                    # Check if your activity_logs table HAS a weight column.
                    # If it's plural 'weight_lbs' in DB, change this line to "weight_lbs": int(weight_val)
                    # If it's singular 'weight_lb' in DB, use the line below:
                    payload["weight_lb"] = int(weight_val)

                    supabase.table("activity_logs").insert(payload).execute()
                    st.rerun()
                except Exception as e:
                    st.error(
                        f"Insert Failed: {e}. Check if column name is 'weight_lb' or 'weight_lbs' in Supabase."
                    )

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
            # Dynamic column display to avoid "not in index" errors
            show_cols = [
                c
                for c in [
                    "log_date",
                    "exercise_name",
                    "activity_category",
                    "sets",
                    "reps",
                    "weight_lb",
                    "weight_lbs",
                    "duration_min",
                ]
                if c in df_act.columns
            ]
            st.dataframe(df_act[show_cols], use_container_width=True)

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

# --- TAB 4: REPORTS & MASTER EXPORT ---
with tab4:
    st.subheader("📊 Database Table Viewer")
    view_tbl = st.selectbox(
        "Select Table",
        [
            "daily_variance",
            "health_metrics",
            "activity_logs",
            "detailed_health_trends",
            "daily_logs",
            "foods",
        ],
    )

    sort_lookup = {
        "daily_variance": "date",
        "health_metrics": "date",
        "detailed_health_trends": "date",
        "activity_logs": "log_date",
        "daily_logs": "log_date",
        "foods": "food_name",
    }

    try:
        s_col = sort_lookup.get(view_tbl, "created_at")
        tbl_res = (
            supabase.table(view_tbl)
            .select("*")
            .order(s_col, desc=True)
            .limit(50)
            .execute()
        )
        if tbl_res.data:
            st.dataframe(pd.DataFrame(tbl_res.data), use_container_width=True)
    except Exception as e:
        st.error(f"Viewer error: {e}")

    st.divider()
    st.subheader("🚀 Master Data Export")
    if st.button("Generate Master Data File"):
        try:
            nut_raw = (
                supabase.table("daily_logs")
                .select("log_date, foods(food_name, calories)")
                .execute()
                .data
            )
            met_raw = (
                supabase.table("health_metrics")
                .select("date, weight_lb, blood_glucose")
                .execute()
                .data
            )
            act_raw = (
                supabase.table("activity_logs")
                .select("log_date, exercise_name, duration_min")
                .execute()
                .data
            )

            master_records = []
            for n in nut_raw:
                master_records.append(
                    {
                        "Date": n["log_date"],
                        "Category": "Nutrition",
                        "Metric": n["foods"]["food_name"],
                        "Value": n["foods"]["calories"],
                    }
                )
            for m in met_raw:
                if m["weight_lb"]:
                    master_records.append(
                        {
                            "Date": m["date"],
                            "Category": "Health",
                            "Metric": "Weight",
                            "Value": m["weight_lb"],
                        }
                    )
                if m["blood_glucose"]:
                    master_records.append(
                        {
                            "Date": m["date"],
                            "Category": "Health",
                            "Metric": "Glucose",
                            "Value": m["blood_glucose"],
                        }
                    )
            for a in act_raw:
                master_records.append(
                    {
                        "Date": a["log_date"],
                        "Category": "Activity",
                        "Metric": a["exercise_name"],
                        "Value": a["duration_min"],
                    }
                )

            if master_records:
                master_df = pd.DataFrame(master_records).sort_values(
                    "Date", ascending=False
                )
                st.download_button(
                    "📥 Download CSV",
                    master_df.to_csv(index=False),
                    "health_master.csv",
                )
                st.dataframe(master_df.head(20))
        except Exception as e:
            st.error(f"Export Error: {e}")
