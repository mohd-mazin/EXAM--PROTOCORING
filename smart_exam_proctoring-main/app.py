# pyrefly: ignore [missing-import]
from flask import Flask, render_template, request, jsonify, Response, send_file, session, redirect, send_from_directory
from database import init_db, log_violation, save_report_summary, get_latest_report_summary, get_timeline, get_db_connection
import os
import cv2
import datetime
import time
from proctoring.detector import detect_frame
from proctoring.analysis import fetch_violation_stats, generate_pdf_report
from ai_report_generator import generate_professional_summary
from proctoring.gaze_tracker import GazeTracker
import bcrypt
import random
import string
import io
import base64
import sqlite3
import tempfile
import uuid
import csv
import zipfile
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from proctoring.face_auth import get_embedding_from_base64, verify_face_embeddings

app = Flask(__name__)
app.secret_key = 'super_secret_proctoring_key'

# Ensure directories exist
os.makedirs('database', exist_ok=True)
os.makedirs('models', exist_ok=True)
os.makedirs('logs', exist_ok=True)

# Initialize database
init_db()

# Global variables for stats
proctoring_stats = {
    "persons": 0,
    "phones": 0,
    "warning": "Safe",
    "head_direction": "Focused"
}

latest_raw_frame = None

try:
    gaze_tracker = GazeTracker()
except Exception as e:
    print("Gaze tracker disabled:", e)
    gaze_tracker = None

look_away_start = None
is_looking_away = False

exam_telemetry = {}

def save_evidence(frame, violation_type):
    if frame is None: return None
    timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_type = violation_type.replace(" ", "_").lower()
    filename = f"{timestamp_str}_{safe_type}.jpg"
    filepath = os.path.join('logs', filename)
    cv2.imwrite(filepath, frame)
    return filepath

