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

# --- SESSION STATE FOR EDITING ---
if "edit_mode" not in st.session_state:
    st.session_state.edit_mode = None
if "edit_data" not in st.session_state:
    st.session_state.edit_data = {}


# --- ACCESS CONTROL ---
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        st.title("🔒 Dashboard Access")
        with st.form("login_form"):
            pwd = st.text_input("Enter Access Code", type="password")
            if st.form_submit_button("Login"):
                if pwd == st.secrets["ADMIN_PASSWORD"]:
                    st.session_state.authenticated, st.session_state.is_admin = (
                        True,
                        True,
                    )
                    st.rerun()
                elif pwd == st.secrets["GUEST_PASSWORD"]:
                    st.session_state.authenticated, st.session_state.is_admin = (
                        True,
                        False,
                    )
                    st.rerun()
                else:
                    st.error("Invalid Code")
        return False
    return True


if not check_password():
    st.stop()

# --- ADMIN VIEW TOGGLE ---
if st.session_state.is_admin:
    view_choice = st.sidebar.radio(
        "🔎 View Mode", ["My Data (Admin)", "Tester Data (Guest)"]
    )
    active_user = "admin" if "Admin" in view_choice else "guest"
else:
    active_user = "guest"

record_owner = "admin" if st.session_state.is_admin else "guest"

# --- TARGETS ---
TARGET_CALORIES, TARGET_PROTEIN = 1800, 160
TARGET_FAT_MAX, TARGET_FIBER_MIN = 60, 30
NC_LIMIT = 100

tab1, tab2, tab3, tab4 = st.tabs(
    ["🍴 Nutrition", "🩺 Health Metrics", "🏃 Activity", "📊 Reports"]
)

# --- TAB 1: NUTRITION ---
with tab1:
    try:
        # Get daily totals from view
        response = (
            supabase.table("daily_variance")
            .select("*")
            .eq("user_id", active_user)
            .order("date", desc=True)
            .limit(1)
            .execute()
        )
        if response.data:
            latest = response.data[0]
            st.subheader(f"Daily Status: {latest.get('date')} ({active_user.upper()})")
            c1, c2, c3, c4, c5 = st.columns(5)

            cals = float(latest.get("total_calories") or 0)
            prot = float(latest.get("total_protein") or 0)
            net_c = float(latest.get("total_net_carbs") or 0)
            fat = float(latest.get("total_fat") or 0)
            fib = float(latest.get("total_fiber") or 0)

            c1.metric("Calories", f"{int(cals)}", f"{int(TARGET_CALORIES - cals)} Left")
            c2.metric(
                "Protein", f"{int(prot)}g", f"{int(prot - TARGET_PROTEIN)}g vs Goal"
            )
            c3.metric(
                f"Net Carbs {'🟢' if net_c <= NC_LIMIT else '🔴'}",
                f"{int(net_c)}g",
                f"{int(net_c - NC_LIMIT)}g Over",
                delta_color="inverse",
            )
            c4.metric(
                f"Fat {'🟢' if fat <= TARGET_FAT_MAX else '🔴'}",
                f"{int(fat)}g",
                f"{int(TARGET_FAT_MAX - fat)}g Left",
            )
            c5.metric(
                f"Fiber {'🟢' if fib >= TARGET_FIBER_MIN else '🔴'}",
                f"{int(fib)}g",
                f"{int(fib - TARGET_FIBER_MIN)}g vs Min",
            )
    except Exception as e:
        st.error(f"Header Error: {e}")

    # QUICK LOG (FREQUENCY)
    st.divider()
    st.markdown("### ⚡ Quick Log (Frequent Items)")
    freq_res = (
        supabase.table("daily_logs")
        .select("foods(food_name, food_id)")
        .eq("user_id", active_user)
        .execute()
    )
    if freq_res.data:
        names_list = [r["foods"]["food_name"] for r in freq_res.data if r.get("foods")]
        if names_list:
            top_5 = pd.Series(names_list).value_counts().head(5).index.tolist()
            btns = st.columns(len(top_5))
            for i, name in enumerate(top_5):
                if btns[i].button(f"➕ {name}"):
                    f_id_res = (
                        supabase.table("foods")
                        .select("food_id")
                        .eq("food_name", name)
                        .limit(1)
                        .execute()
                    )
                    if f_id_res.data:
                        supabase.table("daily_logs").insert(
                            {
                                "food_id": f_id_res.data[0]["food_id"],
                                "servings": 1.0,
                                "log_date": str(datetime.now().date()),
                                "user_id": record_owner,
                            }
                        ).execute()
                        st.rerun()

    st.divider()
    st.markdown("### 🔎 Library Search")
    f_query = supabase.table("foods").select("*").order("food_name").execute()
    if f_query.data:
        f_dict = {f["food_name"]: f for f in f_query.data}
        edit_name = st.session_state.edit_data.get("food_name")
        sel = st.selectbox(
            "Select Item",
            options=list(f_dict.keys()),
            index=list(f_dict.keys()).index(edit_name) if edit_name in f_dict else None,
        )
        srv = st.number_input(
            "Servings",
            0.1,
            10.0,
            float(st.session_state.edit_data.get("servings", 1.0)),
        )

        btn_txt = (
            "Update Log Entry"
            if st.session_state.edit_mode == "nutr"
            else "Log Food Entry"
        )
        if st.button(btn_txt):
            if sel:
                f_id = f_dict[sel]["food_id"]
                payload = {
                    "food_id": f_id,
                    "servings": srv,
                    "log_date": str(datetime.now().date()),
                    "user_id": record_owner,
                }
                if st.session_state.edit_mode == "nutr":
                    supabase.table("daily_logs").update(
                        {"food_id": f_id, "servings": srv}
                    ).eq("log_id", st.session_state.edit_data["id"]).execute()
                else:
                    supabase.table("daily_logs").insert(payload).execute()
                st.session_state.edit_mode, st.session_state.edit_data = None, {}
                st.rerun()

    st.divider()
    st.subheader("🗑️ Today's Log")
    log_res = (
        supabase.table("daily_logs")
        .select("*, foods(food_name, calories)")
        .eq("log_date", str(datetime.now().date()))
        .eq("user_id", active_user)
        .execute()
    )
    if log_res.data:
        for r in log_res.data:
            l1, l2, l3, l4 = st.columns([3, 1, 0.5, 0.5])
            fname = r["foods"]["food_name"]
            l1.write(f"**{fname}**")
            l2.write(f"{int(r['foods']['calories'] * r['servings'])} kcal")
            if l3.button("📝", key=f"ed_n_{r['log_id']}"):
                st.session_state.edit_mode, st.session_state.edit_data = (
                    "nutr",
                    {"id": r["log_id"], "food_name": fname, "servings": r["servings"]},
                )
                st.rerun()
            if l4.button("🗑️", key=f"dl_n_{r['log_id']}"):
                supabase.table("daily_logs").delete().eq(
                    "log_id", r["log_id"]
                ).execute()
                st.rerun()

