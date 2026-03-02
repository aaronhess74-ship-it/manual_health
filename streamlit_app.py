import streamlit as st
from supabase import create_client
from datetime import datetime
import pandas as pd
import altair as alt

# 1. Setup Connection
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.set_page_config(
    page_title="Health Dashboard Pro", layout="wide", initial_sidebar_state="collapsed"
)

# --- SESSION STATE ---
if "edit_mode" not in st.session_state:
    st.session_state.edit_mode = None
if "edit_data" not in st.session_state:
    st.session_state.edit_data = {}

# --- ACCESS CONTROL ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if not st.session_state.authenticated:
    st.title("🔒 Dashboard Access")
    with st.form("login"):
        pwd = st.text_input("Enter Access Code", type="password")
        if st.form_submit_button("Login"):
            if pwd == st.secrets["ADMIN_PASSWORD"]:
                st.session_state.authenticated, st.session_state.is_admin = True, True
                st.rerun()
            elif pwd == st.secrets["GUEST_PASSWORD"]:
                st.session_state.authenticated, st.session_state.is_admin = True, False
                st.rerun()
    st.stop()

# --- DATA SCOPING ---
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


# --- UNIVERSAL ID HELPER ---
def get_id_info(obj):
    """Finds the ID column name and value dynamically to prevent KeyError."""
    for k in ["log_id", "metric_id", "activity_id", "food_id", "id"]:
        if k in obj:
            return k, obj[k]
    return None, None


tab1, tab2, tab3, tab4 = st.tabs(
    ["🍴 Nutrition", "🩺 Health Metrics", "🏃 Activity", "📊 Reports"]
)

# --- TAB 1: NUTRITION ---
with tab1:
    try:
        res = (
            supabase.table("daily_variance")
            .select("*")
            .eq("user_id", active_user)
            .order("date", desc=True)
            .limit(1)
            .execute()
        )
        if res.data:
            d = res.data[0]
            st.subheader(f"Daily Status: {d.get('date')} ({active_user.upper()})")
            c1, c2, c3, c4, c5 = st.columns(5)

            cals, prot = (
                float(d.get("total_calories") or 0),
                float(d.get("total_protein") or 0),
            )
            nc, fat, fib = (
                float(d.get("total_net_carbs") or 0),
                float(d.get("total_fat") or 0),
                float(d.get("total_fiber") or 0),
            )

            c1.metric("Calories", f"{int(cals)}", f"{int(1800 - cals)} Left")
            c2.metric("Protein", f"{int(prot)}g", f"{int(prot - 160)}g vs Goal")
            c3.metric(
                f"Net Carbs {'🟢' if nc <= 100 else '🔴'}",
                f"{int(nc)}g",
                f"{int(nc - 100)}g Over",
                delta_color="inverse",
            )
            c4.metric(
                f"Fat {'🟢' if fat <= 60 else '🔴'}",
                f"{int(fat)}g",
                f"{int(60 - fat)}g Left",
            )
            c5.metric(
                f"Fiber {'🟢' if fib >= 30 else '🔴'}",
                f"{int(fib)}g",
                f"{int(fib - 30)}g vs Min",
            )
    except:
        st.warning("Nutrition totals temporarily unavailable.")

    # QUICK LOG (FREQUENCY)
    st.divider()
    st.markdown("### ⚡ Quick Log (Frequent Items)")
    f_res = (
        supabase.table("daily_logs")
        .select("foods(food_name, food_id)")
        .eq("user_id", active_user)
        .execute()
    )
    if f_res.data:
        names = [r["foods"]["food_name"] for r in f_res.data if r.get("foods")]
        if names:
            top_5 = pd.Series(names).value_counts().head(5).index.tolist()
            btns = st.columns(len(top_5))
            for i, name in enumerate(top_5):
                if btns[i].button(f"➕ {name}"):
                    fid_res = (
                        supabase.table("foods")
                        .select("food_id")
                        .eq("food_name", name)
                        .limit(1)
                        .execute()
                    )
                    if fid_res.data:
                        supabase.table("daily_logs").insert(
                            {
                                "food_id": fid_res.data[0]["food_id"],
                                "servings": 1.0,
                                "log_date": str(datetime.now().date()),
                                "user_id": record_owner,
                            }
                        ).execute()
                        st.rerun()

    st.divider()
    # SEARCH & EDIT
    col_search, col_cancel = st.columns([4, 1])
    with col_search:
        st.markdown("### 🔎 Library Search")
        f_list = supabase.table("foods").select("*").order("food_name").execute().data
        if f_list:
            f_dict = {f["food_name"]: f for f in f_list}
            ed_n = (
                st.session_state.edit_data
                if st.session_state.edit_mode == "nutr"
                else {}
            )
            sel = st.selectbox(
                "Select Food Item",
                options=list(f_dict.keys()),
                index=list(f_dict.keys()).index(ed_n.get("food_name"))
                if ed_n.get("food_name") in f_dict
                else None,
            )
            srv = st.number_input(
                "Servings", 0.1, 10.0, float(ed_n.get("servings", 1.0))
            )

            if st.button("Update Log Entry" if ed_n else "Log Food Entry"):
                payload = {
                    "food_id": f_dict[sel]["food_id"],
                    "servings": srv,
                    "log_date": str(datetime.now().date()),
                    "user_id": record_owner,
                }
                if ed_n:
                    id_col, id_val = get_id_info(ed_n)
                    supabase.table("daily_logs").update(payload).eq(
                        id_col, id_val
                    ).execute()
                else:
                    supabase.table("daily_logs").insert(payload).execute()
                st.session_state.edit_mode, st.session_state.edit_data = None, {}
                st.rerun()
    with col_cancel:
        if st.session_state.edit_mode:
            st.write("")  # Spacer
            if st.button("❌ Cancel Edit"):
                st.session_state.edit_mode, st.session_state.edit_data = None, {}
                st.rerun()

    st.divider()
    st.subheader("🗑️ Today's Log")
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
        fname = r["foods"]["food_name"]
        lc1.write(f"**{fname}**")
        lc2.write(f"{int(r['foods']['calories'] * r['servings'])} kcal")
        id_col, id_val = get_id_info(r)
        if lc3.button("📝", key=f"ed_n_{id_val}"):
            st.session_state.edit_mode, st.session_state.edit_data = (
                "nutr",
                {"id": id_val, "food_name": fname, "servings": r["servings"]},
            )
            st.rerun()
        if lc4.button("🗑️", key=f"dl_n_{id_val}"):
            supabase.table("daily_logs").delete().eq(id_col, id_val).execute()
            st.rerun()

