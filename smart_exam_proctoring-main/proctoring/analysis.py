import sqlite3
import os
import io
import textwrap
import pandas as pd
import base64

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from database import DB_PATH

def fetch_violation_stats():
    """Reads violations from DB and computes basic stats and risk score."""
    if not os.path.exists(DB_PATH):
        return {"total": 0, "phone": 0, "face_absent": 0, "multiple_persons": 0, "risk_percentage": 0, "risk_label": "SAFE"}
        
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT violation_type, COUNT(*) as count FROM violations GROUP BY violation_type")
        rows = cursor.fetchall()
    except Exception:
        rows = []
    conn.close()
    
    stats = {
        "phone": 0,
        "face_absent": 0,
        "multiple_persons": 0,
        "look_away": 0,
        "multiple_voice": 0,
        "tab_switch": 0,
        "fullscreen": 0,
        "right_click": 0,
        "browser_manipulation": 0,
        "external_audio": 0,
        "identity_mismatch": 0
    }
    
    for row in rows:
        v_type = row[0]
        count = row[1]
        if v_type == "Mobile Phone Detected":
            stats["phone"] = count
        elif v_type == "Face Absent":
            stats["face_absent"] = count
        elif v_type == "Multiple Persons Detected":
            stats["multiple_persons"] = count
        elif v_type == "Identity Mismatch":
            stats["identity_mismatch"] = count
        elif v_type == "Tab Switch Detected":
            stats["tab_switch"] = count
        elif v_type == "Fullscreen Violation":
            stats["fullscreen"] = count
        elif v_type == "Restricted Key Attempt":
            stats["restricted_key"] = count
        elif v_type == "Right Click Attempt":
            stats["right_click"] = count
        elif v_type == "Browser Manipulation Detected":
            stats["browser_manipulation"] = count
        elif v_type == "Looking Away From Exam Screen":
            stats["look_away"] = count
        elif v_type == "Multiple Voices Detected":
            stats["multiple_voice"] = count
        elif v_type == "External Audio Detected":
            stats["external_audio"] = count
            
    total = sum(stats.values())
    
    # New Risk Score Formula based on Severity Levels
    # CRITICAL: 100, HIGH: 25, MEDIUM: 10, LOW: 5
    risk = (stats["phone"] * 25 +                   # HIGH
            stats["multiple_persons"] * 25 +        # HIGH
            stats["multiple_voice"] * 25 +          # HIGH
            stats["external_audio"] * 25 +          # HIGH
            stats["identity_mismatch"] * 100 +      # CRITICAL
            stats["face_absent"] * 10 +             # MEDIUM
            stats["tab_switch"] * 10 +              # MEDIUM
            stats["fullscreen"] * 10 +              # MEDIUM
            stats["restricted_key"] * 10 +          # MEDIUM
            stats["browser_manipulation"] * 10 +    # MEDIUM
            stats["right_click"] * 10 +             # MEDIUM
            stats["look_away"] * 5)                 # LOW
            
    risk = min(risk, 100) # cap at 100%
    
    risk_label = "SAFE"
    if risk >= 21:
        risk_label = "SUSPICIOUS"
    if risk >= 51:
        risk_label = "HIGH RISK"
        
    return {
        "total": total,
        "phone": stats["phone"],
        "face_absent": stats["face_absent"],
        "multiple_persons": stats["multiple_persons"],
        "tab_switch": stats["tab_switch"],
        "fullscreen": stats["fullscreen"],
        "restricted_key": stats["restricted_key"],
        "voice": stats["multiple_voice"],
        "external_audio": stats["external_audio"],
        "identity_mismatch": stats["identity_mismatch"],
        "look_away": stats["look_away"],
        "risk_percentage": risk,
        "risk_label": risk_label
    }

