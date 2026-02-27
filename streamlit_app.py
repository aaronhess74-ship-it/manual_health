import streamlit as st
from supabase import create_client
from datetime import datetime
import pandas as pd

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
        response = supabase.table("daily_variance").select("*").execute()
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
import altair as alt
from datetime import datetime

with tab2:
    # --- 1. DATA FETCHING ---
    try:
        res = (
            supabase.table("health_metrics")
            .select("*")
            .order("date", desc=False)
            .execute()
        )
        df_v = pd.DataFrame(res.data) if res.data else pd.DataFrame()

        if not df_v.empty:
            # Crucial: Keep 'ts' as a datetime object for the charts
            df_v["ts"] = pd.to_datetime(df_v["date"])

            # --- 2. LATEST METRICS (UNCHANGED) ---
            st.subheader("📊 Current Status")

            def get_latest(col):
                valid = df_v.dropna(subset=[col])
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
                m1.metric(
                    "Latest BP",
                    f"{'🟢' if s < 120 else '🟡' if s < 130 else '🔴'} {s}/{d}",
                )
            if l_gl is not None:
                g = int(l_gl["blood_glucose"])
                m2.metric(
                    "Latest Glucose",
                    f"{'🟢' if g < 100 else '🟡' if g < 126 else '🔴'} {g} mg/dL",
                )
            if l_wt is not None:
                m3.metric("Latest Weight", f"⚖️ {l_wt['weight_lb']} lbs")

            st.divider()

        # --- 3. LOG NEW MEASUREMENT (UNCHANGED) ---
        st.subheader("➕ Log New Measurement")
        col_bp, col_wt, col_gl = st.columns(3)
        now = datetime.now()

        with col_bp:
            with st.expander("❤️ Blood Pressure", expanded=False):
                d = st.date_input("BP Date", now.date(), key="nbpd")
                t = st.time_input("BP Time", now.time(), key="nbpt")
                sys = st.number_input("Systolic", 0, 300, 120)
                dia = st.number_input("Diastolic", 0, 200, 80)
                if st.button("Log BP", key="l_bp"):
                    supabase.table("health_metrics").insert(
                        {
                            "date": datetime.combine(d, t).isoformat(),
                            "blood_pressure_systolic": sys,
                            "blood_pressure_diastolic": dia,
                        }
                    ).execute()
                    st.rerun()

        with col_wt:
            with st.expander("⚖️ Weight", expanded=False):
                d = st.date_input("Wt Date", now.date(), key="nwtd")
                t = st.time_input("Wt Time", now.time(), key="nwtt")
                w = st.number_input("Weight", 0.0, 500.0, 180.0)
                if st.button("Log Weight", key="l_wt"):
                    supabase.table("health_metrics").insert(
                        {"date": datetime.combine(d, t).isoformat(), "weight_lb": w}
                    ).execute()
                    st.rerun()

        with col_gl:
            with st.expander("🩸 Glucose", expanded=False):
                d = st.date_input("Gl Date", now.date(), key="ngld")
                t = st.time_input("Gl Time", now.time(), key="nglt")
                g = st.number_input("Glucose", 0, 500, 100)
                if st.button("Log Glucose", key="l_gl"):
                    supabase.table("health_metrics").insert(
                        {"date": datetime.combine(d, t).isoformat(), "blood_glucose": g}
                    ).execute()
                    st.rerun()

        if not df_v.empty:
            st.divider()

            # --- 4. THE CORRECTED CHARTS ---
            # Using :T (Temporal) instead of :N (Nominal) so lines connect.
            # axis=alt.Axis(format='%b %d %H:%M') ensures the time shows up.

            # Weight Chart
            st.write("**Weight Trend (150 - 300 lbs)**")
            wt_df = df_v.dropna(subset=["weight_lb"])
            wt_base = alt.Chart(wt_df).encode(
                x=alt.X(
                    "ts:T",
                    title="Log Time",
                    axis=alt.Axis(format="%b %d %H:%M", labelAngle=-45),
                ),
                tooltip=[
                    alt.Tooltip("ts:T", format="%b %d %H:%M", title="Time"),
                    "weight_lb",
                ],
            )
            wt_line = wt_base.mark_line(color="#3498db").encode(
                y=alt.Y("weight_lb:Q", scale=alt.Scale(domain=[150, 300]))
            )
            wt_text = wt_base.mark_text(dy=-15, color="white").encode(
                y="weight_lb:Q", text=alt.Text("weight_lb:Q", format=".1f")
            )
            st.altair_chart(
                (wt_line + wt_base.mark_circle(color="#3498db") + wt_text).properties(
                    height=300
                ),
                use_container_width=True,
            )

            # Glucose Chart
            st.write("**Glucose Trend (0 - 200 mg/dL)**")
            gl_df = df_v.dropna(subset=["blood_glucose"])
            gl_base = alt.Chart(gl_df).encode(
                x=alt.X(
                    "ts:T",
                    title="Log Time",
                    axis=alt.Axis(format="%b %d %H:%M", labelAngle=-45),
                ),
                tooltip=[
                    alt.Tooltip("ts:T", format="%b %d %H:%M", title="Time"),
                    "blood_glucose",
                ],
            )
            gl_line = gl_base.mark_line(color="#f1c40f").encode(
                y=alt.Y("blood_glucose:Q", scale=alt.Scale(domain=[0, 200]))
            )
            gl_text = gl_base.mark_text(dy=-15, color="white").encode(
                y="blood_glucose:Q", text="blood_glucose:Q"
            )
            st.altair_chart(
                (gl_line + gl_base.mark_circle(color="#f1c40f") + gl_text).properties(
                    height=300
                ),
                use_container_width=True,
            )

            # BP Chart
            st.write("**Blood Pressure Range (0 - 250 mmHg)**")
            bp_df = df_v.dropna(subset=["blood_pressure_systolic"])
            bp_base = alt.Chart(bp_df).encode(
                x=alt.X(
                    "ts:T",
                    title="Log Time",
                    axis=alt.Axis(format="%b %d %H:%M", labelAngle=-45),
                ),
                tooltip=[
                    alt.Tooltip("ts:T", format="%b %d %H:%M", title="Time"),
                    "blood_pressure_systolic",
                    "blood_pressure_diastolic",
                ],
            )
            bp_range = bp_base.mark_bar(width=8, color="#e74c3c", opacity=0.6).encode(
                y=alt.Y("blood_pressure_diastolic:Q", scale=alt.Scale(domain=[0, 250])),
                y2="blood_pressure_systolic:Q",
            )
            bp_text_s = bp_base.mark_text(
                dy=-10, color="#e74c3c", fontWeight="bold"
            ).encode(y="blood_pressure_systolic:Q", text="blood_pressure_systolic:Q")
            bp_text_d = bp_base.mark_text(dy=15, color="#95a5a6").encode(
                y="blood_pressure_diastolic:Q", text="blood_pressure_diastolic:Q"
            )
            st.altair_chart(
                (bp_range + bp_text_s + bp_text_d).properties(height=300),
                use_container_width=True,
            )

            # --- 5. MANAGE ENTRIES (UNCHANGED) ---
            with st.expander("🗑️ Manage & Edit Recent Entries"):
                if "editing_id" not in st.session_state:
                    st.session_state.editing_id = None
                recent = df_v.sort_values("date", ascending=False).head(10)
                for _, row in recent.iterrows():
                    m_id = row["metric_id"]
                    if st.session_state.editing_id == m_id:
                        with st.container(border=True):
                            c1, c2, c3 = st.columns(3)
                            e_date = c1.date_input(
                                "Date", row["ts"].date(), key=f"d{m_id}"
                            )
                            e_time = c2.time_input(
                                "Time", row["ts"].time(), key=f"t{m_id}"
                            )
                            e_notes = c3.text_input(
                                "Notes",
                                row["notes"] if row["notes"] else "",
                                key=f"n{m_id}",
                            )
                            v1, v2, _ = st.columns(3)
                            e_w = v1.number_input(
                                "Weight",
                                value=float(row["weight_lb"])
                                if not pd.isna(row["weight_lb"])
                                else 0.0,
                                key=f"w{m_id}",
                            )
                            e_g = v2.number_input(
                                "Glucose",
                                value=int(row["blood_glucose"])
                                if not pd.isna(row["blood_glucose"])
                                else 0,
                                key=f"g{m_id}",
                            )
                            if st.button("Save", key=f"s{m_id}"):
                                up = {
                                    "date": datetime.combine(
                                        e_date, e_time
                                    ).isoformat(),
                                    "notes": e_notes,
                                }
                                if not pd.isna(row["weight_lb"]):
                                    up["weight_lb"] = e_w
                                if not pd.isna(row["blood_glucose"]):
                                    up["blood_glucose"] = e_g
                                supabase.table("health_metrics").update(up).eq(
                                    "metric_id", m_id
                                ).execute()
                                st.session_state.editing_id = None
                                st.rerun()
                            if st.button("Cancel", key=f"c{m_id}"):
                                st.session_state.editing_id = None
                                st.rerun()
                    else:
                        c1, c2, c3 = st.columns([3, 5, 2])
                        c1.write(f"**{row['ts'].strftime('%b %d %H:%M')}**")
                        vals = []
                        if not pd.isna(row["weight_lb"]):
                            vals.append(f"{row['weight_lb']} lbs")
                        if not pd.isna(row["blood_glucose"]):
                            vals.append(f"Glu: {row['blood_glucose']}")
                        if not pd.isna(row["blood_pressure_systolic"]):
                            vals.append(
                                f"BP: {int(row['blood_pressure_systolic'])}/{int(row['blood_pressure_diastolic'])}"
                            )
                        c2.write(" | ".join(vals))
                        if c3.button("✏️", key=f"eb{m_id}"):
                            st.session_state.editing_id = m_id
                            st.rerun()
                        if c3.button("🗑️", key=f"db{m_id}"):
                            supabase.table("health_metrics").delete().eq(
                                "metric_id", m_id
                            ).execute()
                            st.rerun()

    except Exception as e:
        st.error(f"Error: {e}")