# --- TAB 2: HEALTH METRICS ---
with tab2:
    try:
        res = (
            supabase.table("health_metrics")
            .select("*")
            .eq("user_id", active_user)
            .order("date", desc=False)
            .execute()
        )
        df = pd.DataFrame(res.data) if res.data else pd.DataFrame()
        if not df.empty:
            df["ts"] = pd.to_datetime(
                df["date"].astype(str) + " " + df["time"].fillna("00:00:00").astype(str)
            )

            st.subheader("📊 Trends")
            bp_df = df.dropna(
                subset=["blood_pressure_systolic", "blood_pressure_diastolic"]
            )
            if not bp_df.empty:
                bp_chart = (
                    alt.Chart(bp_df)
                    .transform_fold(
                        ["blood_pressure_systolic", "blood_pressure_diastolic"]
                    )
                    .encode(
                        x="ts:T",
                        y=alt.Y("value:Q", scale=alt.Scale(zero=False)),
                        color="key:N",
                    )
                    .mark_line()
                    + alt.Chart(bp_df)
                    .transform_fold(
                        ["blood_pressure_systolic", "blood_pressure_diastolic"]
                    )
                    .encode(x="ts:T", y="value:Q", color="key:N")
                    .mark_point()
                )
                st.altair_chart(
                    bp_chart.properties(height=250), use_container_width=True
                )

        st.divider()
        st.subheader("➕ Manual Health Entries")
        ed_h = (
            st.session_state.edit_data if st.session_state.edit_mode == "health" else {}
        )
        c1, c2, c3 = st.columns(3)
        with c1:
            wv = st.number_input("Weight", 0.0, float(ed_h.get("weight_lb", 0.0)))
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
                st.session_state.edit_mode, st.session_state.edit_data = None, {}
                st.rerun()
        with c2:
            bs = st.number_input(
                "Systolic", 0, int(ed_h.get("blood_pressure_systolic", 0))
            )
            bd = st.number_input(
                "Diastolic", 0, int(ed_h.get("blood_pressure_diastolic", 0))
            )
            if st.button("Save BP"):
                d = {
                    "date": str(datetime.now().date()),
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "blood_pressure_systolic": bs,
                    "blood_pressure_diastolic": bd,
                    "user_id": record_owner,
                }
                if ed_h:
                    supabase.table("health_metrics").update(d).eq(
                        "metric_id", ed_h["metric_id"]
                    ).execute()
                else:
                    supabase.table("health_metrics").insert(d).execute()
                st.session_state.edit_mode, st.session_state.edit_data = None, {}
                st.rerun()
        with c3:
            gl = st.number_input("Glucose", 0, int(ed_h.get("blood_glucose", 0)))
            if st.button("Save Glucose"):
                d = {
                    "date": str(datetime.now().date()),
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "blood_glucose": gl,
                    "user_id": record_owner,
                }
                if ed_h:
                    supabase.table("health_metrics").update(d).eq(
                        "metric_id", ed_h["metric_id"]
                    ).execute()
                else:
                    supabase.table("health_metrics").insert(d).execute()
                st.session_state.edit_mode, st.session_state.edit_data = None, {}
                st.rerun()

        st.divider()
        st.subheader("📜 Recent Health")
        h_logs = (
            supabase.table("health_metrics")
            .select("*")
            .eq("user_id", active_user)
            .order("date", desc=True)
            .limit(5)
            .execute()
        )
        for r in h_logs.data or []:
            l1, l2, l3, l4 = st.columns([3, 1, 0.5, 0.5])
            l1.write(f"**{r['date']}** | Metrics Recorded")
            if l3.button("📝", key=f"ed_h_{r['metric_id']}"):
                st.session_state.edit_mode, st.session_state.edit_data = "health", r
                st.rerun()
            if l4.button("🗑️", key=f"dl_h_{r['metric_id']}"):
                supabase.table("health_metrics").delete().eq(
                    "metric_id", r["metric_id"]
                ).execute()
                st.rerun()
    except Exception as e:
        st.error(f"Health Error: {e}")

