import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager, create_access_token,
    jwt_required, get_jwt_identity
)
from models import db, User, Student, Room

app = Flask(__name__)
CORS(app)

# ─────────────────────────────────────────────
# CONFIGURATION
# IMPORTANT: JWT_SECRET_KEY must come from an environment variable
# ─────────────────────────────────────────────
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL', 'sqlite:///hostel.db'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.environ.get(
    'JWT_SECRET_KEY', 'change-this-in-production'
)

db.init_app(app)
jwt = JWTManager(app)

with app.app_context():
    db.create_all()
    if Room.query.count() == 0:
        rooms = [
            Room(room_number="101", room_type="Single", capacity=1, price=5000, status="Available", description="Comfortable single room with attached bathroom"),
            Room(room_number="102", room_type="Single", capacity=1, price=5000, status="Available", description="Comfortable single room with attached bathroom"),
            Room(room_number="201", room_type="Double", capacity=2, price=8000, status="Available", description="Spacious double room with two beds"),
            Room(room_number="202", room_type="Double", capacity=2, price=8000, status="Available", description="Spacious double room with two beds"),
            Room(room_number="301", room_type="Triple", capacity=3, price=10000, status="Available", description="Triple room ideal for groups"),
            Room(room_number="401", room_type="Dormitory", capacity=6, price=3000, status="Available", description="Affordable dormitory with shared facilities"),
        ]
        db.session.add_all(rooms)
        db.session.commit()


# ─────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────
def get_current_user():
    """Return the User object for the logged-in user."""
    user_id = get_jwt_identity()
    return db.session.get(User, int(user_id)) 

def is_admin():
    user = get_current_user()
    return user and user.role == 'admin'


# ════════════════════════════════════════════════════════
# SECTION 1: USER AUTHENTICATION (Login / Signup)
# ════════════════════════════════════════════════════════

@app.route('/auth/signup', methods=['POST'])
def signup():
    """Register a new user. Role is always 'student' — admin is never self-assignable."""
    data = request.get_json() or {}
    email    = data.get('email', '').strip()
    password = data.get('password', '')
    username = data.get('username', '').strip()

    # Validate required fields
    if not email or not password or not username:
        return jsonify({"message": "email, password, and username are required"}), 400

    if len(password) < 6:
        return jsonify({"message": "Password must be at least 6 characters"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"message": "Email already registered"}), 409

    if User.query.filter_by(username=username).first():
        return jsonify({"message": "Username already taken"}), 409

    # Role is always 'student' on self-signup — only admins can promote users
    new_user = User(username=username, email=email, role='student')
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"message": "Account created successfully"}), 201


@app.route('/auth/login', methods=['POST'])
def login():
    """Login and receive a JWT token."""
    data = request.get_json() or {}
    user = User.query.filter_by(email=data.get('email', '').strip()).first()

    if user and user.check_password(data.get('password', '')):
        access_token = create_access_token(identity=str(user.id))
        return jsonify({
            "token":    access_token,
            "role":     user.role,
            "username": user.username,
            "user_id":  user.id
        }), 200

    return jsonify({"message": "Invalid email or password"}), 401


# ════════════════════════════════════════════════════════
# SECTION 2: STUDENT REGISTRATION / ADMISSION
# ════════════════════════════════════════════════════════

@app.route('/student/register', methods=['POST'])
@jwt_required()
def register_student():
    """
    A logged-in user submits their student profile / admission form.
    Each user can only have one student profile.
    """
    current_user = get_current_user()

    # Check if this user already applied
    if current_user.student:
        return jsonify({"message": "You have already submitted an admission form"}), 409

    data      = request.get_json() or {}
    full_name = data.get('full_name', '').strip()
    phone     = data.get('phone', '').strip()

    if not full_name or not phone:
        return jsonify({"message": "full_name and phone are required"}), 400

    new_student = Student(
        user_id           = current_user.id,
        full_name         = full_name,
        phone             = phone,
        address           = data.get('address', ''),
        cnic              = data.get('cnic', ''),
        emergency_contact = data.get('emergency_contact', ''),
        is_approved       = False   # Pending admin approval
    )
    db.session.add(new_student)
    db.session.commit()

    return jsonify({
        "message":    "Admission form submitted. Awaiting admin approval.",
        "student_id": new_student.id
    }), 201


