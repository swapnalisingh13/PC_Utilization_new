import streamlit as st
import requests
import mysql.connector
import pandas as pd
import plotly.express as px
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, ListFlowable, ListItem
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import matplotlib.pyplot as plt
import io
import datetime as dt 
import pandas as pd

#same as app1 in backup when created or when all the parts are last time working correct
#added logic of slatest static data retrival and update static instead of everyday to once when start up

#added logic of report button 
#added and solved bugs, formatted the reports-pdf's also. 
#added employee record section.

# -------------------- MySQL CONFIG --------------------
DB_CONFIG = {
    'host': 'srv1674.hstgr.io',   # On Hostinger, keep "localhost"
    'user': 'u221987201_hpa_root',
    'password': 'Root@303',
    'database': 'u221987201_hpa_pc'
}
# -------------------- LOGIN ENDPOINT --------------------
#LOGIN_ENDPOINT = "http://127.0.0.1:5000/login"
#onlyt the bottom for when the server is active in the deployment pc
LOGIN_ENDPOINT = "http://192.168.0.221:6060/login"
# -------------------- SESSION STATE --------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "role" not in st.session_state:
    st.session_state.role = ""
if "page" not in st.session_state:
    st.session_state.page = "Homepage"
if "show_report_options" not in st.session_state:
    st.session_state.show_report_options = False

# -------------------- DB CONNECTION --------------------
def get_connection():
    return mysql.connector.connect(**DB_CONFIG)

