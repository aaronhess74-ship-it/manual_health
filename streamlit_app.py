import streamlit as st
from supabase import create_client
from datetime import datetime
import pandas as pd
import altair as alt

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
    st.title("🔒 Private Access")
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

# --- USER SCOPING ---
active_user = (
    "admin"
    if (
        st.session_state.is_admin
        and st.sidebar.radio("View Mode", ["Admin", "Guest"]) == "Admin"
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
            # Goals based on your earlier requirements
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
                f"Net Carbs {'🟢' if (d['total_net_carbs'] or 0) <= 100 else '🔴'}",
                f"{int(d['total_net_carbs'] or 0)}g",
                f"{int((d['total_net_carbs'] or 0) - 100)}g Over",
                delta_color="inverse",
            )
            c4.metric(
                f"Fat {'🟢' if (d['total_fat'] or 0) <= 60 else '🔴'}",
                f"{int(d['total_fat'] or 0)}g",
                f"{int(60 - (d['total_fat'] or 0))}g Left",
            )
            c5.metric(
                f"Fiber {'🟢' if (d['total_fiber'] or 0) >= 30 else '🔴'}",
                f"{int(d['total_fiber'] or 0)}g",
                f"{int((d['total_fiber'] or 0) - 30)}g vs Min",
            )
    except:
        st.info("Welcome! Log your first item for today.")

    # Quick Log (Frequency)
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
                        }
                    ).execute()
                    st.rerun()

    # Log/Edit Form
    st.divider()
    ed_n = st.session_state.edit_data if st.session_state.edit_mode == "nutr" else {}
    f_all = supabase.table("foods").select("*").order("food_name").execute().data
    if f_all:
        f_map = {x["food_name"]: x for x in f_all}
        c_sel, c_srv, c_btn = st.columns([3, 1, 1])
        with c_sel:
            sel_f = st.selectbox(
                "Food Item",
                options=list(f_map.keys()),
                index=list(f_map.keys()).index(ed_n.get("food_name"))
                if ed_n.get("food_name") in f_map
                else 0,
            )
        with c_srv:
            srv_f = st.number_input(
                "Servings", 0.1, 10.0, float(ed_n.get("servings", 1.0))
            )
        with c_btn:
            st.write("")  # Spacer
            if st.button("Update Log" if ed_n else "Add to Log"):
                payload = {
                    "food_id": f_map[sel_f]["food_id"],
                    "servings": srv_f,
                    "log_date": str(datetime.now().date()),
                    "user_id": record_owner,
                }
                if ed_n:
                    supabase.table("daily_logs").update(payload).eq(
                        "log_id", ed_n["log_id"]
                    ).execute()
                else:
                    supabase.table("daily_logs").insert(payload).execute()
                st.session_state.update({"edit_mode": None, "edit_data": {}})
                st.rerun()
            if ed_n and st.button("Cancel"):
                st.session_state.update({"edit_mode": None, "edit_data": {}})
                st.rerun()

    # Daily History
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
        lc1.write(f"**{r['foods']['food_name']}**")
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
        st.subheader("📊 Trends")
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

    st.divider()
    ed_h = st.session_state.edit_data if st.session_state.edit_mode == "health" else {}
    hc1, hc2, hc3 = st.columns(3)
    with hc1:
        wv = st.number_input("Weight (lb)", 0.0, float(ed_h.get("weight_lb", 0.0)))
        if st.button("Save Weight"):
            d = {
                "date": str(datetime.now().date()),
                "time": datetime.now().strftime("%H:%M:%S"),
                "weight_lb": wv,
                "user_id": record_owner,
            }
            if ed_h:
                supabase.table("health_metrics").update(d).eq(
                    "metric_id", ed_h["metric_id"]
                ).execute()
            else:
                supabase.table("health_metrics").insert(d).execute()
            st.session_state.update({"edit_mode": None, "edit_data": {}})
            st.rerun()
    with hc2:
        sys = st.number_input(
            "Systolic", 0, int(ed_h.get("blood_pressure_systolic", 0))
        )
        dia = st.number_input(
            "Diastolic", 0, int(ed_h.get("blood_pressure_diastolic", 0))
        )
        if st.button("Save BP"):
            d = {
                "date": str(datetime.now().date()),
                "time": datetime.now().strftime("%H:%M:%S"),
                "blood_pressure_systolic": sys,
                "blood_pressure_diastolic": dia,
                "user_id": record_owner,
            }
            if ed_h:
                supabase.table("health_metrics").update(d).eq(
                    "metric_id", ed_h["metric_id"]
                ).execute()
            else:
                supabase.table("health_metrics").insert(d).execute()
            st.session_state.update({"edit_mode": None, "edit_data": {}})
            st.rerun()
    with hc3:
        glu = st.number_input("Glucose", 0.0, float(ed_h.get("blood_glucose", 0.0)))
        if st.button("Save Glucose"):
            d = {
                "date": str(datetime.now().date()),
                "time": datetime.now().strftime("%H:%M:%S"),
                "blood_glucose": glu,
                "user_id": record_owner,
            }
            if ed_h:
                supabase.table("health_metrics").update(d).eq(
                    "metric_id", ed_h["metric_id"]
                ).execute()
            else:
                supabase.table("health_metrics").insert(d).execute()
            st.session_state.update({"edit_mode": None, "edit_data": {}})
            st.rerun()

    st.divider()
    for rh in h_data[::-1][:5] if h_data else []:
        r1, r2, r3, r4 = st.columns([3, 1, 0.5, 0.5])
        r1.write(
            f"**{rh['date']}** | Weight: {rh['weight_lb']} | BP: {rh['blood_pressure_systolic']}/{rh['blood_pressure_diastolic']}"
        )
        if r3.button("📝", key=f"eh_{rh['metric_id']}"):
            st.session_state.update({"edit_mode": "health", "edit_data": rh})
            st.rerun()
        if r4.button("🗑️", key=f"dh_{rh['metric_id']}"):
            supabase.table("health_metrics").delete().eq(
                "metric_id", rh["metric_id"]
            ).execute()
            st.rerun()

