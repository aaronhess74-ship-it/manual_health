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
TARGET_WEIGHT = 180
TARGET_GLUCOSE = 100
TARGET_BP_SYS = 130

# Colors for Trends
C_RED, C_YELLOW, C_GREEN, C_GRAY = "#e74c3c", "#f1c40f", "#2ecc71", "#bdc3c7"

tab1, tab2, tab3, tab4 = st.tabs(
    ["🍴 Nutrition", "🩺 Health Metrics", "🏃 Activity", "📊 Reports & Exports"]
)

# --- TAB 1: NUTRITION ---
with tab1:
    try:
        # daily_variance view usually maps to log_date
        response = supabase.table("daily_variance").select("*").execute()
        if response.data:
            latest = response.data[0]
            # Use log_date for display
            display_date = latest.get("log_date") or latest.get("date") or "Today"
            st.subheader(f"Status for {display_date}")
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
                else:
                    if curr >= target:
                        return "🟢 GOAL"
                    if curr >= (target * 0.90):
                        return "🟡 LOW"
                    return "🔴 URGENT"

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
            c4.metric(
                f"Total Fat {get_status_icon(fat, TARGET_FAT_MAX)}",
                f"{int(fat)}g",
                f"{int(TARGET_FAT_MAX - fat)} Left",
            )
            c5.metric(
                f"Fiber {get_status_icon(fib, TARGET_FIBER_MIN, False)}",
                f"{int(fib)}g",
                f"{int(fib - TARGET_FIBER_MIN)} vs Target",
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
                srv = st.number_input("Servings", min_value=0.0, value=1.0, step=0.1)
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

    st.subheader("📜 Today's History")
    # Query logic using log_date
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
            if hc3.button("🗑️", key=f"del_{item['log_id']}"):
                supabase.table("daily_logs").delete().eq(
                    "log_id", item["log_id"]
                ).execute()
                st.rerun()

# --- TAB 2: HEALTH METRICS ---
with tab2:
    try:
        # Changed sort to log_date
        res = (
            supabase.table("health_metrics")
            .select("*")
            .order("log_date", desc=False)
            .execute()
        )
        df_v = pd.DataFrame(res.data) if res.data else pd.DataFrame()

        if not df_v.empty:
            # Map log_date and time for charts
            df_v["ts"] = pd.to_datetime(
                df_v["log_date"].astype(str)
                + " "
                + df_v["time"].fillna("00:00:00").astype(str)
            )

            def format_label(dt):
                if dt.hour == 0 and dt.minute == 0 and dt.second == 0:
                    return dt.strftime("%b %d")
                return dt.strftime("%b %d | %H:%M")

            df_v["chart_label"] = df_v["ts"].apply(format_label)

            st.subheader("📊 Current Status")

            def get_latest(col):
                valid = df_v.dropna(subset=[col]).sort_values("ts")
                return valid.iloc[-1] if not valid.empty else None

            l_bp, l_gl, l_wt = (
                get_latest("blood_pressure_systolic"),
                get_latest("blood_glucose"),
                get_latest("weight_lb"),
            )
            m1, m2, m3 = st.columns(3)
            if l_bp is not None:
                s, d = (
                    int(l_bp["blood_pressure_systolic"]),
                    int(l_bp["blood_pressure_diastolic"]),
                )
                bp_emoji = (
                    "🟢" if s < 120 and d < 80 else "🟡" if s < 130 and d < 80 else "🔴"
                )
                m1.metric("Latest BP", f"{bp_emoji} {s}/{d}")
            if l_gl is not None:
                g = int(l_gl["blood_glucose"])
                gl_emoji = "🟢" if g < 100 else "🟡" if g < 126 else "🔴"
                m2.metric("Latest Glucose", f"{gl_emoji} {g} mg/dL")
            if l_wt is not None:
                m3.metric("Latest Weight", f"⚖️ {l_wt['weight_lb']} lbs")

            st.divider()

            def create_health_chart(data, y_col, color, y_domain, title):
                chart_df = data.dropna(subset=[y_col]).sort_values("ts")
                base = alt.Chart(chart_df).encode(
                    x=alt.X("chart_label:O", title="Entry", sort=None),
                    tooltip=[
                        alt.Tooltip("chart_label:N", title="Logged At"),
                        alt.Tooltip(f"{y_col}:Q", title=title),
                    ],
                )
                line = base.mark_line(color=color, strokeWidth=3).encode(
                    y=alt.Y(f"{y_col}:Q", scale=alt.Scale(domain=y_domain))
                )
                points = base.mark_circle(color=color, size=60).encode(y=f"{y_col}:Q")
                return (line + points).properties(height=300)

            st.write("**Weight Trend**")
            st.altair_chart(
                create_health_chart(df_v, "weight_lb", "#3498db", [150, 300], "Weight"),
                use_container_width=True,
            )

        st.subheader("➕ Log New Measurement")
        col_bp, col_wt, col_gl = st.columns(3)
        now = datetime.now()

        with col_bp:
            with st.expander("❤️ Blood Pressure"):
                d_bp = st.date_input("Date", now.date(), key="d_bp")
                t_bp = st.time_input("Time", now.time(), key="t_bp")
                sys = st.number_input("Systolic", 0, 300, 120)
                dia = st.number_input("Diastolic", 0, 200, 80)
                if st.button("Log BP"):
                    supabase.table("health_metrics").insert(
                        {
                            "log_date": d_bp.isoformat(),
                            "time": t_bp.strftime("%H:%M:%S"),
                            "blood_pressure_systolic": sys,
                            "blood_pressure_diastolic": dia,
                        }
                    ).execute()
                    st.rerun()

        with col_wt:
            with st.expander("⚖️ Weight"):
                d_wt = st.date_input("Date", now.date(), key="d_wt")
                t_wt = st.time_input("Time", now.time(), key="t_wt")
                w_wt = st.number_input("Weight (lbs)", 0.0, 500.0, 180.0)
                if st.button("Log Weight"):
                    supabase.table("health_metrics").insert(
                        {
                            "log_date": d_wt.isoformat(),
                            "time": t_wt.strftime("%H:%M:%S"),
                            "weight_lb": w_wt,
                        }
                    ).execute()
                    st.rerun()

        with col_gl:
            with st.expander("🩸 Glucose"):
                d_gl = st.date_input("Date", now.date(), key="d_gl")
                t_gl = st.time_input("Time", now.time(), key="t_gl")
                g_gl = st.number_input("Glucose", 0, 500, 100)
                if st.button("Log Glucose"):
                    supabase.table("health_metrics").insert(
                        {
                            "log_date": d_gl.isoformat(),
                            "time": t_gl.strftime("%H:%M:%S"),
                            "blood_glucose": g_gl,
                        }
                    ).execute()
                    st.rerun()

        if not df_v.empty:
            with st.expander("🗑️ Manage Recent Entries"):
                recent = df_v.sort_values("ts", ascending=False).head(10)
                for _, row in recent.iterrows():
                    c1, c2, c3 = st.columns([4, 4, 2])
                    c1.write(f"**{row['chart_label']}**")
                    c2.write(f"W: {row['weight_lb']} | G: {row['blood_glucose']}")
                    if c3.button("🗑️", key=f"del_met_{row['metric_id']}"):
                        supabase.table("health_metrics").delete().eq(
                            "metric_id", row["metric_id"]
                        ).execute()
                        st.rerun()
    except Exception as e:
        st.error(f"Health Dashboard error: {e}")

# --- TAB 3: ACTIVITY (CRITICAL FIX FOR log_date) ---
with tab3:
    st.subheader("🏃 Log Activity")
    act_cat = st.radio("Category", ["Strength", "Cardio", "Endurance"], horizontal=True)

    with st.form("act_form", clear_on_submit=True):
        a_date = st.date_input("Date", datetime.now().date())
        name = st.text_input("Exercise Name")
        c1, c2, c3 = st.columns(3)
        dur, dist, s, r, w = 0.0, 0.0, 0, 0, 0

        if act_cat == "Strength":
            s = c1.number_input("Sets", 0, 100, 3)
            r = c2.number_input("Reps", 0, 100, 10)
            w = c3.number_input("Weight (lbs)", 0, 1000, 0)
        elif act_cat == "Cardio":
            dur = c1.number_input("Duration (min)", 0.0, 500.0, 30.0)
            dist = c2.number_input("Distance (mi)", 0.0, 100.0, 0.0)
        elif act_cat == "Endurance":
            dur = c1.number_input("Duration (min)", 0.0, 500.0, 30.0)

        if st.form_submit_button("Log Activity"):
            if name:
                # Use log_date column instead of date
                supabase.table("activity_logs").insert(
                    {
                        "log_date": str(a_date),
                        "exercise_name": name,
                        "activity_category": act_cat,
                        "duration_min": dur,
                        "distance_miles": dist,
                        "sets": s,
                        "reps": r,
                        "weight_lbs": w,
                    }
                ).execute()
                st.success(f"Logged {name}!")
                st.rerun()

    st.divider()
    st.subheader("📜 Activity History")
    try:
        # FIXED: Sorting strictly by log_date
        a_res = (
            supabase.table("activity_logs")
            .select("*")
            .order("log_date", desc=True)
            .execute()
        )
        if a_res.data:
            st.dataframe(pd.DataFrame(a_res.data), use_container_width=True)
    except Exception as e:
        st.error(f"Activity History Error: {e}")

# --- TAB 4: REPORTS & EXPORTS ---
with tab4:
    st.subheader("📊 Individual Table Viewer")
    report_type = st.selectbox(
        "Select Table",
        ["Nutrition Variance", "Health Vitals", "Activity Logs"],
        key="v_sel",
    )
    t_map = {
        "Nutrition Variance": "daily_variance",
        "Health Vitals": "health_metrics",
        "Activity Logs": "activity_logs",
    }
    tbl = t_map[report_type]

    try:
        # General Viewer logic using log_date
        res = (
            supabase.table(tbl)
            .select("*")
            .order("log_date", desc=True)
            .limit(50)
            .execute()
        )
        if res.data:
            st.dataframe(pd.DataFrame(res.data), use_container_width=True)
    except:
        # Fallback for views that might only have 'date' or no sortable column
        res = supabase.table(tbl).select("*").limit(50).execute()
        st.dataframe(pd.DataFrame(res.data), use_container_width=True)

    st.divider()
    st.subheader("📂 Comprehensive Master Export")
    if st.button("🚀 Prepare Master CSV", key="master_exp_btn"):
        try:
            l_res = (
                supabase.table("daily_logs")
                .select("log_date, foods(food_name, calories)")
                .execute()
            )
            h_res = supabase.table("health_metrics").select("*").execute()
            a_res = supabase.table("activity_logs").select("*").execute()

            master = []
            for i in l_res.data:
                if i.get("foods"):
                    master.append(
                        {
                            "date": i["log_date"],
                            "type": "Nutrition",
                            "metric": i["foods"]["food_name"],
                            "value": i["foods"]["calories"],
                            "unit": "kcal",
                        }
                    )
            for i in h_res.data:
                # Use log_date for consistency
                d_val = i.get("log_date") or i.get("date")
                if i.get("weight_lb"):
                    master.append(
                        {
                            "date": d_val,
                            "type": "Health",
                            "metric": "Weight",
                            "value": i["weight_lb"],
                            "unit": "lbs",
                        }
                    )
            for i in a_res.data:
                lbl = i.get("exercise_name") or i.get("activity_category") or "Activity"
                master.append(
                    {
                        "date": i.get("log_date"),
                        "type": "Activity",
                        "metric": lbl,
                        "value": i.get("duration_min", 0),
                        "unit": "min",
                    }
                )

            if master:
                m_df = pd.DataFrame(master).sort_values(by="date", ascending=False)
                st.download_button(
                    "📥 Download Master CSV",
                    m_df.to_csv(index=False).encode("utf-8"),
                    "health_master.csv",
                    "text/csv",
                )
                st.dataframe(m_df.head(10))
            else:
                st.warning("No data found to export.")
        except Exception as e:
            st.error(f"Export failed: {e}")
