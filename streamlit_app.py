import streamlit as st
from supabase import create_client
from datetime import datetime
import pandas as pd
import alt
import io

# 1. Setup
url, key = st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.set_page_config(
    page_title="Health Dashboard Pro", layout="wide", initial_sidebar_state="collapsed"
)

# --- SESSION STATE ---
if "edit_mode" not in st.session_state:
    st.session_state.edit_mode = None
if "edit_data" not in st.session_state:
    st.session_state.edit_data = {}

# --- AUTH ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if not st.session_state.authenticated:
    st.title("🔒 Access Control")
    with st.form("login"):
        pwd = st.text_input("Enter Code", type="password")
        if st.form_submit_button("Login"):
            if pwd == st.secrets["ADMIN_PASSWORD"]:
                st.session_state.update({"authenticated": True, "is_admin": True})
            elif pwd == st.secrets["GUEST_PASSWORD"]:
                st.session_state.update({"authenticated": True, "is_admin": False})
            if st.session_state.authenticated:
                st.rerun()
    st.stop()

active_user = (
    "admin"
    if (
        st.session_state.is_admin
        and st.sidebar.radio("🔎 View Mode", ["Admin Data", "Guest Data"])
        == "Admin Data"
    )
    else "guest"
)
record_owner = "admin" if st.session_state.is_admin else "guest"

tab1, tab2, tab3, tab4 = st.tabs(
    ["🍴 Nutrition", "🩺 Health Metrics", "🏃 Activity", "📊 Reports"]
)

# --- TAB 1: NUTRITION (Manual Entry Restored) ---
with tab1:
    # A. Metrics UI
    try:
        dv = (
            supabase.table("daily_variance")
            .select("*")
            .eq("user_id", active_user)
            .order("date", desc=True)
            .limit(1)
            .execute()
            .data
        )
        if dv:
            d = dv[0]
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric(
                "Calories",
                f"{int(d['total_calories'] or 0)}",
                f"{int(1800 - (d['total_calories'] or 0))} Left",
            )
            c2.metric(
                "Protein",
                f"{int(d['total_protein'] or 0)}g",
                f"{int((d['total_protein'] or 0) - 160)}g",
            )
            c3.metric(
                "Net Carbs",
                f"{int(d['total_net_carbs'] or 0)}g",
                f"{int((d['total_net_carbs'] or 0) - 100)}g Over",
                delta_color="inverse",
            )
            c4.metric(
                "Fat",
                f"{int(d['total_fat'] or 0)}g",
                f"{int(60 - (d['total_fat'] or 0))}g Left",
            )
            c5.metric(
                "Fiber",
                f"{int(d['total_fiber'] or 0)}g",
                f"{int((d['total_fiber'] or 0) - 30)}g Min",
            )
    except:
        st.info("Ready for logs.")

    st.divider()
    # B. Quick Log
    st.markdown("### ⚡ Quick Log")
    freq = (
        supabase.table("daily_logs")
        .select("foods(food_name, food_id)")
        .eq("user_id", active_user)
        .execute()
        .data
    )
    if freq:
        names = [x["foods"]["food_name"] for x in freq if x.get("foods")]
        if names:
            tops = pd.Series(names).value_counts().head(5).index.tolist()
            cols = st.columns(len(tops))
            for i, n in enumerate(tops):
                if cols[i].button(f"➕ {n}"):
                    fid = (
                        supabase.table("foods")
                        .select("food_id")
                        .eq("food_name", n)
                        .execute()
                        .data[0]["food_id"]
                    )
                    supabase.table("daily_logs").insert(
                        {
                            "food_id": fid,
                            "servings": 1.0,
                            "log_date": str(datetime.now().date()),
                            "user_id": record_owner,
                        }
                    ).execute()
                    st.rerun()

    st.divider()
    # C. Manual Entry & Macro Control
    st.markdown("### 📝 Add Food Entry")
    ed_n = st.session_state.edit_data if st.session_state.edit_mode == "nutr" else {}
    entry_type = st.radio(
        "Entry Method", ["Library Search", "Manual Macro Entry"], horizontal=True
    )

    with st.form("nutrition_form"):
        if entry_type == "Library Search":
            f_data = (
                supabase.table("foods").select("*").order("food_name").execute().data
            )
            f_map = {x["food_name"]: x for x in f_data}
            sel = st.selectbox(
                "Select Food",
                options=list(f_map.keys()),
                index=list(f_map.keys()).index(ed_n.get("food_name"))
                if ed_n.get("food_name") in f_map
                else 0,
            )
            srv = st.number_input(
                "Servings", 0.1, 10.0, float(ed_n.get("servings", 1.0))
            )
        else:
            m_name = st.text_input("Item Name", value=ed_n.get("food_name", ""))
            mc1, mc2, mc3, mc4 = st.columns(4)
            m_cal = mc1.number_input("Calories", 0, 2000, 0)
            m_pro = mc2.number_input("Protein (g)", 0, 200, 0)
            m_crb = mc3.number_input("Net Carbs (g)", 0, 200, 0)
            m_fat = mc4.number_input("Fat (g)", 0, 200, 0)

        m_label = st.text_input(
            "Meal Name (Breakfast, Lunch, etc.)", value=ed_n.get("meal_name", "")
        )

        if st.form_submit_button("Save Entry"):
            if entry_type == "Library Search":
                p = {
                    "food_id": f_map[sel]["food_id"],
                    "servings": srv,
                    "log_date": str(datetime.now().date()),
                    "user_id": record_owner,
                    "meal_name": m_label,
                }
            else:
                # Add to foods table first then log
                new_f = (
                    supabase.table("foods")
                    .insert(
                        {
                            "food_name": m_name,
                            "calories": m_cal,
                            "protein_g": m_pro,
                            "carbs_g": m_crb,
                            "fat_g": m_fat,
                            "is_custom": True,
                        }
                    )
                    .execute()
                )
                new_id = new_f.data[0]["food_id"]
                p = {
                    "food_id": new_id,
                    "servings": 1.0,
                    "log_date": str(datetime.now().date()),
                    "user_id": record_owner,
                    "meal_name": m_label,
                }

            if ed_n:
                supabase.table("daily_logs").update(p).eq(
                    "log_id", ed_n["log_id"]
                ).execute()
            else:
                supabase.table("daily_logs").insert(p).execute()
            st.session_state.update({"edit_mode": None, "edit_data": {}})
            st.rerun()

    # D. Daily History
    st.subheader("Today's Log")
    logs = (
        supabase.table("daily_logs")
        .select("*, foods(*)")
        .eq("log_date", str(datetime.now().date()))
        .eq("user_id", active_user)
        .execute()
        .data
    )
    for r in logs or []:
        lc1, lc2, lc3, lc4 = st.columns([3, 1, 0.5, 0.5])
        lc1.write(f"**{r['meal_name'] or 'Entry'}:** {r['foods']['food_name']}")
        lc2.write(f"{int(r['foods']['calories'] * r['servings'])} kcal")
        if lc3.button("📝", key=f"en_{r['log_id']}"):
            st.session_state.update(
                {
                    "edit_mode": "nutr",
                    "edit_data": {**r, "food_name": r["foods"]["food_name"]},
                }
            )
            st.rerun()
        if lc4.button("🗑️", key=f"dn_{r['log_id']}"):
            supabase.table("daily_logs").delete().eq("log_id", r["log_id"]).execute()
            st.rerun()

