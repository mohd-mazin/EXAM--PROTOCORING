import torch
from transformers import ViTImageProcessor, ViTModel
from PIL import Image
import io
import base64
import json
import numpy as np

# Use Vision Transformer (ViT) to extract deep embeddings of the webcam face crop
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
processor = ViTImageProcessor.from_pretrained('google/vit-base-patch16-224-in21k')
model = ViTModel.from_pretrained('google/vit-base-patch16-224-in21k').to(device).eval()

import cv2

# Load OpenCV face detector
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

def get_embedding_from_base64(b64_string):
    """Takes a base64 encoded image string and returns (json_string, error_msg)."""
    try:
        if ',' in b64_string:
            b64_string = b64_string.split(',')[1]
        img_data = base64.b64decode(b64_string)
        
        # Convert to cv2 image for face detection
        np_arr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if img is None:
            return None, "Invalid image data."
            
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(100, 100))
        
        if len(faces) == 0:
            return None, "Face not detected."
        if len(faces) > 1:
            return None, "Multiple faces detected. Only one face must be visible."
            
        x, y, w, h = faces[0]
        
        # Add a 20% margin around the face
        margin_x = int(w * 0.2)
        margin_y = int(h * 0.2)
        x1 = max(0, x - margin_x)
        y1 = max(0, y - margin_y)
        x2 = min(img.shape[1], x + w + margin_x)
        y2 = min(img.shape[0], y + h + margin_y)
        
        cropped_face = img[y1:y2, x1:x2]
        
        # Save debug images
        cv2.imwrite("debug_face_crop.jpg", cropped_face)
        
        # Convert back to PIL for ViT
        cropped_rgb = cv2.cvtColor(cropped_face, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(cropped_rgb)
        
        inputs = processor(images=pil_img, return_tensors="pt").to(device)
        
        with torch.no_grad():
            outputs = model(**inputs)
            # Use the pooled output
            embedding = outputs.pooler_output.cpu().numpy()[0]
            
        return json.dumps(embedding.tolist()), "Success"
    except Exception as e:
        print(f"Face Error: {e}")
        return None, str(e)

def verify_face_embeddings(emb_json1, emb_json2, threshold=0.70):
    """Compares two JSON embedding strings via cosine similarity."""
    try:
        emb1 = np.array(json.loads(emb_json1))
        emb2 = np.array(json.loads(emb_json2))
        
        dot_product = np.dot(emb1, emb2)
        norm_a = np.linalg.norm(emb1)
        norm_b = np.linalg.norm(emb2)
        
        cosine_similarity = dot_product / (norm_a * norm_b)
        distance = 1 - cosine_similarity
        
        # High similarity required for face match (dist < 0.15)
        is_match = cosine_similarity > threshold
        return bool(is_match), float(distance)
    except Exception as e:
        print(f"Verification Error: {e}")
        return False, 1.0