# -------------------- LOGIN PAGE --------------------
def show_login():
    st.title("🖥️ HPA - Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        try:
            response = requests.post(
                LOGIN_ENDPOINT,
                json={"username": username, "password": password},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.role = data["role"]
                    st.success(f"✅ Logged in as {username} ({data['role']})")
                    st.rerun()
                else:
                    st.error("❌ Invalid username or password")
            else:
                st.error(f"⚠️ Server error {response.status_code}")
        except Exception as e:
            st.error(f"⚠️ Error: {e}")

# -------------------- FETCH EMPLOYEE DATA (Dynamic only) --------------------
def fetch_dynamic_data(date_filter=None):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT e.emp_id, e.name, e.pc_number, d.record_timestamp,
               d.cpu_utilization_percent, d.gpu_utilization_percent, d.ram_utilization_percent,
               d.disk_usage_percent, d.ethernet_utilization_percent,
               d.top_cpu_process, d.top_gpu_process, d.top_ram_process 
        FROM Employee e
        JOIN Dynamic_Data d ON e.pc_number = d.pc_name
    """
    params = []
    if date_filter:
        query += " WHERE DATE(d.record_timestamp) = %s"
        params.append(date_filter.strftime("%Y-%m-%d"))

    try:
        cursor.execute(query, params)
        rows = cursor.fetchall()
    except Exception:
        rows = []
    finally:
        conn.close()

    df = pd.DataFrame(rows)
    if not df.empty and "record_timestamp" in df.columns:
        df["record_timestamp"] = pd.to_datetime(df["record_timestamp"], errors="coerce")
    return df

# -------------------- FETCH STATIC DATA --------------------
def fetch_employee_static():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT s.pc_name, s.cpu_model, s.ram_size_gb, s.ip_address, s.bios_version
        FROM Static_Data s
        INNER JOIN (
            SELECT pc_name, MAX(record_date) AS latest_date
            FROM Static_Data
            GROUP BY pc_name
        ) t ON s.pc_name = t.pc_name AND s.record_date = t.latest_date
    """

    try:
        cursor.execute(query)
        rows = cursor.fetchall()
    except Exception:
        rows = []
    finally:
        conn.close()

    return pd.DataFrame(rows)

# -------------------- SAFE PLOT FUNCTION --------------------
# -------------------- SAFE PLOT FUNCTION --------------------
def safe_plot_line(emp_df, y_col, hover_col, title, y_label, height=300):
    """Plot a safe Plotly line chart if data exists; otherwise do nothing and return False."""
    if emp_df is None or emp_df.empty:
        return False
    if y_col not in emp_df.columns:
        return False
    vals = pd.to_numeric(emp_df[y_col], errors="coerce")
    valid_mask = vals.notna()
    plot_df = emp_df.loc[valid_mask].copy()
    if plot_df.empty:
        return False

    hover_vals = None
    if hover_col and hover_col in plot_df.columns:
        hover_vals = plot_df[hover_col].fillna("N/A").replace("", "N/A").astype(str).values

    fig = px.line(
        plot_df,
        x="record_timestamp",
        y=y_col,
        markers=True,
        title=title,
        labels={y_col: y_label, "record_timestamp": "Time"},
        hover_data={y_col: True, "record_timestamp": True}
    )
    if hover_vals is not None:
        fig.update_traces(
            customdata=hover_vals,
            hovertemplate="<b>%{customdata}</b><br>Time: %{x}<br>Utilization: %{y}%"
        )
    fig.update_traces(mode="lines+markers")
    fig.update_layout(height=height)
    st.plotly_chart(fig, use_container_width=True)
    return True

# -------------------- ADMIN DASHBOARD --------------------
def show_admin_dashboard():
    st.title("📊 Admin Dashboard")

    # Filters
    col1, col2 = st.columns([2, 2])
    with col1:
        date_filter = st.date_input("📅 Select Date")
    with col2:
        metric = st.selectbox(
            "📈 Select Metric",
            ["CPU", "GPU", "RAM", "Ethernet", "Disk"]
        )

    dynamic_df = fetch_dynamic_data(date_filter)
    static_df = fetch_employee_static()

    if dynamic_df.empty:
        st.warning("⚠️ No data available for the selected date.")
        return

    # Loop over employees
    for emp_id, emp_df in dynamic_df.groupby("emp_id"):
        st.markdown("---")
        st.subheader(f"👤 {emp_df['name'].iloc[0]} ({emp_df['pc_number'].iloc[0]})")

        col_left, col_right = st.columns([2, 1])

        # --- LEFT: Graphs ---
        with col_left:
            if metric == "CPU":
                safe_plot_line(emp_df, "cpu_utilization_percent", "top_cpu_process",
                               "CPU Utilization Trend", "CPU (%)")
            elif metric == "GPU":
                safe_plot_line(emp_df, "gpu_utilization_percent", "top_gpu_process",
                               "GPU Utilization Trend", "GPU (%)")
            elif metric == "RAM":
                safe_plot_line(emp_df, "ram_utilization_percent", "top_ram_process",
                               "RAM Utilization Trend", "RAM (%)")
            elif metric == "Ethernet":
                safe_plot_line(emp_df, "ethernet_utilization_percent", None,
                               "Ethernet Utilization Trend", "Ethernet (%)")
            elif metric == "Disk":
                safe_plot_line(emp_df, "disk_usage_percent", None,
                               "Disk Usage Trend", "Disk (%)")

        # --- RIGHT: Static Specs ---
        with col_right:
            st.markdown("### 🖥️ PC Specs")
            specs = static_df[static_df["pc_name"] == emp_df["pc_number"].iloc[0]]
            if not specs.empty:
                specs_dict = specs.iloc[0].to_dict()
                st.write(f"**CPU Model:** {specs_dict.get('cpu_model', 'N/A')}")
                st.write(f"**RAM Size:** {specs_dict.get('ram_size_gb', 'N/A')} GB")
                st.write(f"**IP Address:** {specs_dict.get('ip_address', 'N/A')}")
                st.write(f"**BIOS Version:** {specs_dict.get('bios_version', 'N/A')}")
            else:
                st.info("ℹ️ No static specs available for this PC.")







# --------------------Employee detail update ----------
def show_employee_details():
    st.title("👨‍💻 Employee Details")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # 🔹 Get all PC names from Static_Data/Dynamic_Data
    cursor.execute("""
        SELECT DISTINCT s.pc_name
        FROM Static_Data s
        LEFT JOIN Employee e ON s.pc_name = e.pc_number
        WHERE e.pc_number IS NULL
        UNION
        SELECT DISTINCT d.pc_name
        FROM Dynamic_Data d
        LEFT JOIN Employee e ON d.pc_name = e.pc_number
        WHERE e.pc_number IS NULL
    """)
    available_pcs = [row["pc_name"] for row in cursor.fetchall()]

    # 🔹 Also get all existing employee-PC mappings (for update)
    cursor.execute("SELECT * FROM Employee")
    existing_records = cursor.fetchall()
    conn.close()

    # Dropdown for PC number (unlinked ones first, or manual entry)
    pc_number = st.selectbox(
        "PC Number (from collected data but not yet linked)",
        options=["-- Enter Manually --"] + available_pcs
    )
    if pc_number == "-- Enter Manually --":
        pc_number = st.text_input("Enter PC Number manually")

    emp_id = st.text_input("Employee ID")
    emp_name = st.text_input("Employee Name")
    office_location = st.text_input("Office Location", value="Mumbai")

    if st.button("💾 Save Employee"):
        if not emp_id or not emp_name or not pc_number:
            st.error("⚠️ Please fill Employee ID, Name, and PC Number.")
        else:
            try:
                conn = get_connection()
                cursor = conn.cursor(dictionary=True)

                # check if PC already exists
                cursor.execute("SELECT * FROM Employee WHERE pc_number = %s", (pc_number,))
                exists = cursor.fetchone()

                if exists:
                    st.info(f"ℹ️ This PC `{pc_number}` is already assigned to: {exists['name']} ({exists['emp_id']})")

                    if st.confirm("Do you want to update this employee's details?"):
                        cursor.execute("""
                            UPDATE Employee
                            SET emp_id = %s, name = %s, office_location = %s
                            WHERE pc_number = %s
                        """, (emp_id, emp_name, office_location, pc_number))
                        conn.commit()
                        st.success(f"✅ Employee details updated for PC `{pc_number}`")
                else:
                    cursor.execute(
                        "INSERT INTO Employee (emp_id, name, pc_number, office_location) VALUES (%s, %s, %s, %s)",
                        (emp_id, emp_name, pc_number, office_location)
                    )
                    conn.commit()
                    st.success(f"✅ Employee `{emp_name}` added and linked to PC `{pc_number}`")

            except Exception as e:
                st.error(f"❌ Database error: {e}")
            finally:
                conn.close()


# -------------------- MAIN ROUTER --------------------
def show_dashboard():
    if st.session_state.role == "Admin":
        st.sidebar.title("🔧 Navigation")
        page = st.sidebar.radio(
            "Go to", 
            ["Homepage", "Graph Stats", "Individual Stats", "Alerts", "Employee Details"], 
            index=["Homepage", "Graph Stats", "Individual Stats", "Alerts", "Employee Details"].index(st.session_state.page)
        )

        st.session_state.page = page


        # --- Logout Button at the bottom ---
        st.sidebar.markdown("---")
        if st.sidebar.button(" Logout"):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.role = ""
            st.session_state.page = "Homepage"
            st.rerun()

        # Route to pages
        if page == "Homepage":
            show_admin_dashboard()
        elif page == "Graph Stats":
            #show_graph_stats()
            st.write("Graph under construciton")
        elif page == "Individual Stats":
            #show_individual_stats()
            st.write("individual under construciton")
        elif page == "Alerts":
            #show_alerts()
            st.write("alerts under construciton")
        elif page == "Employee Details":
            show_employee_details()
            #st.write("Employee under construciton")
    else:
        st.error("🚫 Only Admin access is implemented right now.")


# -------------------- APP ENTRY --------------------
if not st.session_state.logged_in:
    show_login()
else:
    show_dashboard()
