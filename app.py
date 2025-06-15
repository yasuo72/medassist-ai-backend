import os
from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.exceptions import HTTPException
from services.face_recognition import FaceRecognitionService
from utils.logger import setup_logger

app = Flask(__name__)
CORS(app)

# Initialize logger
logger = setup_logger()

# Initialize face recognition service
face_recognition_service = FaceRecognitionService()

# Rate limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["50 per minute", "1000 per day"],
    storage_uri="memory://"
)

# Error handling
@app.errorhandler(Exception)
def handle_error(e):
    logger.error(f"Error occurred: {str(e)}", exc_info=True)
    
    if isinstance(e, HTTPException):
        return jsonify({
            "status": "error",
            "message": e.description,
            "code": e.code
        }), e.code
    
    return jsonify({
        "status": "error",
        "message": "Internal server error",
        "code": 500
    }), 500

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    try:
        # Check if face recognition service is available
        face_recognition_service.ping()
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "dependencies": {
                "face_recognition": "ok"
            }
        })
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Service unavailable",
            "timestamp": datetime.utcnow().isoformat()
        }), 503

@app.route('/api/register_face', methods=['POST'])
@limiter.limit("5/minute;100/day", error_message="Too many requests. Please try again later.")
def register_face():
    """
    Register a new face for a user
    
    Request Body:
    {
        "user_id": "string",
        "image_data": "base64_encoded_image",
        "metadata": {
            "name": "string",
            "emergency_contacts": ["string"],
            "medical_conditions": ["string"]
        }
    }
    """
    try:
        # Validate request
        data = request.json
        if not data:
            logger.error("Invalid request: No JSON data provided")
            raise ValueError("No JSON data provided")
            
        user_id = data.get('user_id')
        image_data = data.get('image_data')
        metadata = data.get('metadata')
        
        if not user_id or not image_data:
            logger.error(f"Invalid request: Missing required fields - user_id: {user_id}, image_data: {bool(image_data)}")
            raise ValueError("Missing required fields")
            
        # Validate image data size
        if len(image_data) > 5000000:  # 5MB limit
            logger.error(f"Image too large: {len(image_data)} bytes")
            raise ValueError("Image data too large")
            
        # Validate metadata
        if metadata:
            if not isinstance(metadata, dict):
                logger.error(f"Invalid metadata format: {type(metadata)}")
                raise ValueError("Metadata must be a dictionary")
            
            required_fields = ['name', 'emergency_contacts', 'medical_conditions']
            missing_fields = [field for field in required_fields if field not in metadata]
            if missing_fields:
                logger.error(f"Missing metadata fields: {missing_fields}")
                raise ValueError(f"Missing required metadata fields: {missing_fields}")

        logger.info(f"Registering face for user: {user_id}")
        
        # Add timeout to face recognition operation
        result = face_recognition_service.register_face(user_id, image_data, metadata)
        
        return jsonify({
            "status": "success",
            "message": "Face registered successfully",
            "data": result
        })
        
    except ValueError as ve:
        logger.error(f"Validation error: {str(ve)}")
        return jsonify({
            "status": "error",
            "message": str(ve),
            "code": 400
        }), 400
        
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)
        raise        
    except Exception as e:
        logger.error(f"Error in register_face: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/verify_face', methods=['POST'])
def verify_face():
    """
    Verify a face against registered faces
    
    Request Body:
    {
        "image_data": "base64_encoded_image",
        "min_confidence": 0.7 (optional)
    }
    """
    try:
        data = request.json
        
        if not data:
            return jsonify({"status": "error", "message": "Invalid request"}), 400
            
        image_data = data.get('image_data')
        min_confidence = data.get('min_confidence', 0.7)
        
        if not image_data:
            return jsonify({"status": "error", "message": "Missing image_data"}), 400
            
        logger.info("Verifying face...")
        
        result = face_recognition_service.verify_face(image_data, min_confidence)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in verify_face: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/get_user_faces', methods=['GET'])
def get_user_faces():
    """
    Get face information for a specific user
    
    Query Parameters:
    user_id: string
    """
    try:
        user_id = request.args.get('user_id')
        
        if not user_id:
            return jsonify({"status": "error", "message": "Missing user_id"}), 400
            
        logger.info(f"Getting face info for user: {user_id}")
        
        result = face_recognition_service.get_user_faces(user_id)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in get_user_faces: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/update_metadata', methods=['POST'])
def update_metadata():
    """
    Update metadata for a registered face
    
    Request Body:
    {
        "user_id": "string",
        "metadata": {
            "name": "string",
            "emergency_contacts": ["string"],
            "medical_conditions": ["string"]
        }
    }
    """
    try:
        data = request.json
        
        if not data:
            return jsonify({"status": "error", "message": "Invalid request"}), 400
            
        user_id = data.get('user_id')
        metadata = data.get('metadata')
        
        if not user_id or not metadata:
            return jsonify({"status": "error", "message": "Missing required fields"}), 400
            
        logger.info(f"Updating metadata for user: {user_id}")
        
        result = face_recognition_service.update_metadata(user_id, metadata)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in update_metadata: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """
    Health check endpoint
    Returns:
        dict: Service status
    """
    try:
        logger.info("Health check request received")
        return jsonify({
            "status": "healthy",
            "service": "face_recognition",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error in health check: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.errorhandler(404)
def not_found_error(error):
    logger.error(f"404 error: {str(error)}")
    return jsonify({"status": "error", "message": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"500 error: {str(error)}")
    return jsonify({"status": "error", "message": "Internal server error"}), 500

# For local development
if __name__ == '__main__':
    logger.info("Starting Flask server...")
    app.run(host='0.0.0.0', port=5000)
