import streamlit as st
import requests
import mysql.connector
import pandas as pd
import plotly.express as px
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, ListFlowable, ListItem
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import matplotlib.dates as mdates
from reportlab.lib import colors
import matplotlib.pyplot as plt
import io
import datetime as dt 
import pandas as pd

# app file in backup ready, will make it.
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
        SELECT s.*
        FROM Static_Data s
        INNER JOIN (
            SELECT pc_name, MAX(static_id) AS latest_id
            FROM Static_Data
            GROUP BY pc_name
        ) t ON s.pc_name = t.pc_name AND s.static_id = t.latest_id
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

# -------------------- GRAPH STATS (Grid of Graphs only) --------------------
def show_graph_stats():
    st.title("📈 Graph Stats - All Employees")

    # User input filters
    col1, col2 = st.columns([2, 2])
    with col1:
        date_filter = st.date_input("📅 Select Date", key="graph_stats_date")
    with col2:
        metric = st.selectbox(
            "📊 Select Metric",
            ["CPU", "GPU", "RAM", "Ethernet", "Disk"],
            key="graph_stats_metric"
        )

    df = fetch_dynamic_data(date_filter)

    if df.empty:
        st.warning("⚠️ No data available for the selected date.")
        return

    # Metric mapping
    if metric == "CPU":
        y_col, hover_col, y_label = "cpu_utilization_percent", "top_cpu_process", "CPU Utilization (%)"
    elif metric == "GPU":
        y_col, hover_col, y_label = "gpu_utilization_percent", "top_gpu_process", "GPU Utilization (%)"
    elif metric == "RAM":
        y_col, hover_col, y_label = "ram_utilization_percent", "top_ram_process", "RAM Utilization (%)"
    elif metric == "Ethernet":
        y_col, hover_col, y_label = "ethernet_utilization_percent", None, "Ethernet Utilization (%)"
    else:  # Disk
        y_col, hover_col, y_label = "disk_usage_percent", None, "Disk Usage (%)"

    # Group by employees
    employees = list(df.groupby("emp_id"))

    # Show 3 employees per row
    for i in range(0, len(employees), 3):
        cols = st.columns(3)
        for j, (emp_id, emp_df) in enumerate(employees[i:i+3]):
            with cols[j]:
                with st.container():
                    # Use caption for uniform small text
                    emp_name = str(emp_df['name'].iloc[0]) if 'name' in emp_df.columns else "Employee"
                    pc_number = str(emp_df['pc_number'].iloc[0]) if 'pc_number' in emp_df.columns else "PC"
                    st.caption(f"👤 {emp_name} ({pc_number})")

                    # Plot graph
                    ok = safe_plot_line(
                        emp_df,
                        y_col=y_col,
                        hover_col=hover_col,
                        title=f"{metric} Utilization Trend",
                        y_label=y_label,
                        height=250,
                    )
                    if not ok:
                        st.info(f"No valid {metric} data to plot.")