# --- TAB 3: ACTIVITY ---
with tab3:
    st.subheader("🏃 Activity Tracking")
    ed_a = st.session_state.edit_data if st.session_state.edit_mode == "act" else {}
    cat_list = ["Strength", "Cardio", "Endurance"]
    cur_cat = ed_a.get("activity_category", "Strength")
    cat = st.radio("Category", cat_list, horizontal=True, index=cat_list.index(cur_cat))

    with st.form("act_form"):
        name = st.text_input("Exercise", value=ed_a.get("exercise_name", ""))
        c1, c2, c3, c4, c5 = st.columns(5)
        s = c1.number_input("Sets", 0, int(ed_a.get("sets", 0)))
        r = c2.number_input("Reps", 0, int(ed_a.get("reps", 0)))
        w = c3.number_input("Weight", 0, int(ed_a.get("weight_lb", 0)))
        du = c4.number_input("Mins", 0, int(ed_a.get("duration_min", 0)))
        di = c5.number_input("Miles", 0.0, float(ed_a.get("distance_miles", 0.0)))

        if st.form_submit_button("Update Activity" if ed_a else "Log Activity"):
            d = {
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
                supabase.table("activity_logs").update(d).eq(
                    "activity_id", ed_a["activity_id"]
                ).execute()
            else:
                supabase.table("activity_logs").insert(d).execute()
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
    )
    for r in a_logs.data or []:
        l1, l2, l3, l4 = st.columns([3, 1, 0.5, 0.5])
        l1.write(f"**{r['log_date']}**: {r['exercise_name']}")
        if l3.button("📝", key=f"ed_a_{r['activity_id']}"):
            st.session_state.edit_mode, st.session_state.edit_data = "act", r
            st.rerun()
        if l4.button("🗑️", key=f"dl_a_{r['activity_id']}"):
            supabase.table("activity_logs").delete().eq(
                "activity_id", r["activity_id"]
            ).execute()
            st.rerun()

# --- TAB 4: REPORTS ---
with tab4:
    st.subheader("📊 Master Table Viewer")
    tbl = st.selectbox(
        "Select Table", ["health_metrics", "activity_logs", "daily_logs", "foods"]
    )
    id_map = {
        "health_metrics": "metric_id",
        "activity_logs": "activity_id",
        "daily_logs": "log_id",
        "foods": "food_id",
    }
    sort_key = id_map.get(tbl, "created_at")

    try:
        q = supabase.table(tbl).select("*")
        if tbl != "foods":
            q = q.eq("user_id", active_user)
        res = q.order(sort_key, desc=True).limit(100).execute()
        if res.data:
            df_master = pd.DataFrame(res.data)
            st.dataframe(df_master, use_container_width=True)
            # Master Export Logic fixed inside the try block
            st.download_button(
                "📥 Export Current View to CSV",
                data=df_master.to_csv(index=False).encode("utf-8"),
                file_name=f"{tbl}_export.csv",
                mime="text/csv",
            )
    except Exception as e:
        st.error(f"Table Error: {e}")