# --- TAB 3: ACTIVITY (UI SWAP FIX) ---
with tab3:
    st.subheader("🏃 Log Activity")

    # 1. Radio moves OUTSIDE the form to trigger the UI refresh
    act_type = st.radio(
        "Select Activity Type",
        ["Strength", "Cardio", "Endurance"],
        horizontal=True,
        key="activity_selector",
    )

    # 2. The Form begins AFTER the radio button
    with st.form("act_form", clear_on_submit=True):
        a_date = st.date_input("Date", datetime.now().date())
        name = st.text_input("Exercise Name")

        c1, c2, c3 = st.columns(3)

        # Initialize defaults
        dur, dist, sets, reps, weight_ex = 0.0, 0.0, 0, 0, 0

        # UI now swaps instantly when you click the radio buttons above
        if act_type == "Strength":
            sets = c1.number_input("Sets", min_value=0, value=3)
            reps = c2.number_input("Reps", min_value=0, value=10)
            weight_ex = c3.number_input("Weight (lbs)", min_value=0, value=0)

        elif act_type == "Cardio":
            dur = c1.number_input("Duration (mins)", min_value=0.0, value=30.0)
            dist = c2.number_input("Distance (miles)", min_value=0.0, value=0.0)

        elif act_type == "Endurance":
            dur = c1.number_input("Duration (mins)", min_value=0.0, value=30.0)
            sets = c2.number_input("Sets", min_value=0, value=0)
            reps = c3.number_input("Reps", min_value=0, value=0)

        if st.form_submit_button("Log Activity"):
            if name:
                supabase.table("activity_logs").insert(
                    {
                        "date": str(a_date),
                        "exercise_name": name,
                        "activity_type": act_type,
                        "duration_min": dur,
                        "distance_miles": dist,
                        "sets": sets,
                        "reps": reps,
                        "weight_lbs": weight_ex,
                    }
                ).execute()
                st.rerun()
            else:
                st.warning("Please enter an exercise name.")

    st.divider()
    # (Rest of history table logic follows below...)
    try:
        a_res = (
            supabase.table("activity_logs")
            .select("*")
            .order("date", desc=False)
            .execute()
        )
        if a_res.data:
            df_a = pd.DataFrame(a_res.data)
            st.subheader("📜 Activity History")
            st.dataframe(
                df_a.sort_values(by="date", ascending=False),
                use_container_width=True,
                column_order=[
                    "date",
                    "exercise_name",
                    "activity_type",
                    "sets",
                    "reps",
                    "weight_lbs",
                    "duration_min",
                    "distance_miles",
                ],
            )
    except:
        pass