# -------------------- INDIVIDUAL STATS --------------------
def show_individual_stats():
    st.title("👤 Individual Employee Stats")

    # Fetch all employee names
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT name FROM Employee")
        employees = [row[0] for row in cursor.fetchall()]
        conn.close()
    except Exception:
        employees = []

    if not employees:
        st.warning("⚠️ No employees found.")
        return

    # Employee & date selection
    selected_emp = st.selectbox("🔎 Search Employee by Name", employees)
    date_filter = st.date_input("📅 Select Date")

    if not selected_emp:
        return

    # --- Fetch dynamic data for graphs ---
    try:
        df = fetch_dynamic_data(date_filter)
    except Exception:
        st.warning("⚠️ Unable to fetch dynamic data.")
        return

    # --- Filter only this employee ---
    emp_df_all = df[df.get("name", pd.Series(dtype=str)) == selected_emp].copy()

    if emp_df_all.empty:
        st.warning("⚠️ No utilization data for this employee on the selected date.")
        return

    # Ensure timestamp is datetime
    if "record_timestamp" in emp_df_all.columns:
        emp_df_all["record_timestamp"] = pd.to_datetime(
            emp_df_all["record_timestamp"], errors="coerce"
        )

    # --- Show 5 graphs ---
    st.subheader(f"📊 Utilization Trends for {selected_emp} ({date_filter})")

    # CPU
    safe_plot_line(
        emp_df_all,
        "cpu_utilization_percent",
        "top_cpu_process",
        "CPU Utilization Trend",
        "CPU Utilization (%)",
        height=300,
    )

    # RAM
    safe_plot_line(
        emp_df_all,
        "ram_utilization_percent",
        "top_ram_process",
        "RAM Utilization Trend",
        "RAM Utilization (%)",
        height=300,
    )

    # GPU
    safe_plot_line(
        emp_df_all,
        "gpu_utilization_percent",
        "top_gpu_process",
        "GPU Utilization Trend",
        "GPU Utilization (%)",
        height=300,
    )

    # Ethernet (no hover)
    safe_plot_line(
        emp_df_all,
        "ethernet_utilization_percent",
        None,
        "Ethernet Utilization Trend",
        "Ethernet Utilization (%)",
        height=300,
    )

    # Disk (no hover)
    safe_plot_line(
        emp_df_all,
        "disk_usage_percent",
        None,
        "Disk Usage Trend",
        "Disk Usage (%)",
        height=300,
    )

    # --- Fetch static info (latest only, not affected by date) ---
    st.markdown("### 🖥️ System Specs")
    try:
        static_df = fetch_employee_static()
    except Exception:
        st.warning("⚠️ Unable to fetch static system specs.")
        return

    if static_df.empty:
        st.warning("⚠️ No static specs available.")
        return

    emp_pc = emp_df_all["pc_number"].iloc[0] if "pc_number" in emp_df_all.columns else None
    if emp_pc:
        specs = static_df[static_df["pc_name"] == emp_pc]
        if not specs.empty:
            specs_dict = specs.iloc[0].to_dict()

            # Nicely formatted system specs
            st.write(f"**CPU Model:** {specs_dict.get('cpu_model', 'N/A')}")
            st.write(f"**Logical Processors:** {specs_dict.get('logical_processors', 'N/A')}")
            st.write(f"**RAM Size:** {specs_dict.get('ram_size_gb', 'N/A')} GB")
            st.write(f"**Storage Size:** {specs_dict.get('storage_size_gb', 'N/A')} GB")
            st.write(f"**OS Version:** {specs_dict.get('os_version', 'N/A')}")
            st.write(f"**IP Address:** {specs_dict.get('ip_address', 'N/A')}")
            st.write(f"**BIOS Version:** {specs_dict.get('bios_version', 'N/A')}")
            st.write(f"**Expansion Slots (Motherboard):** {specs_dict.get('expansion_slots_motherboard', 'N/A')}")
            st.write(f"**PC Location:** {specs_dict.get('pc_location', 'N/A')}")
            st.write(f"**System Serial Number:** {specs_dict.get('system_serial_number', 'N/A')}")
            st.write(f"**Motherboard Serial Number:** {specs_dict.get('motherboard_serial_number', 'N/A')}")
            st.write(f"**BIOS Serial Number:** {specs_dict.get('bios_serial_number', 'N/A')}")

        else:
            st.warning("⚠️ Specs not found for this employee’s PC.")
    else:
        st.warning("⚠️ Employee PC number missing in records.")


