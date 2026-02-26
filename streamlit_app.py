import streamlit as st
from supabase import create_client
from datetime import datetime
import pandas as pd

# 1. Setup Connection
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.set_page_config(page_title="Health Dashboard", layout="wide")
st.title("💪 My Health Dashboard")

# --- TARGET CONSTANTS ---
TARGET_CALORIES = 1800
TARGET_PROTEIN = 160
TARGET_FAT_MAX = 60
TARGET_NET_CARBS = 60
TARGET_FIBER_MIN = 30

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

            # Ensure we are working with floats/ints
            cals = float(latest.get("total_calories", 0))
            prot = float(latest.get("total_protein", 0))
            net_c = float(latest.get("total_net_carbs", 0))
            fat = float(latest.get("total_fat", 0))
            fib = float(latest.get("total_fiber", 0))

            # 1. Calories (Ceiling: 1800)
            # Logic: If > 1800 (Inverse/Red). If 1620-1800 (Off/Yellow). Else (Normal/Green).
            cal_delta = TARGET_CALORIES - cals
            cal_color = "normal"
            if cals > TARGET_CALORIES:
                cal_color = "inverse"
            elif cals >= (TARGET_CALORIES * 0.90):
                cal_color = "off"
            c1.metric(
                "Calories",
                f"{int(cals)}",
                f"{int(cal_delta)} Left",
                delta_color=cal_color,
            )

            # 2. Protein (Floor: 160)
            # Logic: If >= 160 (Normal/Green). If 144-159 (Off/Yellow). Else (Inverse/Red).
            prot_delta = prot - TARGET_PROTEIN
            prot_color = "normal"
            if prot < (TARGET_PROTEIN * 0.90):
                prot_color = "inverse"
            elif prot < TARGET_PROTEIN:
                prot_color = "off"
            c2.metric(
                "Protein",
                f"{int(prot)}g",
                f"{int(prot_delta)} vs Target",
                delta_color=prot_color,
            )

            # 3. Net Carbs (Ceiling: 60)
            carb_delta = TARGET_NET_CARBS - net_c
            carb_color = "normal"
            if net_c > TARGET_NET_CARBS:
                carb_color = "inverse"
            elif net_c >= (TARGET_NET_CARBS * 0.90):
                carb_color = "off"
            c3.metric(
                "Net Carbs",
                f"{int(net_c)}g",
                f"{int(carb_delta)} Left",
                delta_color=carb_color,
            )

            # 4. Total Fat (Ceiling: 60)
            fat_delta = TARGET_FAT_MAX - fat
            fat_color = "normal"
            if fat > TARGET_FAT_MAX:
                fat_color = "inverse"
            elif fat >= (TARGET_FAT_MAX * 0.90):
                fat_color = "off"
            c4.metric(
                "Total Fat",
                f"{int(fat)}g",
                f"{int(fat_delta)} Left",
                delta_color=fat_color,
            )

            # 5. Fiber (Floor: 30)
            fib_delta = fib - TARGET_FIBER_MIN
            fib_color = "normal"
            if fib < (TARGET_FIBER_MIN * 0.90):
                fib_color = "inverse"
            elif fib < TARGET_FIBER_MIN:
                fib_color = "off"
            c5.metric(
                "Fiber",
                f"{int(fib)}g",
                f"{int(fib_delta)} vs Target",
                delta_color=fib_color,
            )
    except Exception as e:
        st.error(f"Display Error: {e}")

    st.divider()
    st.subheader("⚡ Quick Log")
    try:
        recent = (
            supabase.table("daily_logs")
            .select("food_id, foods(food_name)")
            .order("log_id", desc=True)
            .limit(20)
            .execute()
        )
        if recent.data:
            seen, quick_foods = set(), []
            for r in recent.data:
                fid, fname = r["food_id"], r["foods"]["food_name"]
                if fid not in seen:
                    quick_foods.append({"id": fid, "name": fname})
                    seen.add(fid)
                if len(quick_foods) == 5:
                    break
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
            sel = st.selectbox("Search...", options=list(f_dict.keys()), index=None)
            if sel:
                food = f_dict[sel]
                if food.get("fat_g") is None or pd.isna(food.get("fat_g")):
                    st.info(f"Adding missing macros for {sel}")
                    u_fat = st.number_input("Fat", 0.0)
                    u_fib = st.number_input("Fiber", 0.0)
                    if st.button("Update & Log"):
                        supabase.table("foods").update(
                            {"fat_g": u_fat, "fiber_g": u_fib}
                        ).eq("food_id", food["food_id"]).execute()
                        supabase.table("daily_logs").insert(
                            {
                                "food_id": food["food_id"],
                                "servings": 1.0,
                                "log_date": str(datetime.now().date()),
                            }
                        ).execute()
                        st.rerun()
                else:
                    srv = st.number_input("Servings", 0.1, 10.0, value=1.0, step=0.1)
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
            c_f, c_fi = st.columns(2)
            nf, nfi = c_f.number_input("Fat", 0), c_fi.number_input("Fib", 0)
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
with tab2:
    try:
        last_v = (
            supabase.table("health_metrics")
            .select("*")
            .order("date", desc=True)
            .limit(1)
            .execute()
        )
        if last_v.data:
            v = last_v.data[0]
            m1, m2, m3 = st.columns(3)
            m1.metric(
                "BP",
                f"{int(v['blood_pressure_systolic'])}/{int(v['blood_pressure_diastolic'])}",
            )
            m2.metric("Glucose", f"{v['blood_glucose']}")
            m3.metric("Weight", f"{v['weight_lb']} lbs")
    except:
        pass
    with st.expander("Log Vitals"):
        with st.form("v_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            sys, dia = c1.number_input("Sys", 120), c2.number_input("Dia", 80)
            weight, glu = c3.number_input("Wt", 180.0), st.number_input("Glu", 100)
            if st.form_submit_button("Save"):
                supabase.table("health_metrics").insert(
                    {
                        "date": str(datetime.now().date()),
                        "blood_pressure_systolic": sys,
                        "blood_pressure_diastolic": dia,
                        "blood_glucose": glu,
                        "weight_lb": weight,
                    }
                ).execute()
                st.rerun()

# --- TAB 3: ACTIVITY TRACKER ---
with tab3:
    cat = st.radio("Type:", ["Strength", "Static", "Cardio"], horizontal=True)
    with st.form("act_form", clear_on_submit=True):
        name = st.text_input("Exercise Name")
        c1, c2 = st.columns(2)
        dur, dist, sets, reps = 0.0, 0.0, 0, 0
        if cat == "Cardio":
            dur, dist = c1.number_input("Min", 0.0), c2.number_input("Mi", 0.0)
        else:
            sets, reps = c1.number_input("Sets", 0), c2.number_input("Reps", 0)
            if cat == "Static":
                dur = st.number_input("Min", 0.0)
        if st.form_submit_button("Log Activity"):
            supabase.table("activity_logs").insert(
                {
                    "date": str(datetime.now().date()),
                    "exercise_name": name,
                    "duration_min": dur,
                    "distance_miles": dist,
                    "sets": sets,
                    "reps": reps,
                    "type": cat,
                }
            ).execute()
            st.rerun()
    st.divider()
    a_res = (
        supabase.table("activity_logs").select("*").order("date", desc=False).execute()
    )
    if a_res.data:
        df_a = pd.DataFrame(a_res.data)
        df_a["pace"] = df_a.apply(
            lambda r: (
                round(r["duration_min"] / r["distance_miles"], 2)
                if r["distance_miles"] > 0
                else None
            ),
            axis=1,
        )
        st.subheader("Duration Trends")
        st.line_chart(df_a, x="date", y="duration_min")
        df_c = df_a[df_a["type"] == "Cardio"].dropna(subset=["pace"])
        if not df_c.empty:
            st.subheader("Cardio Pace")
            st.line_chart(df_c, x="date", y="pace")
        st.dataframe(df_a)