def get_admin_dashboard_metrics():
    if not os.path.exists(DB_PATH): return {}
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT COUNT(*) FROM students")
        total_students = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM exam_sessions WHERE end_time IS NULL")
        active_exams = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM exam_sessions WHERE end_time IS NOT NULL")
        completed_exams = cursor.fetchone()[0]
        
        cursor.execute("SELECT id FROM students")
        students = cursor.fetchall()
        
        student_risks = []
        top_violations = {}
        high_risk_count = 0
        total_risk = 0
        
        for (s_id,) in students:
            cursor.execute("SELECT id FROM exam_sessions WHERE student_id = ? ORDER BY id DESC LIMIT 1", (s_id,))
            sess = cursor.fetchone()
            if not sess: continue
            
            session_id = sess[0]
            cursor.execute("SELECT violation_type, COUNT(*) FROM violations WHERE session_id = ? GROUP BY violation_type", (session_id,))
            v_rows = cursor.fetchall()
            
            risk = 0
            for v_type, count in v_rows:
                top_violations[v_type] = top_violations.get(v_type, 0) + count
                
                if v_type == "Mobile Phone Detected": risk += 25 * count
                elif v_type == "Multiple Persons Detected": risk += 25 * count
                elif v_type == "Multiple Voices Detected": risk += 25 * count
                elif v_type == "External Audio Detected": risk += 25 * count
                elif v_type == "Identity Mismatch": risk += 100 * count
                elif v_type == "Face Absent": risk += 10 * count
                elif v_type == "Tab Switch Detected": risk += 10 * count
                elif v_type == "Fullscreen Violation": risk += 10 * count
                elif v_type == "Restricted Key Attempt": risk += 10 * count
                elif v_type == "Browser Manipulation Detected": risk += 10 * count
                elif v_type == "Right Click Attempt": risk += 10 * count
                elif v_type == "Looking Away From Exam Screen": risk += 5 * count
                
            risk = min(risk, 100)
            total_risk += risk
            if risk >= 51: high_risk_count += 1
            student_risks.append({"student_id": s_id, "risk": risk})
            
        avg_risk = total_risk / len(student_risks) if student_risks else 0
        sorted_top = sorted(top_violations.items(), key=lambda x: x[1], reverse=True)[:5]
        top_v_list = [{"type": k, "count": v} for k, v in sorted_top]
        
    except Exception as e:
        return {}
    finally:
        conn.close()
        
    return {
        "total_students": total_students,
        "active_exams": active_exams,
        "completed_exams": completed_exams,
        "high_risk_count": high_risk_count,
        "average_risk": round(avg_risk, 1),
        "top_violations": top_v_list,
        "student_risks": student_risks
    }