# ------------------- Alerts - fetch query, get and show (CPU, RAM, GPU only) -------------------
def fetch_data(start_date, end_date, group_by="month"):
    """
    Returns aggregated averages per PC between [start_date, end_date].
    group_by = "month" → aggregates by YYYY-MM
    group_by = "day"   → aggregates by YYYY-MM-DD
    """
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

    from datetime import datetime, timedelta
    end_exclusive = (datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

    if group_by == "month":
        date_expr = "DATE_FORMAT(record_timestamp, '%Y-%m')"
    else:  # daily aggregation for custom ranges
        date_expr = "DATE(record_timestamp)"

    query = f"""
        SELECT 
            pc_name,
            {date_expr} AS period,
            AVG(cpu_utilization_percent) AS avg_cpu,
            AVG(ram_utilization_percent) AS avg_ram,
            AVG(gpu_utilization_percent) AS avg_gpu
        FROM Dynamic_Data
        WHERE record_timestamp >= %s AND record_timestamp < %s
        GROUP BY pc_name, period
        ORDER BY pc_name, period;
    """

    cursor.execute(query, (start_date, end_exclusive))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return pd.DataFrame(rows)


# ------------------- Generate ALERT LOGIC -------------------
def generate_alerts(df):
    critical, imbalance, idle = [], [], []

    for _, row in df.iterrows():
        pc = row['pc_name']
        cpu, ram, gpu = row['avg_cpu'], row['avg_ram'], row['avg_gpu']

        if cpu > 85 and ram > 85 and gpu > 85:
            critical.append(f"{pc} is heavily overutilized across CPU, RAM, and GPU.")
        elif cpu < 20 and ram < 20 and gpu < 20:
            idle.append(f"{pc} is mostly idle across CPU, RAM, and GPU.")
        else:
            if cpu < 20 and ram > 80:
                imbalance.append(f"{pc}: CPU is underused while RAM is overloaded.")
            elif cpu > 80 and ram < 20:
                imbalance.append(f"{pc}: CPU is overworked while RAM remains idle.")
            elif gpu > 80 and cpu < 20 and ram < 20:
                imbalance.append(f"{pc}: GPU is overutilized while CPU and RAM are idle.")
            elif gpu < 20 and cpu > 80 and ram > 80:
                imbalance.append(f"{pc}: GPU is idle while CPU and RAM are overworked.")

    return critical, imbalance, idle


# ------------------- Show Alerts -------------------
def show_alerts():
    st.header("⚠️ System Alerts")

    today = dt.date.today()
    option = st.selectbox("Select Range", ["Last 1 Month", "Last 3 Months", "Custom Range"])

    if option == "Last 1 Month":
        start_date = (pd.to_datetime(today) - pd.DateOffset(months=1)).strftime("%Y-%m-%d")
        end_date   = today.strftime("%Y-%m-%d")
        df = fetch_data(start_date, end_date, group_by="month")

    elif option == "Last 3 Months":
        start_date = (pd.to_datetime(today) - pd.DateOffset(months=3)).strftime("%Y-%m-%d")
        end_date   = today.strftime("%Y-%m-%d")
        df = fetch_data(start_date, end_date, group_by="month")

    elif option == "Custom Range":
        start_day = st.date_input("Start Date", value=today.replace(day=1), key="alert_start_day")
        end_day   = st.date_input("End Date",   value=today,               key="alert_end_day")
        start_date = pd.to_datetime(start_day).strftime("%Y-%m-%d")
        end_date   = pd.to_datetime(end_day).strftime("%Y-%m-%d")
        df = fetch_data(start_date, end_date, group_by="day")

    # Handle empty data
    if df.empty:
        st.warning("⚠️ No data available for the selected range.")
        return

    critical, imbalance, idle = generate_alerts(df)

    st.caption(f"Aggregated utilization data from {start_date} to {end_date}.")

    # --- Critical ---
    st.subheader("🔥 Critical Overutilized")
    if critical:
        for alert in critical:
            st.error(alert)
    else:
        st.info("No systems are critically overutilized.")

    # --- Imbalance ---
    st.subheader("⚖️ Resource Imbalance")
    if imbalance:
        for alert in imbalance:
            st.warning(alert)
    else:
        st.info("No resource imbalances detected.")

    # --- Idle ---
    st.subheader("💤 Idle PCs")
    if idle:
        for alert in idle:
            st.info(alert)
    else:
        st.info("No idle systems found.")

    st.markdown("---")
    st.subheader("📑 Reports Section")
    report_option = st.selectbox("Select Report", ["ALL PC Info", "PC Specific Report", "System Alerts Report"])

    if report_option == "ALL PC Info":
        report_all_pc_info()

    elif report_option == "PC Specific Report":
        report_pc_stats()

    elif report_option == "System Alerts Report":
        report_system_alerts(critical, imbalance, idle, start_date, end_date)
            

# ---------------reports section -----------------
# All PC Info --------------------
def report_all_pc_info():
    st.subheader("🖥️ All PC Info")
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

    query = """ 
    SELECT e.emp_id, e.name, e.pc_number, s.cpu_model, s.logical_processors, s.ram_size_gb,
    s.storage_size_gb, s.os_version, s.ip_address, s.pc_location, s.bios_version,
    s.expansion_slots_motherboard
    FROM Employee e
    JOIN Static_Data s 
      ON e.pc_number = s.pc_name
    WHERE NOT EXISTS (
        SELECT 1
        FROM Static_Data s2
        WHERE s2.pc_name = s.pc_name
          AND (
            s2.record_date > s.record_date
            OR (s2.record_date = s.record_date AND s2.static_id > s.static_id)
        )  
    );

    """  

    cursor.execute(query)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if not rows:
        st.info("No PC data found.")
        return

    df = pd.DataFrame(rows)

    # --- Just show count in UI ---
    st.success(f"Retrieved {len(df)} PCs in system.")

    # --- Export full table in PDF ---
    pdf = export_pdf("All PC Info Report", [df], landscape_mode=True)
    st.download_button(
        label="📥 Download All PC Info PDF",
        data=pdf,
        file_name="all_pc_info_report.pdf",
        mime="application/pdf",
    )


# PC Stats --------------------
def report_pc_stats():
    st.subheader("📊 PC Stats (Last 7 Days)")

    # --- Get PC list ---
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT pc_name FROM Dynamic_Data")
    pc_list = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()

    selected_pc = st.selectbox("Select PC", pc_list)
    if not selected_pc:
        return

    # --- Define period ---
    end_date = dt.datetime.now()
    start_date = end_date - dt.timedelta(days=7)

    conn = mysql.connector.connect(**DB_CONFIG)
    query = """
        SELECT record_timestamp, cpu_utilization_percent, ram_utilization_percent, 
               gpu_utilization_percent, disk_usage_percent, ethernet_utilization_percent
        FROM Dynamic_Data
        WHERE pc_name = %s AND record_timestamp BETWEEN %s AND %s
        ORDER BY record_timestamp
    """
    df = pd.read_sql(query, conn, params=(selected_pc, start_date, end_date))
    conn.close()

    if df.empty:
        st.warning("No utilization data for this PC in last 7 days.")
        return

    # --- Show only info message in UI ---
    st.info(f"📊 Stats collected for PC: {selected_pc}.")

    # --- Generate charts only for PDF ---
    charts = []
    for metric in [
        "cpu_utilization_percent", 
        "ram_utilization_percent", 
        "gpu_utilization_percent", 
        "disk_usage_percent", 
        "ethernet_utilization_percent"
    ]:
        fig, ax = plt.subplots()
        ax.plot(df["record_timestamp"], df[metric], label=metric)
        ax.set_title(f"{metric.replace('_', ' ').title()} over Time")
        ax.set_xlabel("Time")
        ax.set_ylabel("Utilization (%)")
        ax.legend()
        img_buf = io.BytesIO()
        plt.savefig(img_buf, format="png")
        img_buf.seek(0)
        charts.append(img_buf)
        plt.close(fig)

    # --- Format period without microseconds ---
    period_start = start_date.strftime("%Y-%m-%d %H:%M:%S")
    period_end = end_date.strftime("%Y-%m-%d %H:%M:%S")

    # --- Export to PDF ---
    pdf = export_pdf(
        f"PC Stats Report - {selected_pc}",
        charts,
        start_date=period_start,
        end_date=period_end
    )

    st.download_button(
        label=f"📥 Download {selected_pc} Stats PDF",
        data=pdf,
        file_name=f"{selected_pc}_stats_report.pdf",
        mime="application/pdf",
    )


# System Alerts --------------------
def report_system_alerts(critical, imbalance, idle, start_date, end_date):
    st.subheader("🛠️ System Alerts")

    # Prepare alert text blocks for PDF
    pdf_blocks = []
    pdf_blocks.append("Critical Alerts: " + (", ".join(critical) if critical else "N/A"))
    pdf_blocks.append("Imbalance Alerts: " + (", ".join(imbalance) if imbalance else "N/A"))
    pdf_blocks.append("Idle Alerts: " + (", ".join(idle) if idle else "N/A"))

    # --- Export Alerts to PDF ---
    pdf = export_pdf("System Alerts Report", pdf_blocks, start_date=start_date, end_date=end_date)
    st.download_button(
        label="📥 Download System Alerts PDF",
        data=pdf,
        file_name="system_alerts_report.pdf",
        mime="application/pdf",
    )


# ---------------export pdf section -----------------
def export_pdf(title, content_blocks, landscape_mode=False, start_date=None, end_date=None):
    buffer = io.BytesIO()
    page_size = landscape(A4) if landscape_mode else A4
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=page_size,
        leftMargin=30, rightMargin=30, topMargin=50, bottomMargin=40
    )
    styles = getSampleStyleSheet()

    # Custom styles
    header_style = ParagraphStyle("Header", parent=styles["Heading1"], fontSize=18, spaceAfter=12, alignment=1)
    subheader_style = ParagraphStyle("SubHeader", parent=styles["Heading2"], fontSize=12, spaceAfter=8, leading=14, fontName="Helvetica-Bold")
    normal_style = ParagraphStyle("Normal", parent=styles["Normal"], fontSize=10, leading=12)

    elements = []

    # --- Title ---
    elements.append(Paragraph(title, header_style))

    # --- Report Date + Period ---
    gen_date_text = f"Report Generation Date: {dt.datetime.now().strftime('%Y-%m-%d')}"
    elements.append(Paragraph(gen_date_text, normal_style))

    if start_date and end_date:
        if start_date == end_date:
            period_text = f"Period: {start_date}"
        else:
            period_text = f"Period: {start_date} to {end_date}"
        elements.append(Paragraph(period_text, normal_style))

    elements.append(Spacer(1, 12))

    # --- Content Blocks ---
    for block in content_blocks:
        if isinstance(block, str):
            if any(block.startswith(prefix) for prefix in ["Critical Alerts:", "Imbalance Alerts:", "Idle Alerts:"]):
                label, values = block.split(":", 1)
                elements.append(Paragraph(label.strip(), subheader_style))

                items = [v.strip() for v in values.split(",")] if values.strip() else ["N/A"]
                bullet_list = ListFlowable(
                    [ListItem(Paragraph(item, normal_style)) for item in items],
                    bulletType="bullet",
                    start="circle"
                )
                elements.append(bullet_list)
                elements.append(Spacer(1, 12))
            else:
                elements.append(Paragraph(block, normal_style))
                elements.append(Spacer(1, 12))

        elif isinstance(block, pd.DataFrame):
            col_widths = [doc.width / len(block.columns)] * len(block.columns)
            data = []
            for i, row in enumerate([block.columns.tolist()] + block.values.tolist()):
                wrapped_row = []
                for val in row:
                    cell_text = str(val) if val is not None else ""
                    wrapped_row.append(Paragraph(cell_text, normal_style))
                data.append(wrapped_row)

            table = Table(data, colWidths=col_widths)
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4F81BD")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F2F2")]),
            ]))
            elements.append(table)
            elements.append(Spacer(1, 12))

        elif isinstance(block, io.BytesIO):  # Chart images
            # 🔹 Slightly wider chart to spread x-ticks
            img = Image(block, width=7.5*inch, height=3*inch)
            elements.append(img)
            elements.append(Spacer(1, 16))

    # --- Footer ---
    def add_footer(canvas, doc):
        canvas.saveState()
        footer_text = "Pioneer Foundations Engineer"
        canvas.setFont("Helvetica-Oblique", 8)
        canvas.drawCentredString(page_size[0] / 2.0, 20, footer_text)
        canvas.restoreState()

    doc.build(elements, onFirstPage=add_footer, onLaterPages=add_footer)

    pdf = buffer.getvalue()
    buffer.close()
    return pdf

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
            show_graph_stats()
        elif page == "Individual Stats":
            show_individual_stats()
        elif page == "Alerts":
            show_alerts()
            st.write("reports under construciton")
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