# --- TAB 2: HEALTH METRICS (Full Inputs + Trends) ---
with tab2:
    st.subheader("🩺 Health Data Entry")
    ed_h = st.session_state.edit_data if st.session_state.edit_mode == "health" else {}
    with st.form("health_form"):
        c1, c2, c3 = st.columns(3)
        w_lb = c1.number_input(
            "Weight (lbs)", 0.0, 500.0, float(ed_h.get("weight_lb", 0.0))
        )
        sys = c2.number_input(
            "Systolic BP", 0, 250, int(ed_h.get("blood_pressure_systolic", 0))
        )
        dia = c3.number_input(
            "Diastolic BP", 0, 150, int(ed_h.get("blood_pressure_diastolic", 0))
        )

        c4, c5 = st.columns(2)
        glu = c4.number_input(
            "Glucose (mg/dL)", 0.0, 500.0, float(ed_h.get("blood_glucose", 0.0))
        )
        nts = c5.text_input("Notes", value=ed_h.get("notes", ""))

        if st.form_submit_button("Save Health Metrics"):
            payload = {
                "date": str(datetime.now().date()),
                "time": datetime.now().strftime("%H:%M:%S"),
                "weight_lb": w_lb,
                "blood_pressure_systolic": sys,
                "blood_pressure_diastolic": dia,
                "blood_glucose": glu,
                "notes": nts,
                "user_id": record_owner,
            }
            if ed_h:
                supabase.table("health_metrics").update(payload).eq(
                    "metric_id", ed_h["metric_id"]
                ).execute()
            else:
                supabase.table("health_metrics").insert(payload).execute()
            st.session_state.update({"edit_mode": None, "edit_data": {}})
            st.rerun()

    st.divider()
    h_data = (
        supabase.table("health_metrics")
        .select("*")
        .eq("user_id", active_user)
        .order("date", desc=False)
        .execute()
        .data
    )
    if h_data:
        df_h = pd.DataFrame(h_data)
        df_h["ts"] = pd.to_datetime(
            df_h["date"].astype(str) + " " + df_h["time"].fillna("00:00:00").astype(str)
        )
        # Triple Chart Trend
        st.subheader("📊 Health Trends")
        base = alt.Chart(df_h).encode(x="ts:T")
        bp = (
            base.transform_fold(["blood_pressure_systolic", "blood_pressure_diastolic"])
            .mark_line(point=True)
            .encode(y="value:Q", color="key:N")
            .properties(height=200, title="Blood Pressure")
        )
        weight_c = (
            base.mark_line(color="green", point=True)
            .encode(y=alt.Y("weight_lb:Q", scale=alt.Scale(zero=False)))
            .properties(height=150, title="Weight Trend")
        )
        glu_c = (
            base.mark_line(color="orange", point=True)
            .encode(y="blood_glucose:Q")
            .properties(height=150, title="Glucose Trend")
        )
        st.altair_chart(alt.vconcat(bp, weight_c, glu_c), use_container_width=True)