@app.route('/admin/students', methods=['GET'])
@jwt_required()
def list_students():
    """Admin: View all students (optionally filter by approval status)."""
    if not is_admin():
        return jsonify({"message": "Admin access required"}), 403

    approved_filter = request.args.get('approved')   # ?approved=true / false
    query = Student.query

    if approved_filter == 'true':
        query = query.filter_by(is_approved=True)
    elif approved_filter == 'false':
        query = query.filter_by(is_approved=False)

    students = query.all()
    return jsonify([{
        "id":           s.id,
        "full_name":    s.full_name,
        "phone":        s.phone,
        "admission_date": str(s.admission_date),
        "is_approved":  s.is_approved,
        "room_id":      s.room_id
    } for s in students]), 200


@app.route('/admin/approve_student/<int:student_id>', methods=['PATCH'])
@jwt_required()
def approve_student(student_id):
    """Admin: Approve or reject a student admission."""
    if not is_admin():
        return jsonify({"message": "Admin access required"}), 403

    student = db.session.get(Student, student_id)
    if not student:
        return jsonify({"message": "Student not found"}), 404

    data = request.get_json() or {}
    student.is_approved = data.get('is_approved', student.is_approved)
    db.session.commit()

    status_text = "approved" if student.is_approved else "rejected"
    return jsonify({"message": f"Student {status_text} successfully"}), 200


@app.route('/admin/allocate_room', methods=['POST'])
@jwt_required()
def allocate_room():
    """Admin: Assign a student to a room."""
    if not is_admin():
        return jsonify({"message": "Admin access required"}), 403

    data    = request.get_json() or {}
    student = db.session.get(Student, data.get('student_id'))
    room    = db.session.get(Room, data.get('room_id'))

    if not student or not room:
        return jsonify({"message": "Student or Room not found"}), 404

    if not student.is_approved:
        return jsonify({"message": "Student must be approved before room allocation"}), 400

    if room.status == 'Maintenance':
        return jsonify({"message": "Room is under maintenance"}), 400

    occupancy = Student.query.filter_by(room_id=room.id).count()
    if occupancy >= room.capacity:
        return jsonify({"message": "Room is at full capacity"}), 400

    student.room_id = room.id
    room.update_status()
    db.session.commit()

    return jsonify({"message": f"Room {room.room_number} allocated to {student.full_name}"}), 200


# ════════════════════════════════════════════════════════
# SECTION 3: ROOM MANAGEMENT (Add, Update, Delete, List)
# ════════════════════════════════════════════════════════

@app.route('/rooms', methods=['GET'])
def list_rooms():
    """Public: Get all available rooms (for the Rooms Listing page)."""
    rooms = Room.query.all()
    return jsonify([{
        "id":          r.id,
        "room_number": r.room_number,
        "room_type":   r.room_type,
        "capacity":    r.capacity,
        "price":       r.price,
        "status":      r.status,
        "description": r.description,
        "occupancy":   Student.query.filter_by(room_id=r.id).count()
    } for r in rooms]), 200


@app.route('/rooms/<int:room_id>', methods=['GET'])
def get_room(room_id):
    """Public: Get details of a single room (for the Room Details page)."""
    room = db.session.get(Room, room_id)
    if not room:
        return jsonify({"message": "Room not found"}), 404

    return jsonify({
        "id":          room.id,
        "room_number": room.room_number,
        "room_type":   room.room_type,
        "capacity":    room.capacity,
        "price":       room.price,
        "status":      room.status,
        "description": room.description,
        "occupancy":   Student.query.filter_by(room_id=room.id).count()
    }), 200


@app.route('/admin/rooms', methods=['POST'])
@jwt_required()
def add_room():
    """Admin: Add a new room."""
    if not is_admin():
        return jsonify({"message": "Admin access required"}), 403

    data        = request.get_json() or {}
    room_number = data.get('room_number', '').strip()
    capacity    = data.get('capacity')
    price       = data.get('price')

    if not room_number or not capacity or not price:
        return jsonify({"message": "room_number, capacity, and price are required"}), 400

    if Room.query.filter_by(room_number=room_number).first():
        return jsonify({"message": "Room number already exists"}), 409

    new_room = Room(
        room_number = room_number,
        room_type   = data.get('room_type', 'Standard'),
        capacity    = int(capacity),
        price       = float(price),
        status      = data.get('status', 'Available'),
        description = data.get('description', '')
    )
    db.session.add(new_room)
    db.session.commit()

    return jsonify({"message": "Room added", "room_id": new_room.id}), 201


