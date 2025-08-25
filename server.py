from flask import Flask, request, jsonify
import mysql.connector

app = Flask(__name__)

# === Database Config ===
db_config = {
    'host': 'srv1674.hstgr.io',   # On Hostinger, keep "localhost"
    'user': 'u221987201_hpa_root',
    'password': 'Root@303',
    'database': 'u221987201_hpa_pc'
}
'''
#online mysql has been connected can use it when want to test with mysql new hosted online
db_config = {
    'host': 'localhost',   # On Hostinger, keep "srv1674.hstgr.io"
    'user': 'root',
    'password': 'root@303',
    'database': 'hpa_pc2'
}
'''

SECRET_KEY = "my_super_secret_key_123"
def check_secret(data):
    return data.get("secret_key") == SECRET_KEY


# === Home Route ===
@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "status": "server running",
        "endpoints": ["/login (POST)", "/add_static (POST)", "/add_dynamic (POST)"]
    })

# === Login API ===
@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')

        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        query = "SELECT role FROM Login WHERE username = %s AND password = %s"
        cursor.execute(query, (username, password))
        result = cursor.fetchone()

        cursor.close()
        conn.close()

        if result:
            return jsonify({"status": "success", "role": result['role']}), 200
        return jsonify({"status": "error", "message": "Invalid credentials"}), 401

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# === Add Static Data API ===
@app.route('/add_static', methods=['POST'])
def add_static():
    try:
        data = request.get_json()

        if not check_secret(data):
            return jsonify({"status": "error", "message": "Unauthorized"}), 403

        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        query = """
        INSERT INTO Static_Data 
        (pc_name, record_date, cpu_model, logical_processors, ram_size_gb, storage_size_gb, os_version,
         ip_address, bios_version, expansion_slots_motherboard, pc_location,
         system_serial_number, motherboard_serial_number, bios_serial_number)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
        cpu_model = VALUES(cpu_model),
        logical_processors = VALUES(logical_processors),
        ram_size_gb = VALUES(ram_size_gb),
        storage_size_gb = VALUES(storage_size_gb),
        os_version = VALUES(os_version),
        ip_address = VALUES(ip_address),
        bios_version = VALUES(bios_version),
        expansion_slots_motherboard = VALUES(expansion_slots_motherboard),
        pc_location = VALUES(pc_location),
        system_serial_number = VALUES(system_serial_number),
        motherboard_serial_number = VALUES(motherboard_serial_number),
        bios_serial_number = VALUES(bios_serial_number)
        """
        values = (
            data['pc_name'], data['record_date'], data.get('cpu_model'),
            data.get('logical_processors'), data.get('ram_size_gb'),
            data.get('storage_size_gb'), data.get('os_version'),
            data.get('ip_address'), data.get('bios_version'),
            data.get('expansion_slots_motherboard'), data.get('pc_location'),
            data.get('system_serial_number'), data.get('motherboard_serial_number'),
            data.get('bios_serial_number')
        )

        cursor.execute(query, values)
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({"status": "success", "message": "Static data inserted/updated"}), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# === Add Dynamic Data API ===
@app.route('/add_dynamic', methods=['POST'])
def add_dynamic():
    try:
        data = request.get_json()

        if not check_secret(data):
            return jsonify({"status": "error", "message": "Unauthorized"}), 403
        
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        query = """
        INSERT INTO Dynamic_Data 
        (pc_name, record_timestamp, cpu_utilization_percent, ram_utilization_percent, 
         gpu_utilization_percent, disk_usage_percent, ethernet_utilization_percent,
         top_cpu_process, top_ram_process, top_gpu_process)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        values = (
            data['pc_name'], data['record_timestamp'],
            data.get('cpu_utilization_percent'), data.get('ram_utilization_percent'),
            data.get('gpu_utilization_percent'), data.get('disk_usage_percent'),
            data.get('ethernet_utilization_percent'), data.get('top_cpu_process'),
            data.get('top_ram_process'), data.get('top_gpu_process')
        )

        cursor.execute(query, values)
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({"status": "success", "message": "Dynamic data inserted"}), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# === Run Server ===
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