def generate_web_charts(session_id=None):
    """Generates the 6 requested charts as base64 images for web rendering."""
    if not os.path.exists(DB_PATH): return {}
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT timestamp, violation_type, details FROM violations"
    if session_id:
        query += f" WHERE session_id = {session_id}"
    query += " ORDER BY timestamp ASC"
    
    try:
        df = pd.read_sql_query(query, conn)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    
    if df.empty: return {}
    
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    def get_b64(fig):
        plt.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        plt.close(fig)
        return "data:image/png;base64," + base64.b64encode(buf.read()).decode('utf-8')
        
    charts = {}
    
    # 1. Violations by Type
    fig1, ax1 = plt.subplots(figsize=(6, 4))
    counts = df['violation_type'].value_counts()
    counts.plot(kind='bar', ax=ax1, color='#3498db')
    ax1.set_title("Violations by Type")
    charts['type'] = get_b64(fig1)
    
    # 2. Risk Score Trend
    fig2, ax2 = plt.subplots(figsize=(6, 4))
    risk_values = []
    current_risk = 0
    for v_type in df['violation_type']:
        if v_type == "Mobile Phone Detected": current_risk += 20
        elif v_type == "Face Absent": current_risk += 10
        elif v_type == "Multiple Persons": current_risk += 25
        elif v_type == "Tab Switch Detected": current_risk += 15
        elif v_type == "Multiple Voices Detected": current_risk += 15
        elif v_type == "Fullscreen Violation": current_risk += 10
        else: current_risk += 5
        risk_values.append(min(current_risk, 100))
    df['risk_score'] = risk_values
    ax2.plot(df['timestamp'], df['risk_score'], marker='o', color='#e74c3c')
    ax2.set_title("Risk Score Trend")
    fig2.autofmt_xdate()
    charts['risk'] = get_b64(fig2)
    
    # 3. Look Away Duration
    look_aways = df[df['violation_type'] == 'Looking Away From Exam Screen'].copy()
    if not look_aways.empty:
        durations = []
        for d in look_aways['details']:
            try:
                durations.append(float(d.split()[0]))
            except:
                durations.append(0)
        look_aways['duration'] = durations
        fig3, ax3 = plt.subplots(figsize=(6, 4))
        ax3.bar(look_aways['timestamp'].dt.strftime('%H:%M:%S'), look_aways['duration'], color='#f39c12')
        ax3.set_title("Look Away Duration (sec)")
        plt.xticks(rotation=45)
        charts['look_away'] = get_b64(fig3)
        
    # 4. Timeline Events
    fig4, ax4 = plt.subplots(figsize=(8, 4))
    y_vals = df['violation_type'].astype('category').cat.codes
    labels = df['violation_type'].astype('category').cat.categories
    ax4.scatter(df['timestamp'], y_vals, c=y_vals, cmap='viridis', s=100)
    ax4.set_yticks(range(len(labels)))
    ax4.set_yticklabels(labels)
    ax4.set_title("Timeline Events")
    fig4.autofmt_xdate()
    charts['timeline'] = get_b64(fig4)
    
    # 5 & 6. Identity Mismatch & Voice Violations
    subset = df[df['violation_type'].isin(['Identity Mismatch', 'Multiple Voices Detected'])]
    if not subset.empty:
        fig5, ax5 = plt.subplots(figsize=(6, 4))
        scounts = subset['violation_type'].value_counts()
        scounts.plot(kind='pie', ax=ax5, autopct='%1.1f%%', colors=['#9b59b6', '#e67e22'])
        ax5.set_ylabel('')
        ax5.set_title("Identity & Voice Events")
        charts['identity_voice'] = get_b64(fig5)
        
    return charts