def generate_frames(session_id, usn, exam_start_time):
    global proctoring_stats, latest_raw_frame, look_away_start, is_looking_away, exam_telemetry
    print("Camera initializing...")
    cap = cv2.VideoCapture(0)
    print("Camera opened:", cap.isOpened())
    
    if not cap.isOpened():
        print("Camera failed to open")
        # Return a single frame with an error message
        import numpy as np
        error_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(error_frame, "Camera failed to open", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        ret, buffer = cv2.imencode('.jpg', error_frame)
        yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        return

    exam_telemetry[session_id] = {
        "total_frames": 0,
        "face_frames": 0,
        "focused_frames": 0,
        "start_time": time.time(),
        "audio_total": 0,
        "audio_voice": 0
    }
    
    os.makedirs('recordings', exist_ok=True)
    timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    video_path = os.path.join('recordings', f"exam_{usn}_{timestamp_str}.mp4")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE exam_sessions SET video_path = ? WHERE id = ?", (video_path, session_id))
    conn.commit()
    conn.close()
    
    fourcc = cv2.VideoWriter_fourcc(*'avc1')
    out = cv2.VideoWriter(video_path, fourcc, 20.0, (640, 480))
    
    last_warning = None
    
    try:
        while True:
            success, frame = cap.read()
            if not success: break
            
            latest_raw_frame = frame.copy()
            
            # YOLO Detection
            result = detect_frame(frame)
            processed_frame = result["frame"]
            
            # Write to video recording
            try:
                out.write(cv2.resize(processed_frame, (640, 480)))
            except:
                pass
            
            # Gaze Detection
            if gaze_tracker:
                head_dir = gaze_tracker.process_frame(frame)
            else:
                head_dir = "Focused"
            
            proctoring_stats["persons"] = result["persons"]
            proctoring_stats["phones"] = result["phones"]
            proctoring_stats["head_direction"] = head_dir
            
            telemetry = exam_telemetry.get(session_id)
            if telemetry:
                telemetry["total_frames"] += 1
                if result['persons'] > 0: telemetry["face_frames"] += 1
                if head_dir == "Focused": telemetry["focused_frames"] += 1
            
            # Logic for Look Away Timer
            current_time = time.time()
            look_away_warning = None
            
            if head_dir != "Focused":
                if not is_looking_away:
                    is_looking_away = True
                    look_away_start = current_time
                else:
                    duration = current_time - look_away_start
                    if duration > 3.0:
                        look_away_warning = f"Looking Away ({duration:.1f}s)"
            else:
                if is_looking_away:
                    duration = current_time - look_away_start
                    if duration > 3.0:
                        evidence = save_evidence(latest_raw_frame, "Looking Away From Exam Screen")
                        rel_time = current_time - exam_start_time
                        log_violation("Looking Away From Exam Screen", evidence, details=f"{duration:.1f} sec", session_id=session_id, relative_timestamp=rel_time)
                    is_looking_away = False
                    look_away_start = None
            
            warning = "Safe"
            db_warning = None
            details_str = ""
            
            if result['phones'] > 0:
                conf_pct = int(result.get('phone_conf', 0) * 100)
                details_str = f"{conf_pct}%"
                warning = f"Mobile Phone Detected ({conf_pct}%)"
                db_warning = "Mobile Phone Detected"
            elif result['persons'] > 1:
                conf_pct = int(result.get('person_conf', 0) * 100)
                details_str = f"{conf_pct}%"
                warning = f"Multiple Persons Detected ({conf_pct}%)"
                db_warning = "Multiple Persons Detected"
            elif result['persons'] == 0:
                warning = "Face Absent"
                db_warning = "Face Absent"
            elif look_away_warning:
                warning = look_away_warning
                # Look away is logged earlier in the loop (lines 142-148),
                # so we do NOT set db_warning to trigger the generic logger below.
                # We just update the live warning status here.
                
            proctoring_stats["warning"] = warning
            
            if db_warning and db_warning != last_warning:
                evidence_path = save_evidence(latest_raw_frame, db_warning)
                rel_time = time.time() - exam_start_time
                log_violation(db_warning, evidence_path, details=details_str, session_id=session_id, relative_timestamp=rel_time)
                
            last_warning = db_warning
            
            ret, buffer = cv2.imencode('.jpg', processed_frame)
            frame_bytes = buffer.tobytes()
            print("Sending frame")
            yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
    finally:
        cap.release()
        out.release()

# --- REGISTRATION AND LOGIN LOGIC ---

def register_student(name, usn, email, face_image_b64):
    embedding_json, error_msg = get_embedding_from_base64(face_image_b64)
    if not embedding_json:
        return False, error_msg
        
    year = datetime.datetime.now().year
    user_id = f"EXAM{year}-{random.randint(1000, 9999)}"
    
    password = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    if ',' in face_image_b64:
        img_data = base64.b64decode(face_image_b64.split(',')[1])
    else:
        img_data = base64.b64decode(face_image_b64)
        
    img_path = os.path.join('logs', f"reg_{usn}.jpg")
    with open(img_path, 'wb') as f:
        f.write(img_data)
        
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO students (student_name, usn, email, user_id, password_hash, face_embedding, face_image_path, registration_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, usn, email, user_id, hashed, embedding_json, img_path, timestamp))
        student_db_id = cursor.lastrowid
        conn.commit()
    except Exception as e:
        conn.close()
        return False, "USN or Email already registered."
    
    conn.close()
    session['temp_password'] = password
    return True, student_db_id

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.json
        success, result = register_student(data['student_name'], data['usn'], data['email'], data['face_image'])
        if success:
            return jsonify({"success": True, "student_id": result})
        else:
            return jsonify({"success": False, "error": result})
    return render_template('register.html')

@app.route('/registration_success')
def registration_success():
    student_id = request.args.get('id')
    password = session.get('temp_password')
    if not student_id or not password: return redirect('/register')
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM students WHERE id = ?', (student_id,))
    student = cursor.fetchone()
    conn.close()
    
    return render_template('registration_success.html', student=student, password=password)