# --- TAB 3: ACTIVITY (Conditional UI Restored) ---
with tab3:
    st.subheader("🏃 Activity Tracking")
    ed_a = st.session_state.edit_data if st.session_state.edit_mode == "act" else {}
    a_cat = st.radio(
        "Select Type",
        ["Strength", "Cardio", "Endurance"],
        horizontal=True,
        index=["Strength", "Cardio", "Endurance"].index(
            ed_a.get("activity_category", "Strength")
        ),
    )

    with st.form("activity_form"):
        a_name = st.text_input("Exercise Name", value=ed_a.get("exercise_name", ""))
        c1, c2, c3 = st.columns(3)

        if a_cat == "Strength":
            sets = c1.number_input("Sets", 0, 20, int(ed_a.get("sets", 0)))
            reps = c2.number_input("Reps", 0, 50, int(ed_a.get("reps", 0)))
            lbs = c3.number_input(
                "Weight (lbs)", 0, 1000, int(ed_a.get("weight_lb", 0))
            )
            dur, dist = 0, 0.0
        elif a_cat == "Cardio":
            dur = c1.number_input(
                "Duration (min)", 0, 300, int(ed_a.get("duration_min", 0))
            )
            dist = c2.number_input(
                "Distance (miles)", 0.0, 100.0, float(ed_a.get("distance_miles", 0.0))
            )
            sets, reps, lbs = 0, 0, 0
        else:  # Endurance
            dur = c1.number_input(
                "Duration (min)", 0, 300, int(ed_a.get("duration_min", 0))
            )
            sets = c2.number_input("Sets", 0, 20, int(ed_a.get("sets", 0)))
            reps = c3.number_input("Reps", 0, 100, int(ed_a.get("reps", 0)))
            dist, lbs = 0.0, 0

        if st.form_submit_button("Log Activity"):
            p = {
                "log_date": str(datetime.now().date()),
                "exercise_name": a_name,
                "activity_category": a_cat,
                "sets": sets,
                "reps": reps,
                "weight_lb": lbs,
                "duration_min": dur,
                "distance_miles": dist,
                "user_id": record_owner,
            }
            if ed_a:
                supabase.table("activity_logs").update(p).eq("id", ed_a["id"]).execute()
            else:
                supabase.table("activity_logs").insert(p).execute()
            st.session_state.update({"edit_mode": None, "edit_data": {}})
            st.rerun()

    # Recent Activity with Delete
    a_logs = (
        supabase.table("activity_logs")
        .select("*")
        .eq("user_id", active_user)
        .order("log_date", desc=True)
        .limit(5)
        .execute()
        .data
    )
    for ra in a_logs or []:
        al1, al2, al3, al4 = st.columns([3, 1, 0.5, 0.5])
        al1.write(
            f"**{ra['log_date']}**: {ra['exercise_name']} ({ra['activity_category']})"
        )
        if al3.button("📝", key=f"ea_{ra['id']}"):
            st.session_state.update({"edit_mode": "act", "edit_data": ra})
            st.rerun()
        if al4.button("🗑️", key=f"da_{ra['id']}"):
            supabase.table("activity_logs").delete().eq("id", ra["id"]).execute()
            st.rerun()

# --- TAB 4: REPORTS (Full Master Export Restored) ---
with tab4:
    st.subheader("📊 Master Data Export")
    tables = [
        "daily_logs",
        "health_metrics",
        "activity_logs",
        "foods",
        "daily_variance",
    ]
    selected_tbl = st.selectbox("Select Table to Preview & Export", tables)

    # Logic to fetch based on table type
    q = supabase.table(selected_tbl).select("*")
    if selected_tbl not in ["foods", "daily_variance"]:
        q = q.eq("user_id", active_user)

    data = q.execute().data
    if data:
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True)

        # Proper CSV Export
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label=f"📥 Download {selected_tbl}.csv",
            data=csv,
            file_name=f"{selected_tbl}_full.csv",
            mime="text/csv",
        )
    else:
        st.warning("No data found.")
