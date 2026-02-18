from flask_socketio import emit
from app.extensions import socketio
from app.services.recognition import load_known_students
import cv2
import numpy as np
import base64
import face_recognition

@socketio.on('process_frame')
def handle_frame(data):
    image_data = data.get('image')  # Base64-encoded image
    section_name = data.get('section_name')

    # Load known students for the current section
    known_face_encodings, known_face_ids = load_known_students(section_name)

    known_face_encodings = [np.array(encoding, dtype=np.float64) for encoding in known_face_encodings]

    try:
        # Decode the image
        image_data = image_data.split(",")[1]
        image = base64.b64decode(image_data)
        np_image = np.frombuffer(image, dtype=np.uint8)
        img = cv2.imdecode(np_image, cv2.IMREAD_COLOR)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB) # Convert to RGB for face_recognition
    except Exception as e:
        emit('frame_processed', {'success': False, 'message': f'Error decoding image: {e}'})
        return

    # If no known face encodings are found, return an empty response
    if not known_face_encodings:
        emit('frame_processed', {
            'success': True,
            'faces': [],
            'message': 'No known students found for this section.'
        })
        return

    # Perform facial recognition
    face_locations = face_recognition.face_locations(img)
    face_encodings = face_recognition.face_encodings(img, face_locations)

    faces_info = []

    for face_encoding, face_location in zip(face_encodings, face_locations):
        matches = face_recognition.compare_faces(known_face_encodings, face_encoding)
        face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)

        student_id = "Unknown"

        # If a match is found, get the student ID
        if True in matches:
            best_match_index = np.argmin(face_distances)
            if matches[best_match_index]:
                student_id = known_face_ids[best_match_index]
            print(f'{student_id} found')

        # Append face location and student ID to results
        faces_info.append({
            "location": face_location,  # [top, right, bottom, left]
            "student_id": student_id
        })
        
    emit('frame_processed', {'success': True, 'faces': faces_info})
