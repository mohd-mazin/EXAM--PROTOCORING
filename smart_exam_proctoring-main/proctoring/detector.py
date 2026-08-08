import cv2
from ultralytics import YOLO

# Initialize the YOLO model globally
try:
    # YOLO automatically downloads the model if it's missing in the current directory
    model = YOLO("yolov8n.pt")
    print("Model yolov8n.pt loaded successfully.")
except Exception as e:
    print(f"Error loading model: {e}")
    model = None

def detect_frame(frame):
    """
    Analyze a frame to detect persons and cell phones.
    Draws bounding boxes and returns counts.
    """
    person_count = 0
    phone_count = 0
    person_conf = 0.0
    phone_conf = 0.0
    
    # Work on a copy to draw bounding boxes
    processed_frame = frame.copy()
    
    if model:
        # Run YOLOv8 inference with a confidence threshold of 0.25
        results = model(processed_frame, conf=0.25, verbose=False)
        
        for r in results:
            boxes = r.boxes
            for box in boxes:
                cls = int(box.cls[0])
                # COCO classes: 0 = person, 67 = cell phone
                if cls == 0 or cls == 67:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    conf = float(box.conf[0])
                    
                    if cls == 0:
                        person_count += 1
                        if conf > person_conf: person_conf = conf
                        cv2.rectangle(processed_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        cv2.putText(processed_frame, f'Person {conf:.2f}', (x1, y1 - 10), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                        print(f"YOLO Log: Detected Person (Confidence: {conf:.2f})")
                    elif cls == 67:
                        phone_count += 1
                        if conf > phone_conf: phone_conf = conf
                        cv2.rectangle(processed_frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                        cv2.putText(processed_frame, f'Phone {conf:.2f}', (x1, y1 - 10), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                        print(f"YOLO Log: Detected Mobile Phone (Confidence: {conf:.2f})")
                        
    return {
        "persons": person_count,
        "phones": phone_count,
        "person_conf": person_conf,
        "phone_conf": phone_conf,
        "frame": processed_frame
    }

# Local webcam capture test
if __name__ == "__main__":
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        exit()
        
    print("Starting webcam... Press 'q' to quit.")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Could not read frame from webcam.")
            break
            
        result = detect_frame(frame)
        
        # Show stats on the frame
        cv2.putText(result["frame"], f"Persons: {result['persons']}", (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
        cv2.putText(result["frame"], f"Phones: {result['phones']}", (10, 70), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
        
        cv2.imshow("Proctoring Detector", result["frame"])
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
            
    cap.release()
    cv2.destroyAllWindows()