# --- TAB 3: ACTIVITY ---
with tab3:
    st.subheader("🏃 Training Log")
    ed_a = st.session_state.edit_data if st.session_state.edit_mode == "act" else {}
    c_list = ["Strength", "Cardio", "Endurance"]
    cat = st.radio(
        "Category",
        c_list,
        horizontal=True,
        index=c_list.index(ed_a.get("activity_category", "Strength")),
    )

    with st.form("act_form"):
        name = st.text_input("Exercise", value=ed_a.get("exercise_name", ""))
        a1, a2, a3, a4, a5 = st.columns(5)
        se = a1.number_input("Sets", 0, int(ed_a.get("sets", 0)))
        re = a2.number_input("Reps", 0, int(ed_a.get("reps", 0)))
        we = a3.number_input("Lbs", 0, int(ed_a.get("weight_lb", 0)))
        du = a4.number_input("Min", 0, int(ed_a.get("duration_min", 0)))
        di = a5.number_input("Miles", 0.0, float(ed_a.get("distance_miles", 0.0)))
        if st.form_submit_button("Save Activity"):
            p = {
                "log_date": str(datetime.now().date()),
                "exercise_name": name,
                "activity_category": cat,
                "sets": se,
                "reps": re,
                "weight_lb": we,
                "duration_min": du,
                "distance_miles": di,
                "user_id": record_owner,
            }
            if ed_a:
                supabase.table("activity_logs").update(p).eq("id", ed_a["id"]).execute()
            else:
                supabase.table("activity_logs").insert(p).execute()
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
        al1.write(f"**{ra['log_date']}**: {ra['exercise_name']}")
        if al3.button("📝", key=f"ea_{ra['id']}"):
            st.session_state.update({"edit_mode": "act", "edit_data": ra})
            st.rerun()
        if al4.button("🗑️", key=f"da_{ra['id']}"):
            supabase.table("activity_logs").delete().eq("id", ra["id"]).execute()
            st.rerun()

# --- TAB 4: REPORTS ---
with tab4:
    tbl = st.selectbox(
        "Select Table", ["health_metrics", "activity_logs", "daily_logs", "foods"]
    )
    q = supabase.table(tbl).select("*")
    if tbl != "foods":
        q = q.eq("user_id", active_user)
    m_data = q.limit(100).execute().data
    if m_data:
        df_m = pd.DataFrame(m_data)
        st.dataframe(df_m, use_container_width=True)
        st.download_button(
            "📥 Export CSV", df_m.to_csv(index=False).encode("utf-8"), f"{tbl}.csv"
        )
