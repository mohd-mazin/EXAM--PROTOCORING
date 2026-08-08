import cv2
import mediapipe as mp
import numpy as np

print("MediaPipe version:", getattr(mp, '__version__', 'unknown'))

class GazeTracker:
    def __init__(self):
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            min_detection_confidence=0.5, 
            min_tracking_confidence=0.5,
            refine_landmarks=True
        )
        
    def process_frame(self, image):
        # Convert the color space from BGR to RGB
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        image_rgb.flags.writeable = False
        results = self.face_mesh.process(image_rgb)
        
        direction = "Focused"
        
        if results.multi_face_landmarks:
            for face_landmarks in results.multi_face_landmarks:
                img_h, img_w, img_c = image.shape
                face_3d = []
                face_2d = []
                
                # specific landmarks for head pose
                # Nose tip: 1, Chin: 152, Left eye: 33, Right eye: 263, Left mouth: 61, Right mouth: 291
                landmarks = [1, 152, 33, 263, 61, 291]
                for idx in landmarks:
                    lm = face_landmarks.landmark[idx]
                    x, y = int(lm.x * img_w), int(lm.y * img_h)
                    face_2d.append([x, y])
                    face_3d.append([x, y, lm.z])
                
                # Get 2d/3d numpy arrays
                face_2d = np.array(face_2d, dtype=np.float64)
                face_3d = np.array(face_3d, dtype=np.float64)
                
                focal_length = 1 * img_w
                cam_matrix = np.array([[focal_length, 0, img_w / 2],
                                       [0, focal_length, img_h / 2],
                                       [0, 0, 1]])
                dist_matrix = np.zeros((4, 1), dtype=np.float64)
                
                success, rot_vec, trans_vec = cv2.solvePnP(face_3d, face_2d, cam_matrix, dist_matrix)
                rmat, jac = cv2.Rodrigues(rot_vec)
                angles, mtxR, mtxQ, Qx, Qy, Qz = cv2.RQDecomp3x3(rmat)
                
                x_angle = angles[0] * 360
                y_angle = angles[1] * 360
                
                if y_angle < -10:
                    direction = "Looking Left"
                elif y_angle > 10:
                    direction = "Looking Right"
                elif x_angle < -10:
                    direction = "Looking Down"
                elif x_angle > 10:
                    direction = "Looking Up"
                else:
                    direction = "Focused"
                    
                break # only care about one face for gaze
                
        return direction