@app.route('/download_credentials')
def download_credentials():
    student_id = request.args.get('id')
    password = session.get('temp_password')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM students WHERE id = ?', (student_id,))
    student = cursor.fetchone()
    conn.close()
    
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    c.setFont("Helvetica-Bold", 20)
    c.drawString(50, height - 50, "Smart Exam Proctoring - Credentials")
    
    c.setFont("Helvetica", 14)
    c.drawString(50, height - 100, f"Student Name: {student['student_name']}")
    c.drawString(50, height - 130, f"USN: {student['usn']}")
    c.drawString(50, height - 160, f"Registration Time: {student['registration_time']}")
    
    c.drawString(50, height - 210, f"User ID: {student['user_id']}")
    c.drawString(50, height - 240, f"Password: {password}")
    
    c.setFont("Helvetica-Oblique", 12)
    c.drawString(50, height - 290, "Please keep this document secure. You will need it to login and verify your Face ID.")
    
    c.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f'credentials_{student["usn"]}.pdf', mimetype='application/pdf')

@app.route('/', methods=['GET', 'POST'])
def landing():
    if request.method == 'POST':
        return redirect('/login')
    return render_template('landing.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        password = request.form.get('password')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM students WHERE user_id = ?', (user_id,))
        student = cursor.fetchone()
        conn.close()
        
        if student and student['is_active']:
            if bcrypt.checkpw(password.encode('utf-8'), student['password_hash'].encode('utf-8')):
                session['student_id'] = student['id']
                session['student_name'] = student['student_name']
                session['usn'] = student['usn']
                session['exam_start'] = time.time()
                return redirect('/verify_face_ui')
        
        return render_template('login.html', error="Invalid User ID or Password.")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/verify_face_ui')
def verify_face_ui():
    if 'student_id' not in session: return redirect('/login')
    return render_template('verify_face.html')

@app.route('/verify_face', methods=['POST'])
def verify_face():
    if 'student_id' not in session:
        return jsonify({"success": False, "error": "Session expired."})
        
    data = request.json
    login_img_b64 = data.get('face_image')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT face_embedding, usn FROM students WHERE id = ?', (session['student_id'],))
    student = cursor.fetchone()
    conn.close()
    
    login_emb_json, error_msg = get_embedding_from_base64(login_img_b64)
    if not login_emb_json:
        return jsonify({"success": False, "error": error_msg})
        
    is_match, distance = verify_face_embeddings(student['face_embedding'], login_emb_json)
    
    if ',' in login_img_b64:
        img_data = base64.b64decode(login_img_b64.split(',')[1])
    else:
        img_data = base64.b64decode(login_img_b64)
        
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    login_img_path = os.path.join('logs', f"login_attempt_{student['usn']}_{timestamp}.jpg")
    with open(login_img_path, 'wb') as f:
        f.write(img_data)
        
    if is_match:
        session['verified'] = True
        return jsonify({"success": True, "confidence": max(0, 1.0 - distance)})
    else:
        log_violation("Identity Mismatch", login_img_path, details=f"Distance: {distance:.2f}")
        return jsonify({"success": False, "error": "Face does not match registered identity."})


# --- EXISTING PROCTORING LOGIC ---

@app.route('/dashboard')
def dashboard():
    if not session.get('verified'): return redirect('/')
    
    # Create Exam Session
    if 'exam_session_id' not in session:
        conn = get_db_connection()
        cursor = conn.cursor()
        start_t = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO exam_sessions (student_id, start_time) VALUES (?, ?)", (session['student_id'], start_t))
        session['exam_session_id'] = cursor.lastrowid
        conn.commit()
        conn.close()
        
    return render_template('dashboard.html')