# --- TAB 2: HEALTH METRICS ---
with tab2:
    try:
        h_res = (
            supabase.table("health_metrics")
            .select("*")
            .eq("user_id", active_user)
            .order("date", desc=False)
            .execute()
            .data
        )
        if h_res:
            df = pd.DataFrame(h_res)
            df["ts"] = pd.to_datetime(
                df["date"].astype(str) + " " + df["time"].fillna("00:00:00").astype(str)
            )

            st.subheader("📊 Blood Pressure Trend")
            bp_df = df.dropna(
                subset=["blood_pressure_systolic", "blood_pressure_diastolic"]
            )
            if not bp_df.empty:
                chart = (
                    alt.Chart(bp_df)
                    .transform_fold(
                        ["blood_pressure_systolic", "blood_pressure_diastolic"],
                        as_=["Metric", "Value"],
                    )
                    .encode(
                        x="ts:T",
                        y=alt.Y("Value:Q", scale=alt.Scale(zero=False)),
                        color="Metric:N",
                    )
                    .mark_line()
                    + alt.Chart(bp_df)
                    .transform_fold(
                        ["blood_pressure_systolic", "blood_pressure_diastolic"],
                        as_=["Metric", "Value"],
                    )
                    .encode(x="ts:T", y="Value:Q", color="Metric:N")
                    .mark_point()
                )
                st.altair_chart(chart.properties(height=250), use_container_width=True)
    except:
        st.info("Logged data needed for trends.")

    st.divider()
    st.subheader("➕ Manual Health Entries")
    ed_h = st.session_state.edit_data if st.session_state.edit_mode == "health" else {}
    hc1, hc2, hc3 = st.columns(3)
    with hc1:
        wv = st.number_input("Weight Lbs", 0.0, float(ed_h.get("weight_lb", 0.0)))
        if st.button("Save Weight"):
            d = {
                "date": str(datetime.now().date()),
                "time": datetime.now().strftime("%H:%M:%S"),
                "weight_lb": wv,
                "user_id": record_owner,
            }
            if ed_h:
                id_col, id_val = get_id_info(ed_h)
                supabase.table("health_metrics").update(d).eq(id_col, id_val).execute()
            else:
                supabase.table("health_metrics").insert(d).execute()
            st.session_state.edit_mode, st.session_state.edit_data = None, {}
            st.rerun()
    with hc2:
        sys = st.number_input(
            "Systolic", 0, int(ed_h.get("blood_pressure_systolic", 0))
        )
        dia = st.number_input(
            "Diastolic", 0, int(ed_h.get("blood_pressure_diastolic", 0))
        )
        if st.button("Save Blood Pressure"):
            d = {
                "date": str(datetime.now().date()),
                "time": datetime.now().strftime("%H:%M:%S"),
                "blood_pressure_systolic": sys,
                "blood_pressure_diastolic": dia,
                "user_id": record_owner,
            }
            if ed_h:
                id_col, id_val = get_id_info(ed_h)
                supabase.table("health_metrics").update(d).eq(id_col, id_val).execute()
            else:
                supabase.table("health_metrics").insert(d).execute()
            st.session_state.edit_mode, st.session_state.edit_data = None, {}
            st.rerun()
    with hc3:
        gl = st.number_input("Glucose mg/dL", 0, int(ed_h.get("blood_glucose", 0)))
        if st.button("Save Glucose"):
            d = {
                "date": str(datetime.now().date()),
                "time": datetime.now().strftime("%H:%M:%S"),
                "blood_glucose": gl,
                "user_id": record_owner,
            }
            if ed_h:
                id_col, id_val = get_id_info(ed_h)
                supabase.table("health_metrics").update(d).eq(id_col, id_val).execute()
            else:
                supabase.table("health_metrics").insert(d).execute()
            st.session_state.edit_mode, st.session_state.edit_data = None, {}
            st.rerun()

    st.divider()
    st.subheader("📜 Recent Health Logs")
    h_logs = (
        supabase.table("health_metrics")
        .select("*")
        .eq("user_id", active_user)
        .order("date", desc=True)
        .limit(5)
        .execute()
        .data
    )
    for r in h_logs or []:
        l1, l2, l3, l4 = st.columns([3, 1, 0.5, 0.5])
        l1.write(f"**{r['date']}** | Metrics Recorded")
        id_col, id_val = get_id_info(r)
        if l3.button("📝", key=f"ed_h_{id_val}"):
            st.session_state.edit_mode, st.session_state.edit_data = "health", r
            st.rerun()
        if l4.button("🗑️", key=f"dl_h_{id_val}"):
            supabase.table("health_metrics").delete().eq(id_col, id_val).execute()
            st.rerun()