def generate_pdf_report(stats, summary, metrics=None):
    """Generates a PDF using reportlab to a memory buffer."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    c.setFont("Helvetica-Bold", 20)
    c.drawString(50, height - 50, "Smart Exam Proctoring - Final Report")
    
    c.setFont("Helvetica", 12)
    c.drawString(50, height - 90, "AI Generated Exam Summary:")
    
    # Wrap text manually
    wrapped_summary = textwrap.wrap(summary, width=80)
    y = height - 110
    for line in wrapped_summary:
        c.drawString(50, y, line)
        y -= 20
        
    y -= 10
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Risk Score Explanation:")
    y -= 20
    
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "Violation Type")
    c.drawString(250, y, "Severity")
    c.drawString(350, y, "Count")
    c.drawString(450, y, "Penalty")
    y -= 15
    c.setFont("Helvetica", 10)
    
    explanation_rows = [
        ("Mobile Phone Detected", "HIGH", stats.get("phone", 0), 25),
        ("Multiple Persons Detected", "HIGH", stats.get("multiple_persons", 0), 25),
        ("Identity Mismatch", "CRITICAL", stats.get("identity_mismatch", 0), 100),
        ("Face Absent", "MEDIUM", stats.get("face_absent", 0), 10),
        ("Looking Away", "LOW", stats.get("look_away", 0), 5),
        ("Multiple Voices Detected", "HIGH", stats.get("voice", 0), 25),
        ("External Audio", "HIGH", stats.get("external_audio", 0), 25),
        ("Tab Switch", "MEDIUM", stats.get("tab_switch", 0), 10),
        ("Fullscreen Exit", "MEDIUM", stats.get("fullscreen", 0), 10),
        ("Restricted Key", "MEDIUM", stats.get("restricted_key", 0), 10)
    ]
    
    total_calc_risk = 0
    for v_name, sev, count, weight in explanation_rows:
        if count > 0:
            penalty = count * weight
            total_calc_risk += penalty
            c.drawString(50, y, v_name)
            c.drawString(250, y, sev)
            c.drawString(350, y, str(count))
            c.drawString(450, y, f"+{penalty}")
            y -= 15
            
    y -= 5
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, f"Total Risk Score = {stats['risk_percentage']} (Calculated: {total_calc_risk})")
    y -= 20
    
    if y < 100:
        c.showPage()
        y = height - 50
        
    if metrics:
        y -= 10
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y, "Exam Health Metrics:")
        y -= 20
        c.setFont("Helvetica", 10)
        c.drawString(50, y, f"Average FPS: {metrics.get('fps', 0):.1f}")
        c.drawString(200, y, f"Camera Uptime: {metrics.get('camera_uptime', 0):.1f}s")
        y -= 15
        c.drawString(50, y, f"Face Visibility: {metrics.get('face_visibility_pct', 0):.1f}%")
        c.drawString(200, y, f"Screen Focus: {metrics.get('screen_focus_pct', 0):.1f}%")
        y -= 15
        c.drawString(50, y, f"Audio Activity: {metrics.get('audio_activity_pct', 0):.1f}%")
        y -= 10
        
    y -= 20
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Violation Statistics:")
    
    y -= 25
    c.setFont("Helvetica", 12)
    c.drawString(50, y, f"Total Violations: {stats['total']}")
    y -= 20
    c.drawString(50, y, f"Mobile Phone Detected: {stats['phone']}")
    y -= 20
    c.drawString(50, y, f"Face Absent: {stats['face_absent']}")
    y -= 20
    c.drawString(50, y, f"Multiple Persons: {stats['multiple_persons']}")
    y -= 20
    c.drawString(50, y, f"Tab Switches: {stats['tab_switch']}")
    y -= 20
    c.drawString(50, y, f"Fullscreen Exits: {stats['fullscreen']}")
    y -= 20
    c.drawString(50, y, f"Voice Violations: {stats['voice']}")
    
    y -= 30
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, f"Final Risk Score: {stats['risk_percentage']}% ({stats['risk_label']})")
    
    # Generate Matplotlib Charts for PDF
    charts = generate_web_charts()
    
    # Append visual analysis pages
    c.showPage()
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, height - 50, "Visual Analysis")
    
    if 'type' in charts:
        img_type = ImageReader(io.BytesIO(base64.b64decode(charts['type'].split(',')[1])))
        c.drawImage(img_type, 50, height - 300, width=400, height=220)
        
    if 'timeline' in charts:
        img_tl = ImageReader(io.BytesIO(base64.b64decode(charts['timeline'].split(',')[1])))
        c.drawImage(img_tl, 50, height - 550, width=500, height=220)
        
    if 'risk' in charts or 'identity_voice' in charts:
        c.showPage()
        c.setFont("Helvetica-Bold", 18)
        c.drawString(50, height - 50, "Visual Analysis (Cont.)")
        if 'risk' in charts:
            img_risk = ImageReader(io.BytesIO(base64.b64decode(charts['risk'].split(',')[1])))
            c.drawImage(img_risk, 50, height - 300, width=400, height=220)
        if 'identity_voice' in charts:
            img_iv = ImageReader(io.BytesIO(base64.b64decode(charts['identity_voice'].split(',')[1])))
            c.drawImage(img_iv, 50, height - 550, width=400, height=220)
            
    c.save()
    buffer.seek(0)
    return buffer
