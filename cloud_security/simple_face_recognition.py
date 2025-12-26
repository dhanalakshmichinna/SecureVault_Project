import cv2
import numpy as np
import os
from django.conf import settings

class SimpleFaceRecognition:
    def __init__(self):
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    
    def detect_face(self, image_path):
        img = cv2.imread(image_path)
        if img is None:
            return [], None
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)
        return faces, img
    
    def extract_face_features(self, face_roi):
        # Simple feature extraction - resize and flatten
        resized_face = cv2.resize(face_roi, (50, 50))
        gray_face = cv2.cvtColor(resized_face, cv2.COLOR_BGR2GRAY)
        return gray_face.flatten()
    
    def register_face(self, image_path, user_id):
        faces, img = self.detect_face(image_path)
        if len(faces) > 0:
            x,y,w,h = faces[0]
            face_roi = img[y:y+h, x:x+w]
            face_features = self.extract_face_features(face_roi)
            
            # Save face features
            face_data_path = os.path.join(settings.MEDIA_ROOT, 'face_data', f'user_{user_id}.npy')
            os.makedirs(os.path.dirname(face_data_path), exist_ok=True)
            np.save(face_data_path, face_features)
            return True
        return False
    
    def verify_face(self, image_path, user_id):
        faces, img = self.detect_face(image_path)
        if len(faces) > 0:
            x,y,w,h = faces[0]
            face_roi = img[y:y+h, x:x+w]
            current_features = self.extract_face_features(face_roi)
            
            # Load registered features
            registered_face_path = os.path.join(settings.MEDIA_ROOT, 'face_data', f'user_{user_id}.npy')
            if os.path.exists(registered_face_path):
                registered_features = np.load(registered_face_path)
                
                # Calculate similarity (Euclidean distance)
                similarity = np.linalg.norm(registered_features - current_features)
                return similarity < 1000  # Adjust threshold as needed
        return False