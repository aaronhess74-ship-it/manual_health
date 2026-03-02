import streamlit as st
from supabase import create_client
from datetime import datetime
import pandas as pd
import altair as alt  # Fixed: Changed from 'import alt' to 'import altair as alt'
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
        and st.sidebar.radio("🔎 View Mode", ["Admin Data", "Guest Data"])
        == "Admin Data"
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
                f"{int((d['total_protein'] or 0) - 160)}g Goal",
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
        st.info("Logged data will appear here.")

    st.divider()
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
                            "meal_name": "Quick Log",
                        }
                    ).execute()
                    st.rerun()

    st.divider()
    # RESTORED: Manual Food Entry & Macro Control
    st.markdown("### 📝 Add Food Entry")
    ed_n = st.session_state.edit_data if st.session_state.edit_mode == "nutr" else {}
    entry_method = st.radio(
        "Entry Method", ["Search Library", "Manual Macro Entry"], horizontal=True
    )

    with st.form("nutrition_form"):
        if entry_method == "Search Library":
            f_data = (
                supabase.table("foods").select("*").order("food_name").execute().data
            )
            f_map = {x["food_name"]: x for x in f_data}
            sel_f = st.selectbox(
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
            m_name = st.text_input("New Item Name", value=ed_n.get("food_name", ""))
            mc1, mc2, mc3, mc4 = st.columns(4)
            m_cal = mc1.number_input("Calories", 0, 2000, 0)
            m_pro = mc2.number_input("Protein (g)", 0, 200, 0)
            m_crb = mc3.number_input("Net Carbs (g)", 0, 200, 0)
            m_fat = mc4.number_input("Fat (g)", 0, 200, 0)

        meal_label = st.text_input(
            "Meal Name (Breakfast, etc.)", value=ed_n.get("meal_name", "")
        )

        if st.form_submit_button("Update Log" if ed_n else "Save Entry"):
            if entry_method == "Search Library":
                payload = {
                    "food_id": f_map[sel_f]["food_id"],
                    "servings": srv,
                    "log_date": str(datetime.now().date()),
                    "user_id": record_owner,
                    "meal_name": meal_label,
                }
            else:
                # Add to foods table as custom entry
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
                payload = {
                    "food_id": new_f.data[0]["food_id"],
                    "servings": 1.0,
                    "log_date": str(datetime.now().date()),
                    "user_id": record_owner,
                    "meal_name": meal_label,
                }

            if ed_n:
                supabase.table("daily_logs").update(payload).eq(
                    "log_id", ed_n["log_id"]
                ).execute()
            else:
                supabase.table("daily_logs").insert(payload).execute()
            st.session_state.update({"edit_mode": None, "edit_data": {}})
            st.rerun()

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

# --- TAB 2: HEALTH METRICS ---
with tab2:
    st.subheader("🩺 Clinical Log")
    ed_h = st.session_state.edit_data if st.session_state.edit_mode == "health" else {}
    with st.form("health_form"):
        c1, c2, c3 = st.columns(3)
        weight = c1.number_input(
            "Weight (lb)", 0.0, 500.0, float(ed_h.get("weight_lb", 0.0))
        )
        systolic = c2.number_input(
            "Systolic BP", 0, 250, int(ed_h.get("blood_pressure_systolic", 0))
        )
        diastolic = c3.number_input(
            "Diastolic BP", 0, 150, int(ed_h.get("blood_pressure_diastolic", 0))
        )

        c4, c5 = st.columns(2)
        glucose = c4.number_input(
            "Glucose (mg/dL)", 0.0, 500.0, float(ed_h.get("blood_glucose", 0.0))
        )
        notes = c5.text_input("Notes", value=ed_h.get("notes", ""))

        if st.form_submit_button("Save Clinical Record"):
            p = {
                "date": str(datetime.now().date()),
                "time": datetime.now().strftime("%H:%M:%S"),
                "weight_lb": weight,
                "blood_pressure_systolic": systolic,
                "blood_pressure_diastolic": diastolic,
                "blood_glucose": glucose,
                "notes": notes,
                "user_id": record_owner,
            }
            if ed_h:
                supabase.table("health_metrics").update(p).eq(
                    "metric_id", ed_h["metric_id"]
                ).execute()
            else:
                supabase.table("health_metrics").insert(p).execute()
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
        # RESTORED: Multi-chart Trends
        bp_chart = (
            alt.Chart(df_h)
            .transform_fold(["blood_pressure_systolic", "blood_pressure_diastolic"])
            .mark_line(point=True)
            .encode(
                x="ts:T",
                y=alt.Y("value:Q", scale=alt.Scale(zero=False), title="BP"),
                color="key:N",
            )
            .properties(height=200)
        )

        weight_chart = (
            alt.Chart(df_h)
            .mark_line(color="green", point=True)
            .encode(
                x="ts:T",
                y=alt.Y("weight_lb:Q", scale=alt.Scale(zero=False), title="Weight"),
            )
            .properties(height=150)
        )

        glu_chart = (
            alt.Chart(df_h)
            .mark_line(color="orange", point=True)
            .encode(x="ts:T", y=alt.Y("blood_glucose:Q", title="Glucose"))
            .properties(height=150)
        )

        st.altair_chart(
            alt.vconcat(bp_chart, weight_chart, glu_chart), use_container_width=True
        )

# --- TAB 3: ACTIVITY ---
with tab3:
    st.subheader("🏃 Training Log")
    ed_a = st.session_state.edit_data if st.session_state.edit_mode == "act" else {}
    # RESTORED: Activity Logic
    a_cat = st.radio(
        "Activity Type",
        ["Strength", "Cardio", "Endurance"],
        horizontal=True,
        index=["Strength", "Cardio", "Endurance"].index(
            ed_a.get("activity_category", "Strength")
        ),
    )

    with st.form("activity_form"):
        a_name = st.text_input("Exercise", value=ed_a.get("exercise_name", ""))
        c1, c2, c3 = st.columns(3)

        if a_cat == "Strength":
            sets, reps, weight_lb = (
                c1.number_input("Sets", 0, 50, int(ed_a.get("sets", 0))),
                c2.number_input("Reps", 0, 100, int(ed_a.get("reps", 0))),
                c3.number_input("Weight (lb)", 0, 1000, int(ed_a.get("weight_lb", 0))),
            )
            dur, dist = 0, 0.0
        elif a_cat == "Cardio":
            dur, dist = (
                c1.number_input(
                    "Duration (min)", 0, 500, int(ed_a.get("duration_min", 0))
                ),
                c2.number_input(
                    "Distance (mi)", 0.0, 100.0, float(ed_a.get("distance_miles", 0.0))
                ),
            )
            sets, reps, weight_lb = 0, 0, 0
        else:  # Endurance
            dur, sets, reps = (
                c1.number_input(
                    "Duration (min)", 0, 500, int(ed_a.get("duration_min", 0))
                ),
                c2.number_input("Sets", 0, 50, int(ed_a.get("sets", 0))),
                c3.number_input("Reps", 0, 500, int(ed_a.get("reps", 0))),
            )
            dist, weight_lb = 0.0, 0

        if st.form_submit_button("Update" if ed_a else "Save Activity"):
            p = {
                "log_date": str(datetime.now().date()),
                "exercise_name": a_name,
                "activity_category": a_cat,
                "sets": sets,
                "reps": reps,
                "weight_lb": weight_lb,
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

# --- TAB 4: REPORTS ---
with tab4:
    st.subheader("📊 Master Export")
    # RESTORED: Full Table Selector and Export
    tbl_list = [
        "daily_logs",
        "health_metrics",
        "activity_logs",
        "foods",
        "daily_variance",
    ]
    target = st.selectbox("Select Table to View/Download", tbl_list)

    q = supabase.table(target).select("*")
    if target not in ["foods", "daily_variance"]:
        q = q.eq("user_id", active_user)

    raw_data = q.execute().data
    if raw_data:
        df_final = pd.DataFrame(raw_data)
        st.dataframe(df_final, use_container_width=True)
        csv_data = df_final.to_csv(index=False).encode("utf-8")
        st.download_button(
            label=f"📥 Download {target}.csv",
            data=csv_data,
            file_name=f"{target}_master.csv",
            mime="text/csv",
        )