# --- TAB 4: REPORTS & EXPORTS (FULL RESTORED) ---
with tab4:
    st.subheader("📥 Universal Food Importer")
    import_type = st.selectbox(
        "Format", ["Daily Food & Nutrition (Kaggle)", "USDA FoodData Central"]
    )
    uploaded_file = st.file_uploader("Upload CSV", type="csv")

    if uploaded_file:
        try:
            df_raw = pd.read_csv(uploaded_file, on_bad_lines="skip", engine="python")
            mapping = (
                {
                    "Food_Item": "food_name",
                    "Calories (kcal)": "calories",
                    "Protein (g)": "protein_g",
                    "Carbohydrates (g)": "carbs_g",
                    "Fat (g)": "fat_g",
                    "Fiber (g)": "fiber_g",
                }
                if "Kaggle" in import_type
                else {
                    "description": "food_name",
                    "Energy": "calories",
                    "Protein": "protein_g",
                    "Carbohydrate, by difference": "carbs_g",
                    "Total lipid (fat)": "fat_g",
                    "Fiber, total dietary": "fiber_g",
                }
            )
            df_mapped = df_raw[
                [c for c in mapping.keys() if c in df_raw.columns]
            ].rename(columns=mapping)
            for col in ["calories", "protein_g", "carbs_g", "fat_g", "fiber_g"]:
                if col not in df_mapped.columns:
                    df_mapped[col] = 0.0

            if st.button("🚀 Confirm Upsert Import"):
                supabase.table("foods").upsert(
                    df_mapped.to_dict(orient="records"), on_conflict="food_name"
                ).execute()
                st.success("Import Successful!")
        except Exception as e:
            st.error(f"Error: {e}")

    st.divider()
    st.subheader("📊 Goal Performance")
    try:
        perf_res = supabase.table("daily_variance").select("*").execute()
        if perf_res.data:
            df_perf = pd.DataFrame(perf_res.data)
            win_rate = (
                len(df_perf[df_perf["total_calories"] <= TARGET_CALORIES])
                / len(df_perf)
            ) * 100
            st.info(f"🏆 Calorie Goal Win Rate: **{win_rate:.1f}%**")
    except:
        pass

    st.divider()
    st.subheader("📂 Master Data Export")
    report_type = st.selectbox(
        "View Table", ["Nutrition Variance", "Health Vitals", "Activity Logs"]
    )
    tbl = (
        "daily_variance"
        if report_type == "Nutrition Variance"
        else "health_metrics"
        if report_type == "Health Vitals"
        else "activity_logs"
    )
    res = supabase.table(tbl).select("*").order("date", desc=True).execute()
    if res.data:
        st.dataframe(pd.DataFrame(res.data), use_container_width=True)
