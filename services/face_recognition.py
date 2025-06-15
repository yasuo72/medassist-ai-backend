import os
import json
import numpy as np
from deepface import DeepFace
from PIL import Image
import io
import base64
from datetime import datetime
import time
from utils.logger import setup_logger

class FaceRecognitionService:
    def __init__(self, storage_path='face_data', threshold=0.6, timeout=30):
        """
        Initialize the face recognition service
        
        Args:
            storage_path (str): Path to store face data
            threshold (float): Distance threshold for face matching
            timeout (int): Maximum time to wait for face processing
        """
        self.logger = setup_logger()
        self.storage_path = storage_path
        self.threshold = threshold
        self.timeout = timeout
        
        # Create storage directories
        os.makedirs(self.storage_path, exist_ok=True)
        os.makedirs(os.path.join(self.storage_path, 'images'), exist_ok=True)
        
        self.face_embeddings = {}
        self.load_existing_embeddings()
        
    def ping(self):
        """Check if service is healthy"""
        try:
            # Create a temporary test image
            test_img = Image.new('RGB', (100, 100), color='white')
            test_path = os.path.join(self.storage_path, 'test_health_check.jpg')
            test_img.save(test_path)
            
            # Try a basic face detection
            result = DeepFace.analyze(img_path=test_path, actions=['emotion'])
            
            # Clean up
            os.remove(test_path)
            
            return True
        except Exception as e:
            self.logger.error(f"Service health check failed: {str(e)}")
            raise Exception("Face recognition service unavailable")
            
    def _process_with_timeout(self, func, *args, **kwargs):
        """Process function with timeout"""
        start_time = time.time()
        result = None
        
        try:
            # Check if timeout is exceeded
            if time.time() - start_time > self.timeout:
                raise TimeoutError(f"Operation timed out after {self.timeout} seconds")
            
            result = func(*args, **kwargs)
            
            # Check timeout again after operation
            if time.time() - start_time > self.timeout:
                raise TimeoutError(f"Operation took too long: {time.time() - start_time:.2f} seconds")
        except TimeoutError as te:
            self.logger.error(f"Timeout error: {str(te)}")
            raise
        except Exception as e:
            self.logger.error(f"Processing failed: {str(e)}")
            raise
        
        elapsed_time = time.time() - start_time
        if elapsed_time > self.timeout:
            self.logger.warning(f"Processing took too long: {elapsed_time:.2f}s")
            raise TimeoutError(f"Processing took longer than {self.timeout}s")
            
        return result

    def load_existing_embeddings(self):
        """Load existing face embeddings from storage"""
        try:
            embeddings_file = os.path.join(self.storage_path, 'embeddings.json')
            if os.path.exists(embeddings_file):
                with open(embeddings_file, 'r') as f:
                    self.face_embeddings = json.load(f)
                    self.logger.info(f"Loaded {len(self.face_embeddings)} face embeddings")
            else:
                self.face_embeddings = {}
                self.logger.info("No existing embeddings found")
        except Exception as e:
            self.logger.error(f"Error loading embeddings: {str(e)}")
            self.face_embeddings = {}

    def save_embeddings(self):
        """Save face embeddings to storage"""
        try:
            embeddings_file = os.path.join(self.storage_path, 'embeddings.json')
            with open(embeddings_file, 'w') as f:
                json.dump(self.face_embeddings, f)
            self.logger.info(f"Saved {len(self.face_embeddings)} face embeddings")
        except Exception as e:
            self.logger.error(f"Error saving embeddings: {str(e)}")

    def save_image(self, user_id, image_data, prefix='reg'):
        """
        Save image to storage
        
        Args:
            user_id (str): User ID
            image_data (str): Base64 encoded image
            prefix (str): Prefix for image filename
            
        Returns:
            str: Path to saved image
        """
        try:
            image = Image.open(io.BytesIO(base64.b64decode(image_data)))
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{prefix}_{user_id}_{timestamp}.jpg"
            filepath = os.path.join(self.storage_path, 'images', filename)
            
            image.save(filepath)
            self.logger.info(f"Saved image: {filename}")
            return filepath
        except Exception as e:
            self.logger.error(f"Error saving image: {str(e)}")
            return None

    def register_face(self, user_id, image_data, metadata=None):
        """
        Register a new face
        
        Args:
            user_id (str): User identifier
            image_data (str): Base64 encoded image
            metadata (dict): Additional user metadata
            
        Returns:
            dict: Registration result
        """
        try:
            # Validate input
            if not isinstance(user_id, str):
                raise ValueError("user_id must be a string")
                
            if not isinstance(image_data, str):
                raise ValueError("image_data must be a base64 encoded string")
                
            # Process with timeout
            result = self._process_with_timeout(self._register_face, user_id, image_data, metadata)
            return result
            
        except ValueError as ve:
            self.logger.error(f"Validation error for user {user_id}: {str(ve)}")
            raise
            
        except TimeoutError as te:
            self.logger.error(f"Timeout error for user {user_id}: {str(te)}")
            raise
            
        except Exception as e:
            self.logger.error(f"Error registering face for user {user_id}: {str(e)}")
            raise
            
    def _register_face(self, user_id, image_data, metadata):
        """Internal method to register face"""
        try:
            # Convert base64 image to PIL Image
            image_bytes = base64.b64decode(image_data)
            image = Image.open(io.BytesIO(image_bytes))
            
            # Save image to storage
            image_path = os.path.join(self.storage_path, 'images', f'{user_id}.jpg')
            image.save(image_path)
            
            # Extract face embeddings
            embedding = DeepFace.represent(
                img_path=image_path,
                model_name='Facenet',
                enforce_detection=False
            )
            
            # Store embeddings with metadata
            self.face_embeddings[user_id] = {
                'embedding': embedding,
                'metadata': metadata,
                'last_updated': datetime.now().isoformat()
            }
            
            # Save to disk
            self._save_embeddings()
            
            return {
                'status': 'success',
                'message': 'Face registered successfully',
                'user_id': user_id
            }
        except Exception as e:
            self.logger.error(f"Error in face registration for user {user_id}: {str(e)}")
            raise
            
            # Save image
            image_path = os.path.join(self.storage_path, 'images', f"{user_id}.jpg")
            image.save(image_path)
            
            # Get face embedding
            embedding = DeepFace.represent(image_path, model_name='Facenet')
            
            # Store embedding
            self.face_embeddings[user_id] = {
                'embedding': embedding,
                'metadata': metadata or {},
                'registered_at': datetime.now().isoformat(),
                'last_updated': datetime.now().isoformat(),
                'image_path': image_path
            }
            
            self.save_embeddings()
            
            return {
                "status": "success",
                "message": "Face registered successfully",
                "user_id": user_id,
                "image_path": image_path
            }
        except Exception as e:
            self.logger.error(f"Registration error for user {user_id}: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }

    def verify_face(self, image_data, min_confidence=0.7):
        """
        Verify a face against registered faces
        
        Args:
            image_data (str): Base64 encoded image
            min_confidence (float): Minimum confidence required for match
            
        Returns:
            dict: Verification result
        """
        try:
            # Save the verification image
            image_path = self.save_image('verify', image_data, 'verify')
            if not image_path:
                return {
                    "status": "error",
                    "message": "Failed to save verification image"
                }

            # Convert base64 to image
            image = Image.open(io.BytesIO(base64.b64decode(image_data)))
            
            # Get face embedding for the input image
            try:
                input_embedding = DeepFace.represent(
                    np.array(image), 
                    model_name='Facenet',
                    enforce_detection=False
                )
            except Exception as e:
                self.logger.error(f"Face detection error in verification: {str(e)}")
                return {
                    "status": "error",
                    "message": "No face detected in verification image"
                }

            # Compare with all stored embeddings
            matches = []
            for user_id, data in self.face_embeddings.items():
                embedding = data["embedding"]
                
                # Calculate cosine distance
                distance = np.linalg.norm(np.array(input_embedding) - np.array(embedding))
                confidence = 1 - distance
                
                if confidence >= min_confidence:
                    matches.append({
                        "user_id": user_id,
                        "confidence": confidence,
                        "metadata": data.get("metadata", {})
                    })

            if matches:
                # Sort matches by confidence
                matches.sort(key=lambda x: x["confidence"], reverse=True)
                best_match = matches[0]
                
                return {
                    "status": "success",
                    "match_found": True,
                    "user_id": best_match["user_id"],
                    "confidence": best_match["confidence"],
                    "metadata": best_match["metadata"],
                    "verification_image": image_path,
                    "message": "Face matched successfully"
                }
            else:
                return {
                    "status": "success",
                    "match_found": False,
                    "message": "No matching face found"
                }
        except Exception as e:
            self.logger.error(f"Verification error: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }

    def get_user_faces(self, user_id):
        """
        Get all registered faces for a user
        
        Args:
            user_id (str): User ID
            
        Returns:
            dict: User face information
        """
        try:
            if user_id in self.face_embeddings:
                data = self.face_embeddings[user_id]
                return {
                    "status": "success",
                    "user_id": user_id,
                    "metadata": data.get("metadata", {}),
                    "last_updated": data.get("last_updated"),
                    "image_path": data.get("image_path")
                }
            else:
                return {
                    "status": "error",
                    "message": "User not found"
                }
        except Exception as e:
            self.logger.error(f"Error getting user faces: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }

    def update_metadata(self, user_id, metadata):
        """
        Update metadata for a registered face
        
        Args:
            user_id (str): User ID
            metadata (dict): New metadata
            
        Returns:
            dict: Update result
        """
        try:
            if user_id in self.face_embeddings:
                self.face_embeddings[user_id]["metadata"] = metadata
                self.face_embeddings[user_id]["last_updated"] = datetime.now().isoformat()
                self.save_embeddings()
                return {
                    "status": "success",
                    "message": "Metadata updated successfully"
                }
            else:
                return {
                    "status": "error",
                    "message": "User not found"
                }
        except Exception as e:
            self.logger.error(f"Error updating metadata: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }
