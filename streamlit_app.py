import streamlit as st
from supabase import create_client
from datetime import datetime
import pandas as pd
import altair as alt
import io

# --- 1. DATABASE SETUP ---
url, key = st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

# --- 2. PAGE CONFIG ---
st.set_page_config(
    page_title="Health Dashboard Pro", layout="wide", initial_sidebar_state="collapsed"
)

# --- 3. SESSION STATE ---
if "edit_mode" not in st.session_state:
    st.session_state.edit_mode = None
if "edit_data" not in st.session_state:
    st.session_state.edit_data = {}
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# --- 4. AUTHENTICATION ---
if not st.session_state.authenticated:
    st.title("🔒 Private Access")
    with st.form("login"):
        pwd = st.text_input("Enter Access Code", type="password")
        if st.form_submit_button("Login"):
            if pwd == st.secrets["ADMIN_PASSWORD"]:
                st.session_state.update({"authenticated": True, "is_admin": True})
                st.rerun()
            elif pwd == st.secrets["GUEST_PASSWORD"]:
                st.session_state.update({"authenticated": True, "is_admin": False})
                st.rerun()
    st.stop()

active_user = (
    "admin"
    if (
        st.session_state.is_admin
        and st.sidebar.radio("🔎 View Mode", ["Admin", "Guest"]) == "Admin"
    )
    else "guest"
)
record_owner = "admin" if st.session_state.is_admin else "guest"

# --- 5. TABS ---
tab1, tab2, tab3, tab4 = st.tabs(
    ["🍴 Nutrition", "🩺 Health Metrics", "🏃 Activity", "📊 Reports"]
)