# --- TAB 3: ACTIVITY ---
with tab3:
    st.subheader("🏃 Activity Tracking")
    ed_a = st.session_state.edit_data if st.session_state.edit_mode == "act" else {}
    cat_list = ["Strength", "Cardio", "Endurance"]
    cat = st.radio(
        "Category",
        cat_list,
        horizontal=True,
        index=cat_list.index(ed_a.get("activity_category", "Strength")),
    )

    with st.form("act_form"):
        name = st.text_input("Exercise Name", value=ed_a.get("exercise_name", ""))
        ac1, ac2, ac3, ac4, ac5 = st.columns(5)
        s = ac1.number_input("Sets", 0, int(ed_a.get("sets", 0)))
        r = ac2.number_input("Reps", 0, int(ed_a.get("reps", 0)))
        w = ac3.number_input("Weight Lbs", 0, int(ed_a.get("weight_lb", 0)))
        du = ac4.number_input("Duration (min)", 0, int(ed_a.get("duration_min", 0)))
        di = ac5.number_input(
            "Distance (miles)", 0.0, float(ed_a.get("distance_miles", 0.0))
        )

        if st.form_submit_button("Update Activity" if ed_a else "Log Activity"):
            p = {
                "log_date": str(datetime.now().date()),
                "exercise_name": name,
                "activity_category": cat,
                "sets": s,
                "reps": r,
                "weight_lb": w,
                "duration_min": du,
                "distance_miles": di,
                "user_id": record_owner,
            }
            if ed_a:
                id_col, id_val = get_id_info(ed_a)
                supabase.table("activity_logs").update(p).eq(id_col, id_val).execute()
            else:
                supabase.table("activity_logs").insert(p).execute()
            st.session_state.edit_mode, st.session_state.edit_data = None, {}
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
    for r in a_logs or []:
        al1, al2, al3, al4 = st.columns([3, 1, 0.5, 0.5])
        al1.write(
            f"**{r['log_date']}**: {r['exercise_name']} ({r['activity_category']})"
        )
        id_col, id_val = get_id_info(r)
        if al3.button("📝", key=f"ed_a_{id_val}"):
            st.session_state.edit_mode, st.session_state.edit_data = "act", r
            st.rerun()
        if al4.button("🗑️", key=f"dl_a_{id_val}"):
            supabase.table("activity_logs").delete().eq(id_col, id_val).execute()
            st.rerun()

# --- TAB 4: REPORTS ---
with tab4:
    st.subheader("📊 Master Table Viewer")
    tbl = st.selectbox(
        "Select Table", ["health_metrics", "activity_logs", "daily_logs", "foods"]
    )
    q = supabase.table(tbl).select("*")
    if tbl != "foods":
        q = q.eq("user_id", active_user)

    # Sort by ID column if found, else just execute
    id_col, _ = get_id_info(
        {"log_id": 1, "metric_id": 1, "activity_id": 1, "food_id": 1, "id": 1}
    )  # Dummy to get priority
    res = q.limit(100).execute().data
    if res:
        df_m = pd.DataFrame(res)
        st.dataframe(df_m, use_container_width=True)
        st.download_button(
            f"📥 Export {tbl.replace('_', ' ').title()} CSV",
            data=df_m.to_csv(index=False).encode("utf-8"),
            file_name=f"{tbl}_export.csv",
            mime="text/csv",
        )