@app.route('/admin/rooms/<int:room_id>', methods=['PUT'])
@jwt_required()
def update_room(room_id):
    """Admin: Update room details."""
    if not is_admin():
        return jsonify({"message": "Admin access required"}), 403

    room = db.session.get(Room, room_id)
    if not room:
        return jsonify({"message": "Room not found"}), 404

    data = request.get_json() or {}
    room.room_number = data.get('room_number', room.room_number)
    room.room_type   = data.get('room_type',   room.room_type)
    room.capacity    = data.get('capacity',    room.capacity)
    room.price       = data.get('price',       room.price)
    room.status      = data.get('status',      room.status)
    room.description = data.get('description', room.description)
    db.session.commit()

    return jsonify({"message": "Room updated successfully"}), 200


@app.route('/admin/rooms/<int:room_id>', methods=['DELETE'])
@jwt_required()
def delete_room(room_id):
    """Admin: Delete a room. Blocked if students are assigned."""
    if not is_admin():
        return jsonify({"message": "Admin access required"}), 403

    room = db.session.get(Room, room_id)
    if not room:
        return jsonify({"message": "Room not found"}), 404

    # Safety: cannot delete a room with students in it
    if Student.query.filter_by(room_id=room.id).count() > 0:
        return jsonify({"message": "Cannot delete room — students are assigned to it"}), 400

    db.session.delete(room)
    db.session.commit()

    return jsonify({"message": "Room deleted"}), 200


# ════════════════════════════════════════════════════════
# SECTION 4: STUDENT PROFILE MANAGEMENT
# ════════════════════════════════════════════════════════

@app.route('/student/profile', methods=['GET'])
@jwt_required()
def get_my_profile():
    """Student: View their own profile and room info."""
    current_user = get_current_user()

    if not current_user.student:
        return jsonify({"message": "No student profile found. Please register first."}), 404

    s = current_user.student
    room_info = None
    if s.room_id:
        room = db.session.get(Room, s.room_id)
        if room:
            room_info = {
                "room_number": room.room_number,
                "room_type":   room.room_type,
                "price":       room.price
            }

    return jsonify({
        "id":               s.id,
        "full_name":        s.full_name,
        "phone":            s.phone,
        "address":          s.address,
        "cnic":             s.cnic,
        "emergency_contact": s.emergency_contact,
        "admission_date":   str(s.admission_date),
        "is_approved":      s.is_approved,
        "room":             room_info,
        "username":         current_user.username,
        "email":            current_user.email
    }), 200


@app.route('/student/profile', methods=['PUT'])
@jwt_required()
def update_my_profile():
    """Student: Update their own profile details."""
    current_user = get_current_user()

    if not current_user.student:
        return jsonify({"message": "No student profile found"}), 404

    data = request.get_json() or {}
    s = current_user.student

    # Students can only update non-sensitive fields
    s.phone             = data.get('phone',             s.phone)
    s.address           = data.get('address',           s.address)
    s.emergency_contact = data.get('emergency_contact', s.emergency_contact)

    db.session.commit()
    return jsonify({"message": "Profile updated successfully"}), 200


@app.route('/admin/students/<int:student_id>/profile', methods=['GET'])
@jwt_required()
def admin_get_student_profile(student_id):
    """Admin: View any student's full profile."""
    if not is_admin():
        return jsonify({"message": "Admin access required"}), 403

    s = db.session.get(Student, student_id)
    if not s:
        return jsonify({"message": "Student not found"}), 404

    user = db.session.get(User, s.user_id)
    room_info = None
    if s.room_id:
        room = db.session.get(Room, s.room_id)
        if room:
            room_info = {"room_number": room.room_number, "price": room.price}

    return jsonify({
        "id":               s.id,
        "full_name":        s.full_name,
        "phone":            s.phone,
        "address":          s.address,
        "cnic":             s.cnic,
        "emergency_contact": s.emergency_contact,
        "admission_date":   str(s.admission_date),
        "is_approved":      s.is_approved,
        "room":             room_info,
        "email":            user.email if user else None
    }), 200


if __name__ == '__main__':
    app.run(debug=True)