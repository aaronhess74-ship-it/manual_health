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
st.title("💪 My Health Dashboard")

# --- TARGET CONSTANTS ---
TARGET_CALORIES = 1800
TARGET_PROTEIN = 160
TARGET_FAT_MAX = 60
TARGET_NET_CARBS = 60
TARGET_FIBER_MIN = 30
TARGET_WEIGHT = 180

# Colors for Trends
C_RED, C_YELLOW, C_GREEN, C_GRAY = "#e74c3c", "#f1c40f", "#2ecc71", "#bdc3c7"

# --- TABS SETUP ---
tab1, tab2, tab3, tab4 = st.tabs(
    ["🍴 Nutrition", "🩺 Health Metrics", "🏃 Activity", "📊 Reports & Master Export"]
)


# --- HELPER FUNCTIONS ---
def get_status_icon(curr, target, is_ceiling=True):
    if is_ceiling:
        if curr > target:
            return "🔴 OVER"
        if curr >= (target * 0.90):
            return "🟡 NEAR"
        return "🟢 OK"
    else:
        if curr >= target:
            return "🟢 GOAL"
        if curr >= (target * 0.90):
            return "🟡 LOW"
        return "🔴 URGENT"


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
            fat = float(latest.get("total_fat", 0))
            fib = float(latest.get("total_fiber", 0))

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
        st.error(f"Nutrition summary error: {e}")

    st.divider()
    st.subheader("⚡ Quick Log")
    try:
        # daily_logs uses 'log_date' and 'log_id'
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
                food = f_dict[sel]
                srv = st.number_input("Servings", min_value=0.1, value=1.0, step=0.1)
                if st.button("Log Meal Entry"):
                    supabase.table("daily_logs").insert(
                        {
                            "food_id": food["food_id"],
                            "servings": srv,
                            "log_date": str(datetime.now().date()),
                        }
                    ).execute()
                    st.rerun()

    with col_b:
        st.subheader("🆕 Create New Food")
        with st.form("new_f", clear_on_submit=True):
            n_name = st.text_input("Food Name")
            c_c, c_p, c_cb = st.columns(3)
            nc = c_c.number_input("Calories", 0)
            np = c_p.number_input("Protein", 0)
            ncb = c_cb.number_input("Carbs", 0)
            nf = st.number_input("Fat", 0)
            nfi = st.number_input("Fiber", 0)
            if st.form_submit_button("Save & Log Today"):
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

    st.divider()
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
        # health_metrics TABLE uses 'date'
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

            # --- FIX: SMART LATEST METRIC LOOKUP (Avoids NaN) ---
            def get_latest_non_null(col):
                valid = df_v.dropna(subset=[col])
                return valid.iloc[-1][col] if not valid.empty else None

            st.subheader("📊 Health Trends")
            # Weight Chart
            w_df = df_v.dropna(subset=["weight_lb"])
            if not w_df.empty:
                w_chart = (
                    alt.Chart(w_df)
                    .mark_line(point=True, color="#3498db")
                    .encode(
                        x=alt.X("ts:T", title="Timeline"),
                        y=alt.Y(
                            "weight_lb:Q",
                            title="Weight (lbs)",
                            scale=alt.Scale(zero=False),
                        ),
                        tooltip=["ts", "weight_lb"],
                    )
                    .properties(height=350)
                )
                st.altair_chart(w_chart, use_container_width=True)

            st.subheader("🩺 Latest Vitals Status")
            m1, m2, m3 = st.columns(3)

            last_glu = get_latest_non_null("blood_glucose")
            glu_icon = (
                "🟢"
                if last_glu and last_glu < 100
                else "🟡"
                if last_glu and last_glu < 126
                else "🔴"
            )
            m1.metric(
                "Latest Glucose", f"{glu_icon} {last_glu} mg/dL" if last_glu else "N/A"
            )

            last_sys = get_latest_non_null("blood_pressure_systolic")
            last_dia = get_latest_non_null("blood_pressure_diastolic")
            bp_icon = "🟢" if last_sys and last_sys < 120 else "🔴"
            m2.metric(
                "Latest BP", f"{bp_icon} {last_sys}/{last_dia}" if last_sys else "N/A"
            )

            last_w = get_latest_non_null("weight_lb")
            m3.metric("Latest Weight", f"⚖️ {last_w} lbs" if last_w else "N/A")

        st.divider()
        st.subheader("➕ New Metric Entry")
        with st.form("h_form", clear_on_submit=True):
            f1, f2, f3 = st.columns(3)
            in_w = f1.number_input("Weight (lb)", 0.0, 500.0, step=0.1)
            in_g = f2.number_input("Glucose (mg/dL)", 0, 500)
            f3.write("")  # placeholder
            s1, s2 = st.columns(2)
            in_sys = s1.number_input("Systolic BP", 0, 250)
            in_dia = s2.number_input("Diastolic BP", 0, 150)
            in_notes = st.text_area("Notes", height=70)

            if st.form_submit_button("Save Health Metrics"):
                supabase.table("health_metrics").insert(
                    {
                        "date": str(datetime.now().date()),
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "weight_lb": in_w if in_w > 0 else None,
                        "blood_glucose": in_g if in_g > 0 else None,
                        "blood_pressure_systolic": in_sys if in_sys > 0 else None,
                        "blood_pressure_diastolic": in_dia if in_dia > 0 else None,
                        "notes": in_notes,
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
                    vals = []
                    if row["weight_lb"]:
                        vals.append(f"W: {row['weight_lb']}")
                    if row["blood_glucose"]:
                        vals.append(f"G: {row['blood_glucose']}")
                    if row["blood_pressure_systolic"]:
                        vals.append(
                            f"BP: {row['blood_pressure_systolic']}/{row['blood_pressure_diastolic']}"
                        )
                    r2.write(" | ".join(vals))
                    if r3.button("🗑️", key=f"del_met_{row['metric_id']}"):
                        supabase.table("health_metrics").delete().eq(
                            "metric_id", row["metric_id"]
                        ).execute()
                        st.rerun()
    except Exception as e:
        st.error(f"Health Dashboard error: {e}")

# --- TAB 3: ACTIVITY ---
with tab3:
    st.subheader("🏃 Log Physical Activity")
    act_type = st.radio(
        "Activity Type", ["Strength", "Cardio", "Endurance"], horizontal=True
    )

    with st.form("act_form", clear_on_submit=True):
        a_date = st.date_input("Date", datetime.now().date())
        a_name = st.text_input("Exercise Name (e.g., Squats, Running)")
        c1, c2, c3 = st.columns(3)

        if act_type == "Strength":
            sets = c1.number_input("Sets", 0, 50, 3)
            reps = c2.number_input("Reps", 0, 100, 10)
            # Schema uses weight_lbs
            weight = c3.number_input("Weight (lbs)", 0, 1000, 0)
            dur, dist = 0, 0
        else:
            dur = c1.number_input("Duration (min)", 0, 500, 30)
            dist = c2.number_input("Distance (miles)", 0.0, 100.0, 0.0, step=0.1)
            sets, reps, weight = 0, 0, 0

        if st.form_submit_button("Record Activity"):
            if a_name:
                # activity_logs TABLE uses 'log_date'
                supabase.table("activity_logs").insert(
                    {
                        "log_date": str(a_date),
                        "exercise_name": a_name,
                        "activity_category": act_type,
                        "duration_min": dur,
                        "distance_miles": dist,
                        "sets": sets,
                        "reps": reps,
                        "weight_lbs": weight,
                    }
                ).execute()
                st.rerun()

    st.divider()
    st.subheader("📜 Activity History")
    try:
        # activity_logs TABLE uses 'log_date'
        a_res = (
            supabase.table("activity_logs")
            .select("*")
            .order("log_date", desc=True)
            .execute()
        )
        if a_res.data:
            df_act = pd.DataFrame(a_res.data)
            # Schema column check for display
            display_cols = [
                "log_date",
                "exercise_name",
                "activity_category",
                "sets",
                "reps",
                "weight_lbs",
                "duration_min",
                "distance_miles",
            ]
            st.dataframe(df_act[display_cols], use_container_width=True)

            with st.expander("🗑️ Delete Activity Entries"):
                for _, row in df_act.head(10).iterrows():
                    d1, d2 = st.columns([5, 1])
                    d1.write(
                        f"**{row['log_date']}**: {row['exercise_name']} ({row['activity_category']})"
                    )
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

    # Precise sort column mapping from your schema
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
            .limit(100)
            .execute()
        )
        if tbl_res.data:
            st.dataframe(pd.DataFrame(tbl_res.data), use_container_width=True)
    except Exception as e:
        st.error(f"Viewer error: {e}")

    st.divider()
    st.subheader("🚀 Master Master Export")
    st.write(
        "Consolidate all health, nutrition, and activity data into one master CSV."
    )
    if st.button("Generate Master Data File"):
        try:
            # Gather all sources
            nut_data = (
                supabase.table("daily_logs")
                .select("log_date, foods(food_name, calories)")
                .execute()
                .data
            )
            met_data = (
                supabase.table("health_metrics")
                .select(
                    "date, weight_lb, blood_glucose, blood_pressure_systolic, blood_pressure_diastolic"
                )
                .execute()
                .data
            )
            act_data = (
                supabase.table("activity_logs")
                .select("log_date, exercise_name, activity_category, duration_min")
                .execute()
                .data
            )

            master_records = []

            # Nutrition
            for n in nut_data:
                master_records.append(
                    {
                        "Date": n["log_date"],
                        "Category": "Nutrition",
                        "Metric": n["foods"]["food_name"],
                        "Value": n["foods"]["calories"],
                        "Unit": "kcal",
                    }
                )

            # Health
            for m in met_data:
                if m["weight_lb"]:
                    master_records.append(
                        {
                            "Date": m["date"],
                            "Category": "Health",
                            "Metric": "Weight",
                            "Value": m["weight_lb"],
                            "Unit": "lb",
                        }
                    )
                if m["blood_glucose"]:
                    master_records.append(
                        {
                            "Date": m["date"],
                            "Category": "Health",
                            "Metric": "Glucose",
                            "Value": m["blood_glucose"],
                            "Unit": "mg/dL",
                        }
                    )
                if m["blood_pressure_systolic"]:
                    master_records.append(
                        {
                            "Date": m["date"],
                            "Category": "Health",
                            "Metric": "BP",
                            "Value": f"{m['blood_pressure_systolic']}/{m['blood_pressure_diastolic']}",
                            "Unit": "mmHg",
                        }
                    )

            # Activity
            for a in act_data:
                master_records.append(
                    {
                        "Date": a["log_date"],
                        "Category": "Activity",
                        "Metric": a["exercise_name"],
                        "Value": a["duration_min"],
                        "Unit": "min",
                    }
                )

            if master_records:
                master_df = pd.DataFrame(master_records).sort_values(
                    "Date", ascending=False
                )
                csv_bytes = master_df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="📥 Download Master Export (CSV)",
                    data=csv_bytes,
                    file_name=f"health_master_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                )
                st.write("Preview of master data:")
                st.dataframe(master_df.head(20), use_container_width=True)
            else:
                st.warning("No data found to export.")
        except Exception as e:
            st.error(f"Master Export Error: {e}")
