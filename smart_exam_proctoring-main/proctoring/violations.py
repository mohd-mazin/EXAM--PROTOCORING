from database import get_db_connection
import datetime
import os
# pyrefly: ignore [missing-import]
import cv2

class ViolationLogger:
    def __init__(self):
        self.logs_dir = 'logs/violations'
        os.makedirs(self.logs_dir, exist_ok=True)

    def log_violation(self, student_id, violation_type, frame=None):
        """
        Log a violation to the database and optionally save a snapshot
        """
        image_path = None
        
        if frame is not None:
            timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"violation_{student_id}_{timestamp_str}.jpg"
            image_path = os.path.join(self.logs_dir, filename)
            cv2.imwrite(image_path, frame)
            
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO violations (student_id, violation_type, image_path)
            VALUES (?, ?, ?)
        ''', (student_id, violation_type, image_path))
        
        conn.commit()
        conn.close()
        
        print(f"Logged violation: {violation_type} for student {student_id}")
        return True
