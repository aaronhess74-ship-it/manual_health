import streamlit as st
from supabase import create_client
from datetime import datetime
import pandas as pd
import altair as alt

# 1. Connection
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
    st.title("🔒 Private Health Cloud")
    with st.form("login"):
        pwd = st.text_input("Access Code", type="password")
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
        and st.sidebar.radio("View", ["Admin", "Guest"]) == "Admin"
    )
    else "guest"
)
record_owner = "admin" if st.session_state.is_admin else "guest"

tab1, tab2, tab3, tab4 = st.tabs(
    ["🍴 Nutrition", "🩺 Health Metrics", "🏃 Activity", "📊 Reports"]
)

# --- TAB 1: NUTRITION ---
with tab1:
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
            st.subheader(f"Nutrition Snapshot: {d['date']}")
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric(
                "Calories",
                f"{int(d['total_calories'] or 0)}",
                f"{int(1800 - (d['total_calories'] or 0))} Left",
            )
            c2.metric(
                "Protein",
                f"{int(d['total_protein'] or 0)}g",
                f"{int((d['total_protein'] or 0) - 160)}g vs Goal",
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
                f"{int((d['total_fiber'] or 0) - 30)}g vs Min",
            )
    except:
        st.info("Welcome! Start logging below.")

    st.divider()
    st.markdown("### ⚡ Quick Log")
    freq_data = (
        supabase.table("daily_logs")
        .select("foods(food_name, food_id)")
        .eq("user_id", active_user)
        .execute()
        .data
    )
    if freq_data:
        names = [x["foods"]["food_name"] for x in freq_data if x.get("foods")]
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
                            "meal_name": "Quick Log",
                        }
                    ).execute()
                    st.rerun()

    st.divider()
    st.markdown("### 📝 Detailed Food Entry")
    ed_n = st.session_state.edit_data if st.session_state.edit_mode == "nutr" else {}
    f_all = supabase.table("foods").select("*").order("food_name").execute().data
    if f_all:
        f_map = {x["food_name"]: x for x in f_all}
        with st.form("nutrition_form"):
            col1, col2 = st.columns(2)
            sel_f = col1.selectbox(
                "Food Item",
                options=list(f_map.keys()),
                index=list(f_map.keys()).index(ed_n.get("food_name"))
                if ed_n.get("food_name") in f_map
                else 0,
            )
            meal = col2.text_input(
                "Meal Name (e.g. Breakfast)", value=ed_n.get("meal_name", "")
            )
            srv_f = st.number_input(
                "Servings", 0.1, 10.0, float(ed_n.get("servings", 1.0))
            )

            if st.form_submit_button("Update Entry" if ed_n else "Log Entry"):
                payload = {
                    "food_id": f_map[sel_f]["food_id"],
                    "servings": srv_f,
                    "log_date": str(datetime.now().date()),
                    "user_id": record_owner,
                    "meal_name": meal,
                }
                if ed_n:
                    supabase.table("daily_logs").update(payload).eq(
                        "log_id", ed_n["log_id"]
                    ).execute()
                else:
                    supabase.table("daily_logs").insert(payload).execute()
                st.session_state.update({"edit_mode": None, "edit_data": {}})
                st.rerun()
        if ed_n:
            if st.button("Cancel Edit"):
                st.session_state.update({"edit_mode": None, "edit_data": {}})
                st.rerun()

    st.divider()
    logs = (
        supabase.table("daily_logs")
        .select("*, foods(food_name, calories)")
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

# --- TAB 2: HEALTH METRICS ---
with tab2:
    st.subheader("🩺 Clinical Data Entry")
    ed_h = st.session_state.edit_data if st.session_state.edit_mode == "health" else {}
    with st.form("health_form"):
        c1, c2, c3 = st.columns(3)
        weight = c1.number_input(
            "Weight (lb)", 0.0, 500.0, float(ed_h.get("weight_lb", 0.0))
        )
        sys = c2.number_input(
            "Systolic", 0, 250, int(ed_h.get("blood_pressure_systolic", 0))
        )
        dia = c3.number_input(
            "Diastolic", 0, 150, int(ed_h.get("blood_pressure_diastolic", 0))
        )

        c4, c5 = st.columns(2)
        glucose = c4.number_input(
            "Blood Glucose", 0.0, 500.0, float(ed_h.get("blood_glucose", 0.0))
        )
        notes_h = c5.text_input("Notes", value=ed_h.get("notes", ""))

        if st.form_submit_button("Save Health Record"):
            payload = {
                "date": str(datetime.now().date()),
                "time": datetime.now().strftime("%H:%M:%S"),
                "weight_lb": weight,
                "blood_pressure_systolic": sys,
                "blood_pressure_diastolic": dia,
                "blood_glucose": glucose,
                "notes": notes_h,
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
    if ed_h and st.button("Cancel Health Edit"):
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
        st.subheader("📊 Health Trends")
        chart = (
            alt.Chart(df_h)
            .transform_fold(
                ["blood_pressure_systolic", "blood_pressure_diastolic"],
                as_=["Metric", "Value"],
            )
            .encode(
                x="ts:T",
                y=alt.Y("Value:Q", scale=alt.Scale(zero=False)),
                color="Metric:N",
            )
            .mark_line(point=True)
            .properties(height=300)
        )
        st.altair_chart(chart, use_container_width=True)

# --- TAB 3: ACTIVITY ---
with tab3:
    st.subheader("🏃 Training Log")
    ed_a = st.session_state.edit_data if st.session_state.edit_mode == "act" else {}
    with st.form("activity_form"):
        name_a = st.text_input("Exercise Name", value=ed_a.get("exercise_name", ""))
        cat_list = ["Strength", "Cardio", "Endurance"]
        cat_a = st.selectbox(
            "Category",
            cat_list,
            index=cat_list.index(ed_a.get("activity_category", "Strength")),
        )

        c1, c2, c3, c4, c5 = st.columns(5)
        sets = c1.number_input("Sets", 0, 50, int(ed_a.get("sets", 0)))
        reps = c2.number_input("Reps", 0, 1000, int(ed_a.get("reps", 0)))
        lbs = c3.number_input("Weight (lb)", 0, 1000, int(ed_a.get("weight_lb", 0)))
        mins = c4.number_input(
            "Duration (min)", 0, 1440, int(ed_a.get("duration_min", 0))
        )
        miles = c5.number_input(
            "Distance (mi)", 0.0, 100.0, float(ed_a.get("distance_miles", 0.0))
        )

        if st.form_submit_button("Save Activity"):
            payload = {
                "log_date": str(datetime.now().date()),
                "exercise_name": name_a,
                "activity_category": cat_a,
                "sets": sets,
                "reps": reps,
                "weight_lb": lbs,
                "duration_min": mins,
                "distance_miles": miles,
                "user_id": record_owner,
            }
            if ed_a:
                supabase.table("activity_logs").update(payload).eq(
                    "id", ed_a["id"]
                ).execute()
            else:
                supabase.table("activity_logs").insert(payload).execute()
            st.session_state.update({"edit_mode": None, "edit_data": {}})
            st.rerun()

    st.divider()
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

# --- TAB 4: REPORTS & MASTER EXPORT ---
with tab4:
    st.subheader("📊 Master Data Management")
    tbl_choice = st.selectbox(
        "Select Table to View/Export",
        ["health_metrics", "activity_logs", "daily_logs", "foods", "daily_variance"],
    )

    # Precise query logic based on schema
    query = supabase.table(tbl_choice).select("*")
    if tbl_choice not in ["foods", "daily_variance"]:
        query = query.eq("user_id", active_user)

    data = query.limit(500).execute().data
    if data:
        df_master = pd.DataFrame(data)
        st.dataframe(df_master, use_container_width=True)

        # FIXED EXPORT: Handles CSV encoding and dynamic filename
        csv = df_master.to_csv(index=False).encode("utf-8")
        st.download_button(
            label=f"📥 Download {tbl_choice.replace('_', ' ').title()} as CSV",
            data=csv,
            file_name=f"{tbl_choice}_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )
    else:
        st.warning("No data found for this selection.")
