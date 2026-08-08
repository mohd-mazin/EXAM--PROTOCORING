import json
import base64
import os
import cv2
import numpy as np
import torch
from transformers import ViTImageProcessor, ViTModel
from PIL import Image

print("--- AUDITING FACE RECOGNITION PIPELINE ---")

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
processor = ViTImageProcessor.from_pretrained('google/vit-base-patch16-224-in21k')
model = ViTModel.from_pretrained('google/vit-base-patch16-224-in21k').to(device).eval()

# Load cascade for face detection
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

def process_face(img_path, debug_name):
    print(f"\nProcessing {img_path}...")
    img = cv2.imread(img_path)
    if img is None:
        print("Failed to load image.")
        return None, "File error"
        
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(100, 100))
    
    print(f"Faces detected: {len(faces)}")
    if len(faces) == 0:
        return None, "Face not detected."
    if len(faces) > 1:
        return None, "Multiple faces detected. Only one face must be visible."
        
    x, y, w, h = faces[0]
    
    # Add a 20% margin around the face to capture context
    margin_x = int(w * 0.2)
    margin_y = int(h * 0.2)
    x1 = max(0, x - margin_x)
    y1 = max(0, y - margin_y)
    x2 = min(img.shape[1], x + w + margin_x)
    y2 = min(img.shape[0], y + h + margin_y)
    
    cropped_face = img[y1:y2, x1:x2]
    cv2.imwrite(debug_name, cropped_face)
    print(f"Saved cropped debug image: {debug_name}")
    
    cropped_rgb = cv2.cvtColor(cropped_face, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(cropped_rgb)
    
    inputs = processor(images=pil_img, return_tensors="pt").to(device)
    with torch.no_grad():
        outputs = model(**inputs)
        embedding = outputs.pooler_output.cpu().numpy()[0]
        
    print(f"Embedding generated. Length: {len(embedding)}")
    return embedding, "Success"

def test_thresholds(emb1, emb2):
    dot_product = np.dot(emb1, emb2)
    norm_a = np.linalg.norm(emb1)
    norm_b = np.linalg.norm(emb2)
    
    cosine_similarity = dot_product / (norm_a * norm_b)
    print(f"\nCosine Similarity Score: {cosine_similarity:.4f}")
    
    thresholds = [0.50, 0.60, 0.70, 0.75, 0.85]
    print("\nThreshold Tests:")
    for t in thresholds:
        result = "PASS" if cosine_similarity > t else "FAIL"
        print(f"Threshold: {t:.2f} -> {result}")

# Find test images from logs
reg_img = "logs/reg_20241CSE05061.jpg"
login_img = "logs/login_attempt_20241CSE05061_20260612_034814.jpg"

print("\n1. Registration Audit")
emb_reg, msg_reg = process_face(reg_img, "debug_registered_face.jpg")

print("\n2. Verification Audit")
emb_login, msg_login = process_face(login_img, "debug_live_face.jpg")

if emb_reg is not None and emb_login is not None:
    print("\n3. Similarity Debugging")
    test_thresholds(emb_reg, emb_login)
else:
    print(f"Cannot compare: Reg={msg_reg}, Login={msg_login}")
