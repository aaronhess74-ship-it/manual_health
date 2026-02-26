import streamlit as st
from supabase import create_client
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# 1. Setup Connection
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.set_page_config(page_title="My Health Dashboard", layout="wide")
st.title("💪 My Health Dashboard")

# Targets
TARGET_CALORIES = 2000
TARGET_PROTEIN = 150
TARGET_NET_CARBS = 50
TARGET_FIBER_MIN = 30
TARGET_FAT_MAX = 70

COLOR_NORMAL, COLOR_WARNING, COLOR_DANGER = "#2ecc71", "#f1c40f", "#e74c3c"

tab1, tab2, tab3 = st.tabs(
    ["🍴 Nutrition Budget", "🩺 Health Metrics", "🏃 Activity Tracker"]
)

# --- TAB 1: NUTRITION BUDGET ---
with tab1:
    try:
        response = supabase.table("daily_variance").select("*").execute()
        if response.data:
            latest = response.data[0]
            st.subheader(f"Status for {latest['date']}")
            c1, c2, c3, c4, c5 = st.columns(5)

            # Current Values
            cals = int(latest.get("total_calories", 0))
            prot = int(latest.get("total_protein", 0))
            net_c = int(latest.get("total_net_carbs", 0))
            fat = int(latest.get("total_fat", 0))
            fib = int(latest.get("total_fiber", 0))

            # 1. Calories (Ceiling)
            c1.metric(
                "Calories",
                f"{cals}",
                f"{TARGET_CALORIES - cals} Left",
                delta_color="normal" if cals <= TARGET_CALORIES else "inverse",
            )

            # 2. Protein (Floor)
            c2.metric(
                "Protein",
                f"{prot}g",
                f"{prot - TARGET_PROTEIN} vs Target",
                delta_color="normal" if prot >= TARGET_PROTEIN else "inverse",
            )

            # 3. Net Carbs (Ceiling)
            c3.metric(
                "Net Carbs",
                f"{net_c}g",
                f"{TARGET_NET_CARBS - net_c} Left",
                delta_color="normal" if net_c <= TARGET_NET_CARBS else "inverse",
            )

            # 4. Total Fat (Ceiling: Max 70g)
            c4.metric(
                "Total Fat",
                f"{fat}g",
                f"{TARGET_FAT_MAX - fat} Left",
                delta_color="normal" if fat <= TARGET_FAT_MAX else "inverse",
            )

            # 5. Fiber (Floor: Min 30g)
            c5.metric(
                "Fiber",
                f"{fib}g",
                f"{fib - TARGET_FIBER_MIN} vs Target",
                delta_color="normal" if fib >= TARGET_FIBER_MIN else "inverse",
            )

    except Exception as e:
        st.error(f"Error loading dashboard: {e}")

    st.divider()
    st.subheader("⚡ Quick Log")
    try:
        recent_logs = (
            supabase.table("daily_logs")
            .select("food_id, foods(food_name)")
            .order("log_id", desc=True)
            .limit(20)
            .execute()
        )
        if recent_logs.data:
            seen, quick_foods = set(), []
            for r in recent_logs.data:
                fid, fname = r["food_id"], r["foods"]["food_name"]
                if fid not in seen:
                    quick_foods.append({"id": fid, "name": fname})
                    seen.add(fid)
                if len(quick_foods) == 5:
                    break
            cols = st.columns(len(quick_foods))
            for i, food in enumerate(quick_foods):
                if cols[i].button(f"➕ {food['name']}", key=f"q_{food['id']}"):
                    supabase.table("daily_logs").insert(
                        {
                            "food_id": food["id"],
                            "servings": 1.0,
                            "log_date": str(datetime.now().date()),
                        }
                    ).execute()
                    st.rerun()
    except:
        st.caption("Log items to see Quick Log.")

    st.divider()
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("🍴 Log Existing Food")
        try:
            food_query = (
                supabase.table("foods").select("*").order("food_name").execute()
            )
            if food_query.data:
                food_dict = {f["food_name"]: f for f in food_query.data}
                selected_name = st.selectbox(
                    "Search database...", options=list(food_dict.keys()), index=None
                )
                if selected_name:
                    selected_food = food_dict[selected_name]
                    fat_v, fib_v = (
                        selected_food.get("fat_g"),
                        selected_food.get("fiber_g"),
                    )
                    if (
                        fat_v is None
                        or pd.isna(fat_v)
                        or fib_v is None
                        or pd.isna(fib_v)
                    ):
                        st.info(f"💡 Updating macros for {selected_name}")
                        u_fat = st.number_input("Fat (g)", value=0.0)
                        u_fib = st.number_input("Fiber (g)", value=0.0)
                        if st.button("Update & Log"):
                            supabase.table("foods").update(
                                {"fat_g": u_fat, "fiber_g": u_fib}
                            ).eq("food_id", selected_food["food_id"]).execute()
                            supabase.table("daily_logs").insert(
                                {
                                    "food_id": selected_food["food_id"],
                                    "servings": 1.0,
                                    "log_date": str(datetime.now().date()),
                                }
                            ).execute()
                            st.rerun()
                    else:
                        servings = st.number_input(
                            "Servings", min_value=0.1, value=1.0, step=0.1
                        )
                        if st.button("Log Meal"):
                            supabase.table("daily_logs").insert(
                                {
                                    "food_id": selected_food["food_id"],
                                    "servings": servings,
                                    "log_date": str(datetime.now().date()),
                                }
                            ).execute()
                            st.rerun()
        except:
            pass

    with col_b:
        st.subheader("🆕 Add New Food")
        with st.form("new_food_form", clear_on_submit=True):
            n_name = st.text_input("Food Name")
            c1, c2, c3 = st.columns(3)
            n_cal, n_pro, n_carb = (
                c1.number_input("Cals", 0),
                c2.number_input("Prot", 0),
                c3.number_input("Carb", 0),
            )
            c4, c5 = st.columns(2)
            n_fat, n_fib = c4.number_input("Fat", 0), c5.number_input("Fiber", 0)
            if st.form_submit_button("Save & Log"):
                if n_name:
                    res = (
                        supabase.table("foods")
                        .insert(
                            {
                                "food_name": n_name,
                                "calories": n_cal,
                                "protein_g": n_pro,
                                "carbs_g": n_carb,
                                "fat_g": n_fat,
                                "fiber_g": n_fib,
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
    st.subheader("📜 Today's Log History")
    try:
        history_res = (
            supabase.table("daily_logs")
            .select("log_id, servings, foods(food_name, calories)")
            .eq("log_date", str(datetime.now().date()))
            .execute()
        )
        if history_res.data:
            for item in history_res.data:
                hc1, hc2, hc3 = st.columns([3, 1, 1])
                hc1.write(f"**{item['foods']['food_name']}**")
                hc2.write(f"{int(item['foods']['calories'] * item['servings'])} cal")
                if hc3.button("🗑️", key=f"del_{item['log_id']}"):
                    supabase.table("daily_logs").delete().eq(
                        "log_id", item["log_id"]
                    ).execute()
                    st.rerun()
    except:
        pass

# --- TAB 2: HEALTH METRICS ---
with tab2:
    try:
        last_res = (
            supabase.table("health_metrics")
            .select("*")
            .order("date", desc=True)
            .order("time", desc=True)
            .limit(1)
            .execute()
        )
        if last_res.data:
            v = last_res.data[0]
            s, d, g, w = (
                int(v["blood_pressure_systolic"]),
                int(v["blood_pressure_diastolic"]),
                int(v["blood_glucose"]),
                float(v["weight_lb"]),
            )
            st.subheader("🏷️ Latest Vitals")
            m1, m2, m3 = st.columns(3)
            m1.metric("Blood Pressure", f"{s}/{d}")
            m2.metric("Glucose", f"{g} mg/dL")
            m3.metric("Weight", f"{w} lbs")
    except:
        pass
    with st.expander("Log New Vitals"):
        with st.form("v_form", clear_on_submit=True):
            col_d, col_t = st.columns(2)
            d_val, t_val = col_d.date_input("Date"), col_t.time_input("Time")
            c1, c2, c3 = st.columns(3)
            sys, dia = (
                c1.number_input("Systolic", 120),
                c2.number_input("Diastolic", 80),
            )
            weight_v, glu_v = (
                c3.number_input("Weight", value=180.0),
                st.number_input("Glucose", value=100),
            )
            if st.form_submit_button("Save"):
                supabase.table("health_metrics").insert(
                    {
                        "date": str(d_val),
                        "time": str(t_val),
                        "blood_pressure_systolic": sys,
                        "blood_pressure_diastolic": dia,
                        "blood_glucose": glu_v,
                        "weight_lb": weight_v,
                    }
                ).execute()
                st.rerun()

# --- TAB 3: ACTIVITY TRACKER ---
with tab3:
    st.subheader("🏃 Log Activity")
    category = st.radio(
        "Activity Type:", ["Strength", "Static", "Cardio"], horizontal=True
    )
    with st.form("activity_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        ex_date, ex_name = col1.date_input("Date"), col2.text_input("Exercise Name")
        c1, c2, c3 = st.columns(3)
        dur, sets, reps, dist = 0.0, 0, 0, 0.0
        if category == "Strength":
            sets, reps = c1.number_input("Sets", 0), c2.number_input("Reps", 0)
        elif category == "Static":
            dur, sets, reps = (
                c1.number_input("Duration (min)", 0.0, step=0.1),
                c2.number_input("Sets", 0),
                c3.number_input("Reps", 0),
            )
        elif category == "Cardio":
            dur, dist = (
                c1.number_input("Duration (min)", 0.0, step=0.1),
                c2.number_input("Distance (mi)", 0.0, step=0.1),
            )
        if st.form_submit_button("Save Activity"):
            if ex_name:
                act_data = {
                    "date": str(ex_date),
                    "exercise_name": ex_name,
                    "duration_min": float(dur),
                    "sets": int(sets),
                    "reps": int(reps),
                    "distance_miles": float(dist),
                    "type": category,
                }
                supabase.table("activity_logs").insert(act_data).execute()
                st.rerun()

    st.divider()
    try:
        act_res = (
            supabase.table("activity_logs")
            .select("*")
            .order("date", desc=False)
            .execute()
        )
        if act_res.data:
            df_a = pd.DataFrame(act_res.data)
            df_a["pace_min_mi"] = df_a.apply(
                lambda r: (
                    round(r["duration_min"] / r["distance_miles"], 2)
                    if r["distance_miles"] > 0
                    else None
                ),
                axis=1,
            )

            tc1, tc2 = st.columns(2)
            tc1.subheader("📈 Duration Trends")
            st.line_chart(df_a, x="date", y="duration_min")
            tc2.subheader("⏱️ Cardio Pace")
            df_c = df_a[df_a["type"] == "Cardio"].dropna(subset=["pace_min_mi"])
            if not df_c.empty:
                st.line_chart(df_c, x="date", y="pace_min_mi")

            st.subheader("📜 Activity History")
            st.dataframe(
                df_a[
                    [
                        "date",
                        "exercise_name",
                        "type",
                        "duration_min",
                        "distance_miles",
                        "pace_min_mi",
                        "sets",
                        "reps",
                    ]
                ],
                use_container_width=True,
            )
            csv_act = df_a.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Download Workout CSV", data=csv_act, file_name="workouts.csv"
            )
    except:
        pass