@app.route('/admin')
def admin():
    from proctoring.analysis import get_admin_dashboard_metrics
    stats = fetch_violation_stats()
    timeline = get_timeline(limit=100)
    global_metrics = get_admin_dashboard_metrics()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT timestamp, details FROM violations WHERE violation_type='Looking Away From Exam Screen'")
    look_away_rows = cursor.fetchall()
    
    # Fetch students for admin
    cursor.execute("SELECT * FROM students")
    students = cursor.fetchall()
    
    # Fetch Exam Sessions
    cursor.execute("SELECT es.*, s.student_name, s.usn FROM exam_sessions es JOIN students s ON es.student_id = s.id ORDER BY es.id DESC")
    exam_sessions = cursor.fetchall()
    
    conn.close()
    
    total_look_away_duration = 0
    latest_look_away = "None"
    for row in look_away_rows:
        latest_look_away = row['timestamp']
        try: total_look_away_duration += float(row['details'].split()[0])
        except: pass
            
    exam_duration = "N/A"
    if 'exam_start' in session:
        dur = time.time() - session['exam_start']
        mins = int(dur // 60)
        secs = int(dur % 60)
        exam_duration = f"{mins}m {secs}s"
        
    admin_data = {
        "student_name": session.get('student_name', 'Unknown'),
        "usn": session.get('usn', 'Unknown'),
        "exam_duration": exam_duration,
        "total_look_away_events": len(look_away_rows),
        "total_look_away_duration": round(total_look_away_duration, 1),
        "latest_look_away": latest_look_away
    }
    
    return render_template('admin.html', stats=stats, timeline=timeline, admin=admin_data, students=students, exam_sessions=exam_sessions, global_metrics=global_metrics)

@app.route('/replay')
def replay():
    session_id = request.args.get('session_id')
    if not session_id: return redirect('/admin')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT es.*, s.student_name, s.usn FROM exam_sessions es JOIN students s ON es.student_id = s.id WHERE es.id = ?", (session_id,))
    exam_session = cursor.fetchone()
    
    cursor.execute("SELECT * FROM violations WHERE session_id = ? ORDER BY timestamp ASC", (session_id,))
    session_violations = cursor.fetchall()
    conn.close()
    
    return render_template('replay.html', exam_session=exam_session, violations=session_violations)

@app.route('/video_feed')
def video_feed():
    s_id = session.get('exam_session_id', None)
    usn = session.get('usn', 'unknown')
    exam_start = session.get('exam_start', time.time())
    return Response(generate_frames(s_id, usn, exam_start), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/gallery')
def gallery():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT v.*, s.student_name, s.usn 
        FROM violations v 
        LEFT JOIN exam_sessions es ON v.session_id = es.id 
        LEFT JOIN students s ON es.student_id = s.id 
        WHERE v.evidence_path IS NOT NULL AND v.evidence_path != '' 
        ORDER BY v.timestamp DESC
    ''')
    evidence = [dict(row) for row in cursor.fetchall()]
    
    cursor.execute("SELECT DISTINCT usn, student_name FROM students")
    filter_students = [dict(row) for row in cursor.fetchall()]
    
    cursor.execute("SELECT DISTINCT violation_type FROM violations WHERE evidence_path IS NOT NULL AND evidence_path != ''")
    filter_types = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    return render_template('gallery.html', evidence=evidence, students=filter_students, types=filter_types)

@app.route('/architecture')
def architecture():
    return render_template('architecture.html')

@app.route('/status')
def status():
    stats = fetch_violation_stats()
    stats["live_warning"] = proctoring_stats["warning"]
    stats["head_direction"] = proctoring_stats["head_direction"]
    stats["active_persons"] = proctoring_stats.get("persons", 0)
    stats["active_phones"] = proctoring_stats.get("phones", 0)
    
    import proctoring.audio_analyzer as aa
    stats["audio_level"] = aa.global_audio_level
    stats["audio_status"] = aa.global_mic_error if aa.global_mic_error else aa.global_audio_status
    
    # If audio is detected and it changed from silence, we could log it
    # But for now we just return the live stats for the dashboard
    if stats["audio_status"] == "Audio Detected":
        # Increment live voice count if needed, or rely on other logic
        pass
        
    return jsonify(stats)

@app.route('/api/timeline')
def api_timeline():
    return jsonify(get_timeline())

@app.route('/log_frontend_violation', methods=['POST'])
def log_frontend_violation():
    global latest_raw_frame
    data = request.json
    v_type = data.get('type', 'Unknown Violation')
    
    evidence_path = None
    if latest_raw_frame is not None:
        evidence_path = save_evidence(latest_raw_frame, v_type)
        
    s_id = session.get('exam_session_id')
    rel_time = time.time() - session.get('exam_start', time.time())
    
    log_violation(v_type, evidence_path, session_id=s_id, relative_timestamp=rel_time)
    return jsonify({"status": "success", "evidence_path": evidence_path})

@app.route('/end_exam', methods=['POST'])
def end_exam():
    s_id = session.get('exam_session_id')
    if not s_id: return jsonify({"success": False})
    
    t = exam_telemetry.get(s_id)
    if t:
        uptime = time.time() - t["start_time"]
        fps = t["total_frames"] / uptime if uptime > 0 else 0
        face_pct = (t["face_frames"] / t["total_frames"] * 100) if t["total_frames"] > 0 else 0
        focus_pct = (t["focused_frames"] / t["total_frames"] * 100) if t["total_frames"] > 0 else 0
        audio_pct = (t["audio_voice"] / t["audio_total"] * 100) if t["audio_total"] > 0 else 0
        
        end_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE exam_sessions SET 
            end_time = ?, fps = ?, camera_uptime = ?, face_visibility_pct = ?, screen_focus_pct = ?, audio_activity_pct = ?
            WHERE id = ?
        ''', (end_time_str, fps, uptime, face_pct, focus_pct, audio_pct, s_id))
        conn.commit()
        conn.close()
        
    return jsonify({"success": True})

@app.route('/generate_ai_report', methods=['POST'])
def generate_ai_report():
    raw_stats = fetch_violation_stats()
    
    ai_stats = {
        "face_absent_count": raw_stats["face_absent"],
        "phone_detected_count": raw_stats["phone"],
        "multiple_person_count": raw_stats["multiple_persons"],
        "look_away_count": raw_stats["look_away"], 
        "tab_switch_count": raw_stats["tab_switch"],
        "risk_score": raw_stats["risk_percentage"],
        "risk_label": raw_stats["risk_label"]
    }
    
    summary = generate_professional_summary(ai_stats)
    save_report_summary(summary)
    
    return jsonify({"status": "success", "summary": summary})

from proctoring.audio_analyzer import start_audio_monitoring

# Start audio monitoring when app starts
start_audio_monitoring()

@app.route('/audio_test')
def audio_test():
    import proctoring.audio_analyzer as aa
    return f"""
    <html>
    <head>
        <title>Audio Test</title>
        <meta http-equiv="refresh" content="1">
    </head>
    <body style="font-family: Arial; padding: 20px;">
        <h2>Backend Microphone Monitor Test</h2>
        <p><strong>Microphone Error:</strong> {aa.global_mic_error}</p>
        <p><strong>Audio Status:</strong> {aa.global_audio_status}</p>
        <p><strong>Live RMS Volume:</strong> {aa.global_audio_level:.4f}</p>
        <div style="width: 300px; height: 30px; background: #eee; margin-top: 10px;">
            <div style="width: {min(aa.global_audio_level * 1000, 100)}%; height: 100%; background: {'red' if aa.global_audio_status == 'Audio Detected' else 'green'};"></div>
        </div>
    </body>
    </html>
    """

@app.route('/api/charts')
def api_charts():
    s_id = request.args.get('session_id')
    from proctoring.analysis import generate_web_charts
    charts = generate_web_charts(s_id)
    return jsonify(charts)

@app.route('/report')
def report():
    stats = fetch_violation_stats()
    summary = get_latest_report_summary()
    
    s_id = session.get('exam_session_id')
    metrics = {}
    if s_id:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT fps, camera_uptime, face_visibility_pct, screen_focus_pct, audio_activity_pct FROM exam_sessions WHERE id = ?", (s_id,))
        row = cursor.fetchone()
        conn.close()
        if row: metrics = dict(row)
        
    return render_template('report.html', stats=stats, summary=summary, metrics=metrics)

@app.route('/download_report')
def download_report():
    stats = fetch_violation_stats()
    summary = get_latest_report_summary()
    
    s_id = session.get('exam_session_id')
    metrics = {}
    if s_id:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT fps, camera_uptime, face_visibility_pct, screen_focus_pct, audio_activity_pct FROM exam_sessions WHERE id = ?", (s_id,))
        row = cursor.fetchone()
        conn.close()
        if row: metrics = dict(row)
        
    pdf_buffer = generate_pdf_report(stats, summary, metrics)
    return send_file(pdf_buffer, as_attachment=True, download_name='exam_report.pdf', mimetype='application/pdf')

@app.route('/export/pdf')
def export_pdf():
    return redirect('/download_report')

@app.route('/export/csv')
def export_csv():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM violations")
    rows = cursor.fetchall()
    conn.close()
    
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['ID', 'Session ID', 'Timestamp', 'Relative Time', 'Violation Type', 'Details', 'Evidence Path'])
    for r in rows:
        cw.writerow([r['id'], r['session_id'], r['timestamp'], r['relative_timestamp'], r['violation_type'], r['details'], r['evidence_path']])
        
    return Response(si.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=violations.csv"})

@app.route('/export/zip')
def export_zip():
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        if os.path.exists('logs'):
            for root, _, files in os.walk('logs'):
                for f in files:
                    zf.write(os.path.join(root, f))
        if os.path.exists('recordings'):
            for root, _, files in os.walk('recordings'):
                for f in files:
                    zf.write(os.path.join(root, f))
    memory_file.seek(0)
    return send_file(memory_file, as_attachment=True, download_name='evidence_bundle.zip', mimetype='application/zip')

@app.route('/logs/<path:filename>')
def serve_logs(filename):
    return send_from_directory('logs', filename)

@app.route('/recordings/<path:filename>')
def serve_recordings(filename):
    return send_from_directory('recordings', filename)

# --- ADMIN PORTAL LOGIC ---

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        admin_id = request.form.get('admin_id')
        password = request.form.get('password')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM admins WHERE admin_id = ?', (admin_id,))
        admin = cursor.fetchone()
        conn.close()
        
        if admin and admin['password_hash'].startswith('$2b$'):
            if bcrypt.checkpw(password.encode('utf-8'), admin['password_hash'].encode('utf-8')):
                session['admin_id'] = admin['admin_id']
                return redirect('/admin')
            
        return render_template('admin_login.html', error="Invalid Admin ID or Password.")
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_id', None)
    return redirect('/admin/login')

@app.route('/admin')
def admin_dashboard():
    if 'admin_id' not in session:
        return redirect('/admin/login')
    return render_template('admin_dashboard.html')

@app.route('/api/admin/dashboard')
def api_admin_dashboard():
    if 'admin_id' not in session: return jsonify({"error": "Unauthorized"}), 401
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM students")
    total_students = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM exam_sessions")
    total_sessions = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM exam_sessions WHERE end_time IS NOT NULL")
    completed_exams = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM violations")
    total_violations = cursor.fetchone()[0]
    
    avg_risk_score = 0
    if total_sessions > 0:
        cursor.execute("SELECT COUNT(*) as v_count FROM violations GROUP BY session_id")
        counts = [row['v_count'] for row in cursor.fetchall()]
        if counts:
            avg_risk = sum(counts) / len(counts) * 10
            avg_risk_score = min(int(avg_risk), 100)
    
    conn.close()
    return jsonify({
        "total_students": total_students,
        "total_sessions": total_sessions,
        "completed_exams": completed_exams,
        "average_risk_score": f"{avg_risk_score}%",
        "total_violations": total_violations
    })

@app.route('/api/admin/students')
def api_admin_students():
    if 'admin_id' not in session: return jsonify({"error": "Unauthorized"}), 401
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, student_name, usn, user_id FROM students")
    students = [dict(r) for r in cursor.fetchall()]
    conn.close()
    
    for s in students:
        s['exam_status'] = 'Completed'
        s['risk_score'] = '15%'
        s['classification'] = 'No Action Required'
    return jsonify(students)

@app.route('/api/admin/violations')
def api_admin_violations():
    if 'admin_id' not in session: return jsonify({"error": "Unauthorized"}), 401
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT timestamp, violation_type, evidence_path, details, session_id FROM violations ORDER BY timestamp DESC LIMIT 200")
    violations = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(violations)

@app.route('/api/admin/analytics')
def api_admin_analytics():
    if 'admin_id' not in session: return jsonify({"error": "Unauthorized"}), 401
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT violation_type, COUNT(*) as count FROM violations GROUP BY violation_type")
    violation_counts = {r['violation_type']: r['count'] for r in cursor.fetchall()}
    conn.close()
    return jsonify({
        "violation_types": violation_counts,
        "risk_distribution": {"0-20%": 15, "21-50%": 5, "51-100%": 2},
        "classifications": {"No Action Required": 15, "Manual Review": 5, "Malpractice": 2}
    })

@app.route('/api/admin/evidence')
def api_admin_evidence():
    if 'admin_id' not in session: return jsonify({"error": "Unauthorized"}), 401
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, session_id, violation_type, evidence_path, timestamp FROM violations WHERE evidence_path IS NOT NULL AND evidence_path != '' ORDER BY timestamp DESC LIMIT 50")
    evidence = [dict(r) for r in cursor.fetchall()]
    conn.close()
    
    from flask import make_response
    response = make_response(jsonify(evidence))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/api/admin/evidence_debug')
def api_admin_evidence_debug():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, evidence_path
    FROM violations
    WHERE evidence_path IS NOT NULL
    AND evidence_path != ''
    ORDER BY timestamp DESC
    LIMIT 50
    """)
    evidence = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(evidence)

@app.route('/api/admin/live')
def api_admin_live():
    if 'admin_id' not in session: return jsonify({"error": "Unauthorized"}), 401
    return jsonify([
        {"student_name": "Live Student A", "usn": "1XX12CS001", "current_risk": "8%", "current_warning": "Safe"}
    ])

@app.route('/delete_evidence/<int:id>', methods=['POST'])
def delete_evidence(id):
    print("DELETE ROUTE HIT")
    print("ADMIN SESSION:", session.get("admin_id"))
    
    if 'admin_id' not in session: return jsonify({"error": "Unauthorized"}), 401
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM violations WHERE evidence_path IS NOT NULL AND evidence_path != ''")
    count_before = cursor.fetchone()[0]
    print(f"Evidence gallery records count before delete: {count_before}")
    
    print(f"Deleting evidence ID: {id}")
    cursor.execute("SELECT evidence_path FROM violations WHERE id = ?", (id,))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return jsonify({"success": False, "message": "Evidence not found"})
        
    if row and row['evidence_path']:
        evidence_path = row['evidence_path']
        if os.path.exists(evidence_path):
            try:
                os.remove(evidence_path)
                print(f"Deleted image: {evidence_path}")
            except Exception as e:
                print(f"Failed to delete {evidence_path}: {str(e)}")
        else:
            print(f"File missing on disk, continuing cleanup: {evidence_path}")
        
        cursor.execute("UPDATE violations SET evidence_path = NULL WHERE id = ?", (id,))
        print("ROWS UPDATED:", cursor.rowcount)
        conn.commit()
        print(f"Deleted database record: {id}")
        
    cursor.execute("SELECT COUNT(*) FROM violations WHERE evidence_path IS NOT NULL AND evidence_path != ''")
    count_after = cursor.fetchone()[0]
    print(f"Evidence gallery records count after delete: {count_after}")
    
    conn.close()
    return jsonify({"success": True, "message": "Evidence deleted successfully"})

@app.route('/api/admin/evidence/clear', methods=['POST'])
def api_admin_evidence_clear():
    if 'admin_id' not in session: return jsonify({"error": "Unauthorized"}), 401
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM violations WHERE evidence_path IS NOT NULL AND evidence_path != ''")
    count_before = cursor.fetchone()[0]
    print(f"Evidence gallery records count before delete: {count_before}")
    
    import shutil
    for d in ['logs', 'recordings', 'evidence']:
        if os.path.exists(d):
            for filename in os.listdir(d):
                file_path = os.path.join(d, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.remove(file_path)
                        print(f"Deleted image: {file_path}")
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception:
                    pass
                    
    cursor.execute("UPDATE violations SET evidence_path = NULL")
    conn.commit()
    print("Deleted all database records (evidence_path cleared)")
    
    cursor.execute("SELECT COUNT(*) FROM violations WHERE evidence_path IS NOT NULL AND evidence_path != ''")
    count_after = cursor.fetchone()[0]
    print(f"Evidence gallery records count after delete: {count_after}")
    
    conn.close()
    return jsonify({"success": True, "message": "Evidence deleted successfully"})

if __name__ == '__main__':
    app.run(debug=True, port=5000, threaded=True)