# =================================================================
# TAB 1: NUTRITION (RESTORING FULL TARGET VALUES)
# =================================================================
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
        st.info("Ready for logs.")

    st.divider()

    # --- MANUAL ENTRY WITH CORRECT TARGET VALUES ---
    st.markdown("### 📝 Log Entry")
    ed_n = st.session_state.edit_data if st.session_state.edit_mode == "nutr" else {}
    method = st.radio(
        "Entry Method", ["Search Database", "Manual Macro Entry"], horizontal=True
    )

    with st.form("nutr_form"):
        if method == "Search Database":
            f_data = (
                supabase.table("foods").select("*").order("food_name").execute().data
            )
            f_names = [x["food_name"] for x in f_data]
            sel_food = st.selectbox(
                "Select Item",
                options=f_names,
                index=f_names.index(ed_n.get("food_name"))
                if ed_n.get("food_name") in f_names
                else 0,
            )
            servings = st.number_input(
                "Servings", 0.1, 10.0, float(ed_n.get("servings", 1.0))
            )
        else:
            # RESTORED: Explicit target values calories, protein_g, carbs_g, fat_g
            manual_name = st.text_input("Food Name", value=ed_n.get("food_name", ""))
            col1, col2, col3, col4 = st.columns(4)
            calories = col1.number_input("Calories", 0, 2000, 0)
            protein_g = col2.number_input("Protein (g)", 0, 200, 0)
            carbs_g = col3.number_input("Net Carbs (g)", 0, 200, 0)
            fat_g = col4.number_input("Fat (g)", 0, 200, 0)
            fiber_g = st.number_input("Fiber (g)", 0, 100, 0)

        meal_name = st.text_input(
            "Meal Label", value=ed_n.get("meal_name", ""), placeholder="e.g. Lunch"
        )

        if st.form_submit_button("Save Log Entry"):
            if method == "Search Database":
                f_obj = next(x for x in f_data if x["food_name"] == sel_food)
                payload = {
                    "food_id": f_obj["food_id"],
                    "servings": servings,
                    "log_date": str(datetime.now().date()),
                    "user_id": record_owner,
                    "meal_name": meal_name,
                }
            else:
                # Add to food library first using correct keys
                new_f = (
                    supabase.table("foods")
                    .insert(
                        {
                            "food_name": manual_name,
                            "calories": calories,
                            "protein_g": protein_g,
                            "carbs_g": carbs_g,
                            "fat_g": fat_g,
                            "fiber_g": fiber_g,
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
                    "meal_name": meal_name,
                }

            if ed_n:
                supabase.table("daily_logs").update(payload).eq(
                    "log_id", ed_n["log_id"]
                ).execute()
            else:
                supabase.table("daily_logs").insert(payload).execute()
            st.session_state.update({"edit_mode": None, "edit_data": {}})
            st.rerun()

# =================================================================
# TAB 2: HEALTH METRICS (RESTORING FIXED SCALING & SEPARATE INPUTS)
# =================================================================
with tab2:
    st.subheader("🩺 Vital Signs")
    ed_h = st.session_state.edit_data if st.session_state.edit_mode == "health" else {}

    with st.form("health_form"):
        st.markdown("#### Individual Metrics")
        h_col1, h_col2 = st.columns(2)
        weight_lb = h_col1.number_input(
            "⚖️ Weight (lb)", 50.0, 500.0, float(ed_h.get("weight_lb", 185.0)), step=0.1
        )
        blood_glucose = h_col2.number_input(
            "🧪 Glucose (mg/dL)",
            0.0,
            500.0,
            float(ed_h.get("blood_glucose", 95.0)),
            step=1.0,
        )

        st.markdown("#### Blood Pressure")
        bp_col1, bp_col2 = st.columns(2)
        blood_pressure_systolic = bp_col1.number_input(
            "🩸 Systolic", 50, 250, int(ed_h.get("blood_pressure_systolic", 120))
        )
        blood_pressure_diastolic = bp_col2.number_input(
            "🩸 Diastolic", 30, 160, int(ed_h.get("blood_pressure_diastolic", 80))
        )

        notes = st.text_input("📝 Notes", value=ed_h.get("notes", ""))

        if st.form_submit_button("Save Health Record"):
            h_payload = {
                "date": str(datetime.now().date()),
                "time": datetime.now().strftime("%H:%M:%S"),
                "weight_lb": weight_lb,
                "blood_glucose": blood_glucose,
                "blood_pressure_systolic": blood_pressure_systolic,
                "blood_pressure_diastolic": blood_pressure_diastolic,
                "notes": notes,
                "user_id": record_owner,
            }
            if ed_h:
                supabase.table("health_metrics").update(h_payload).eq(
                    "metric_id", ed_h["metric_id"]
                ).execute()
            else:
                supabase.table("health_metrics").insert(h_payload).execute()
            st.session_state.update({"edit_mode": None, "edit_data": {}})
            st.rerun()

    # --- CHARTS WITH FIXED DOMAINS & NO INTERFERENCE ---
    h_data = (
        supabase.table("health_metrics")
        .select("*")
        .eq("user_id", active_user)
        .order("date", desc=False)
        .execute()
        .data
    )
    if h_data:
        df = pd.DataFrame(h_data)
        df["ts"] = pd.to_datetime(
            df["date"].astype(str) + " " + df["time"].fillna("00:00:00").astype(str)
        )

        st.markdown("### Trends")
        # BP Chart - Fixed 40-200 domain
        bp_chart = (
            alt.Chart(df)
            .transform_fold(["blood_pressure_systolic", "blood_pressure_diastolic"])
            .mark_line(point=True)
            .encode(
                x=alt.X("ts:T", title="Time", axis=alt.Axis(format="%m/%d %H:%M")),
                y=alt.Y("value:Q", scale=alt.Scale(domain=[40, 200]), title="BP mmHg"),
                color="key:N",
            )
            .properties(height=300)
            .interactive(bind_y=False)
        )
        st.altair_chart(bp_chart, use_container_width=True)

        # Glucose Chart - Fixed 50-250 domain
        glu_chart = (
            alt.Chart(df)
            .mark_area(
                line={"color": "orange"},
                color=alt.Gradient(
                    gradient="linear",
                    stops=[
                        alt.GradientStop(color="white", offset=0),
                        alt.GradientStop(color="orange", offset=1),
                    ],
                    x1=1,
                    x2=1,
                    y1=1,
                    y2=0,
                ),
            )
            .encode(
                x=alt.X("ts:T", title=None),
                y=alt.Y(
                    "blood_glucose:Q",
                    scale=alt.Scale(domain=[50, 250]),
                    title="Glucose",
                ),
            )
            .properties(height=200)
            .interactive(bind_y=False)
        )
        st.altair_chart(glu_chart, use_container_width=True)

# =================================================================
# TAB 3: ACTIVITY (RESTORING CONDITIONAL INPUTS)
# =================================================================
with tab3:
    st.subheader("🏃 Activity Log")
    ed_a = st.session_state.edit_data if st.session_state.edit_mode == "act" else {}
    cat = st.radio(
        "Type",
        ["Strength", "Cardio", "Endurance"],
        horizontal=True,
        index=["Strength", "Cardio", "Endurance"].index(
            ed_a.get("activity_category", "Strength")
        ),
    )

    with st.form("activity_form"):
        exercise_name = st.text_input("Exercise", value=ed_a.get("exercise_name", ""))
        c1, c2, c3 = st.columns(3)
        if cat == "Strength":
            sets = c1.number_input("Sets", 0, 50, int(ed_a.get("sets", 0)))
            reps = c2.number_input("Reps", 0, 100, int(ed_a.get("reps", 0)))
            weight_lb = c3.number_input(
                "Weight (lb)", 0, 1000, int(ed_a.get("weight_lb", 0))
            )
            duration_min, distance_miles = 0, 0.0
        elif cat == "Cardio":
            duration_min = c1.number_input(
                "Duration (min)", 0, 500, int(ed_a.get("duration_min", 0))
            )
            distance_miles = c2.number_input(
                "Distance (mi)", 0.0, 100.0, float(ed_a.get("distance_miles", 0.0))
            )
            sets, reps, weight_lb = 0, 0, 0
        else:
            duration_min = c1.number_input(
                "Duration (min)", 0, 500, int(ed_a.get("duration_min", 0))
            )
            sets = c2.number_input("Sets", 0, 50, int(ed_a.get("sets", 0)))
            reps = c3.number_input("Reps", 0, 500, int(ed_a.get("reps", 0)))
            distance_miles, weight_lb = 0.0, 0

        if st.form_submit_button("Save Activity"):
            a_payload = {
                "log_date": str(datetime.now().date()),
                "exercise_name": exercise_name,
                "activity_category": cat,
                "sets": sets,
                "reps": reps,
                "weight_lb": weight_lb,
                "duration_min": duration_min,
                "distance_miles": distance_miles,
                "user_id": record_owner,
            }
            if ed_a:
                supabase.table("activity_logs").update(a_payload).eq(
                    "id", ed_a["id"]
                ).execute()
            else:
                supabase.table("activity_logs").insert(a_payload).execute()
            st.session_state.update({"edit_mode": None, "edit_data": {}})
            st.rerun()

# =================================================================
# TAB 4: REPORTS (RESTORED MASTER GLOBAL VIEW)
# =================================================================
with tab4:
    st.subheader("📊 Master System Export")
    # This loop restores the "Pull all entries" logic for the full database
    tables = [
        "daily_logs",
        "health_metrics",
        "activity_logs",
        "foods",
        "daily_variance",
    ]
    for t in tables:
        with st.expander(f"📁 Master Dataset: {t.upper()}"):
            q = supabase.table(t).select("*")
            if t not in ["foods", "daily_variance"]:
                q = q.eq("user_id", active_user)
            res = q.execute().data
            if res:
                df_exp = pd.DataFrame(res)
                st.dataframe(df_exp, use_container_width=True)
                csv = df_exp.to_csv(index=False).encode("utf-8")
                st.download_button(
                    f"📥 Download {t}.csv",
                    csv,
                    f"MASTER_{t}.csv",
                    "text/csv",
                    key=f"dl_{t}",
                )
