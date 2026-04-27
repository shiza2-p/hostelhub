import os
from datetime import date
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager, create_access_token,
    jwt_required, get_jwt_identity
)
from models import db, User, Student, Room, Fee, Complaint

# ─────────────────────────────────────────
# APP SETUP
# ─────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=os.path.join(BASE_DIR, 'static'), static_url_path='')
CORS(app)

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///hostel.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'change-this-before-deploy')

db.init_app(app)
jwt = JWTManager(app)

with app.app_context():
    db.create_all()


# ─────────────────────────────────────────
# SERVE FRONTEND (HTML pages)
# ─────────────────────────────────────────
@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    """Serve any frontend file; falls back to 404 if not found."""
    filepath = os.path.join(app.static_folder, filename)
    if os.path.isfile(filepath):
        return send_from_directory(app.static_folder, filename)
    return jsonify({"message": "Not found"}), 404


# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────
def get_current_user():
    user_id = get_jwt_identity()
    return db.session.get(User, int(user_id))

def is_admin():
    user = get_current_user()
    return user and user.role == 'admin'


# ═══════════════════════════════════════════════════════
# 1. USER AUTHENTICATION  –  /api/auth/*
# ═══════════════════════════════════════════════════════

@app.route('/api/auth/signup', methods=['POST'])
def signup():
    data     = request.get_json() or {}
    email    = data.get('email', '').strip()
    password = data.get('password', '')
    username = data.get('username', '').strip()

    if not email or not password or not username:
        return jsonify({"message": "email, password and username are required"}), 400
    if len(password) < 6:
        return jsonify({"message": "Password must be at least 6 characters"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"message": "Email already registered"}), 409
    if User.query.filter_by(username=username).first():
        return jsonify({"message": "Username already taken"}), 409

    user = User(username=username, email=email, role='student')
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify({"message": "Account created successfully"}), 201


@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    user = User.query.filter_by(email=data.get('email', '').strip()).first()
    if user and user.check_password(data.get('password', '')):
        token = create_access_token(identity=str(user.id))
        return jsonify({
            "token":    token,
            "role":     user.role,
            "username": user.username,
            "user_id":  user.id
        }), 200
    return jsonify({"message": "Invalid email or password"}), 401


@app.route('/api/auth/change-password', methods=['POST'])
@jwt_required()
def change_password():
    user = get_current_user()
    data = request.get_json() or {}
    old_pw  = data.get('old_password', '')
    new_pw  = data.get('new_password', '')

    if not user.check_password(old_pw):
        return jsonify({"message": "Current password is incorrect"}), 400
    if len(new_pw) < 6:
        return jsonify({"message": "New password must be at least 6 characters"}), 400

    user.set_password(new_pw)
    db.session.commit()
    return jsonify({"message": "Password updated successfully"}), 200


# ═══════════════════════════════════════════════════════
# 2. STUDENT REGISTRATION / ADMISSION  –  /api/student/*
# ═══════════════════════════════════════════════════════

@app.route('/api/student/register', methods=['POST'])
@jwt_required()
def register_student():
    current_user = get_current_user()
    if current_user.student:
        return jsonify({"message": "Admission form already submitted"}), 409

    data      = request.get_json() or {}
    full_name = data.get('full_name', '').strip()
    phone     = data.get('phone', '').strip()

    if not full_name or not phone:
        return jsonify({"message": "full_name and phone are required"}), 400

    s = Student(
        user_id           = current_user.id,
        full_name         = full_name,
        phone             = phone,
        address           = data.get('address', ''),
        cnic              = data.get('cnic', ''),
        emergency_contact = data.get('emergency_contact', ''),
        is_approved       = False
    )
    db.session.add(s)
    db.session.commit()
    return jsonify({"message": "Admission submitted. Awaiting admin approval.", "student_id": s.id}), 201


@app.route('/api/admin/students', methods=['GET'])
@jwt_required()
def list_students():
    if not is_admin():
        return jsonify({"message": "Admin access required"}), 403

    approved_filter = request.args.get('approved')
    query = Student.query
    if approved_filter == 'true':
        query = query.filter_by(is_approved=True)
    elif approved_filter == 'false':
        query = query.filter_by(is_approved=False)

    return jsonify([{
        "id":             s.id,
        "full_name":      s.full_name,
        "phone":          s.phone,
        "email":          db.session.get(User, s.user_id).email if s.user_id else None,
        "admission_date": str(s.admission_date),
        "is_approved":    s.is_approved,
        "room_id":        s.room_id
    } for s in query.all()]), 200


@app.route('/api/admin/approve_student/<int:student_id>', methods=['PATCH'])
@jwt_required()
def approve_student(student_id):
    if not is_admin():
        return jsonify({"message": "Admin access required"}), 403

    s = db.session.get(Student, student_id)
    if not s:
        return jsonify({"message": "Student not found"}), 404

    data = request.get_json() or {}
    s.is_approved = data.get('is_approved', s.is_approved)
    db.session.commit()
    return jsonify({"message": "Student " + ("approved" if s.is_approved else "rejected")}), 200


# ═══════════════════════════════════════════════════════
# 3. ROOM MANAGEMENT  –  /api/rooms  &  /api/admin/rooms
# ═══════════════════════════════════════════════════════

@app.route('/api/rooms', methods=['GET'])
def list_rooms():
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


@app.route('/api/rooms/<int:room_id>', methods=['GET'])
def get_room(room_id):
    r = db.session.get(Room, room_id)
    if not r:
        return jsonify({"message": "Room not found"}), 404
    return jsonify({
        "id":          r.id,
        "room_number": r.room_number,
        "room_type":   r.room_type,
        "capacity":    r.capacity,
        "price":       r.price,
        "status":      r.status,
        "description": r.description,
        "occupancy":   Student.query.filter_by(room_id=r.id).count()
    }), 200


@app.route('/api/admin/rooms', methods=['POST'])
@jwt_required()
def add_room():
    if not is_admin():
        return jsonify({"message": "Admin access required"}), 403

    data = request.get_json() or {}
    room_number = data.get('room_number', '').strip()
    capacity    = data.get('capacity')
    price       = data.get('price')

    if not room_number or not capacity or not price:
        return jsonify({"message": "room_number, capacity and price are required"}), 400
    if Room.query.filter_by(room_number=room_number).first():
        return jsonify({"message": "Room number already exists"}), 409

    r = Room(
        room_number = room_number,
        room_type   = data.get('room_type', 'Standard'),
        capacity    = int(capacity),
        price       = float(price),
        status      = data.get('status', 'Available'),
        description = data.get('description', '')
    )
    db.session.add(r)
    db.session.commit()
    return jsonify({"message": "Room added", "room_id": r.id}), 201


@app.route('/api/admin/rooms/<int:room_id>', methods=['PUT'])
@jwt_required()
def update_room(room_id):
    if not is_admin():
        return jsonify({"message": "Admin access required"}), 403

    r = db.session.get(Room, room_id)
    if not r:
        return jsonify({"message": "Room not found"}), 404

    data = request.get_json() or {}
    r.room_number = data.get('room_number', r.room_number)
    r.room_type   = data.get('room_type',   r.room_type)
    r.capacity    = data.get('capacity',    r.capacity)
    r.price       = data.get('price',       r.price)
    r.status      = data.get('status',      r.status)
    r.description = data.get('description', r.description)
    db.session.commit()
    return jsonify({"message": "Room updated"}), 200


@app.route('/api/admin/rooms/<int:room_id>', methods=['DELETE'])
@jwt_required()
def delete_room(room_id):
    if not is_admin():
        return jsonify({"message": "Admin access required"}), 403

    r = db.session.get(Room, room_id)
    if not r:
        return jsonify({"message": "Room not found"}), 404
    if Student.query.filter_by(room_id=r.id).count() > 0:
        return jsonify({"message": "Cannot delete — students are assigned to this room"}), 400

    db.session.delete(r)
    db.session.commit()
    return jsonify({"message": "Room deleted"}), 200


# ═══════════════════════════════════════════════════════
# 4. ROOM ALLOCATION  –  /api/admin/allocate_room
# ═══════════════════════════════════════════════════════

@app.route('/api/admin/allocate_room', methods=['POST'])
@jwt_required()
def allocate_room():
    if not is_admin():
        return jsonify({"message": "Admin access required"}), 403

    data    = request.get_json() or {}
    student = db.session.get(Student, data.get('student_id'))
    room    = db.session.get(Room,    data.get('room_id'))

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


# ═══════════════════════════════════════════════════════
# 5. FEE MANAGEMENT  –  /api/student/fees  &  /api/admin/fees
# ═══════════════════════════════════════════════════════

@app.route('/api/student/fees', methods=['GET'])
@jwt_required()
def student_get_fees():
    user = get_current_user()
    if not user.student:
        return jsonify({"message": "No student profile found"}), 404

    fees = Fee.query.filter_by(student_id=user.student.id).order_by(Fee.due_date.desc()).all()
    return jsonify([{
        "id":          f.id,
        "description": f.description,
        "amount":      f.amount,
        "due_date":    str(f.due_date),
        "paid_date":   str(f.paid_date) if f.paid_date else None,
        "status":      f.status
    } for f in fees]), 200


@app.route('/api/admin/fees', methods=['GET'])
@jwt_required()
def admin_get_all_fees():
    if not is_admin():
        return jsonify({"message": "Admin access required"}), 403

    fees = Fee.query.all()
    return jsonify([{
        "id":           f.id,
        "student_id":   f.student_id,
        "student_name": f.student.full_name if f.student else None,
        "description":  f.description,
        "amount":       f.amount,
        "due_date":     str(f.due_date),
        "paid_date":    str(f.paid_date) if f.paid_date else None,
        "status":       f.status
    } for f in fees]), 200


@app.route('/api/admin/fees', methods=['POST'])
@jwt_required()
def admin_create_fee():
    """Admin creates a fee record for a student."""
    if not is_admin():
        return jsonify({"message": "Admin access required"}), 403

    data = request.get_json() or {}
    student_id  = data.get('student_id')
    description = data.get('description', '').strip()
    amount      = data.get('amount')
    due_date_str = data.get('due_date', '')

    if not student_id or not description or not amount or not due_date_str:
        return jsonify({"message": "student_id, description, amount and due_date are required"}), 400

    try:
        due_date = date.fromisoformat(due_date_str)
    except ValueError:
        return jsonify({"message": "due_date must be in YYYY-MM-DD format"}), 400

    fee = Fee(
        student_id  = student_id,
        description = description,
        amount      = float(amount),
        due_date    = due_date,
        status      = 'Pending'
    )
    db.session.add(fee)
    db.session.commit()
    return jsonify({"message": "Fee record created", "fee_id": fee.id}), 201


@app.route('/api/admin/fees/<int:fee_id>/mark_paid', methods=['PATCH'])
@jwt_required()
def mark_fee_paid(fee_id):
    """Admin marks a fee as paid."""
    if not is_admin():
        return jsonify({"message": "Admin access required"}), 403

    fee = db.session.get(Fee, fee_id)
    if not fee:
        return jsonify({"message": "Fee not found"}), 404

    fee.status    = 'Paid'
    fee.paid_date = date.today()
    db.session.commit()
    return jsonify({"message": "Fee marked as paid"}), 200


# ═══════════════════════════════════════════════════════
# 6. COMPLAINT / REQUEST SYSTEM  –  /api/student/complaints
# ═══════════════════════════════════════════════════════

@app.route('/api/student/complaints', methods=['POST'])
@jwt_required()
def submit_complaint():
    user = get_current_user()
    if not user.student:
        return jsonify({"message": "Register as a student first"}), 400

    data  = request.get_json() or {}
    title = data.get('title', '').strip()
    desc  = data.get('description', '').strip()

    if not title or not desc:
        return jsonify({"message": "title and description are required"}), 400

    c = Complaint(
        student_id  = user.student.id,
        title       = title,
        description = desc,
        category    = data.get('category', 'Other'),
        status      = 'Open'
    )
    db.session.add(c)
    db.session.commit()
    return jsonify({"message": "Complaint submitted", "complaint_id": c.id}), 201


@app.route('/api/student/complaints', methods=['GET'])
@jwt_required()
def student_get_complaints():
    user = get_current_user()
    if not user.student:
        return jsonify({"message": "No student profile found"}), 404

    complaints = Complaint.query.filter_by(student_id=user.student.id).order_by(Complaint.created_at.desc()).all()
    return jsonify([{
        "id":          c.id,
        "title":       c.title,
        "description": c.description,
        "category":    c.category,
        "status":      c.status,
        "created_at":  str(c.created_at),
        "admin_note":  c.admin_note
    } for c in complaints]), 200


@app.route('/api/admin/complaints', methods=['GET'])
@jwt_required()
def admin_get_complaints():
    if not is_admin():
        return jsonify({"message": "Admin access required"}), 403

    status_filter = request.args.get('status')
    query = Complaint.query
    if status_filter:
        query = query.filter_by(status=status_filter)

    complaints = query.order_by(Complaint.created_at.desc()).all()
    return jsonify([{
        "id":           c.id,
        "student_id":   c.student_id,
        "student_name": c.student.full_name if c.student else None,
        "title":        c.title,
        "category":     c.category,
        "status":       c.status,
        "created_at":   str(c.created_at),
        "admin_note":   c.admin_note
    } for c in complaints]), 200


@app.route('/api/admin/complaints/<int:complaint_id>', methods=['PATCH'])
@jwt_required()
def update_complaint(complaint_id):
    if not is_admin():
        return jsonify({"message": "Admin access required"}), 403

    c = db.session.get(Complaint, complaint_id)
    if not c:
        return jsonify({"message": "Complaint not found"}), 404

    data = request.get_json() or {}
    c.status     = data.get('status',     c.status)
    c.admin_note = data.get('admin_note', c.admin_note)
    if c.status == 'Resolved' and not c.resolved_at:
        c.resolved_at = date.today()
    db.session.commit()
    return jsonify({"message": "Complaint updated"}), 200


# ═══════════════════════════════════════════════════════
# 7. STUDENT PROFILE MANAGEMENT  –  /api/student/profile
# ═══════════════════════════════════════════════════════

@app.route('/api/student/profile', methods=['GET'])
@jwt_required()
def get_my_profile():
    user = get_current_user()
    if not user.student:
        return jsonify({"message": "No student profile found. Please apply first.", "has_profile": False}), 404

    s = user.student
    room_info = None
    if s.room_id:
        r = db.session.get(Room, s.room_id)
        if r:
            room_info = {
                "room_number": r.room_number,
                "room_type":   r.room_type,
                "price":       r.price,
                "status":      r.status
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
        "username":         user.username,
        "email":            user.email,
        "has_profile":      True
    }), 200


@app.route('/api/student/profile', methods=['PUT'])
@jwt_required()
def update_my_profile():
    user = get_current_user()
    if not user.student:
        return jsonify({"message": "No student profile found"}), 404

    data = request.get_json() or {}
    s = user.student
    s.phone             = data.get('phone',             s.phone)
    s.address           = data.get('address',           s.address)
    s.emergency_contact = data.get('emergency_contact', s.emergency_contact)
    db.session.commit()
    return jsonify({"message": "Profile updated successfully"}), 200


@app.route('/api/admin/students/<int:student_id>/profile', methods=['GET'])
@jwt_required()
def admin_get_student_profile(student_id):
    if not is_admin():
        return jsonify({"message": "Admin access required"}), 403

    s = db.session.get(Student, student_id)
    if not s:
        return jsonify({"message": "Student not found"}), 404

    user = db.session.get(User, s.user_id)
    room_info = None
    if s.room_id:
        r = db.session.get(Room, s.room_id)
        if r:
            room_info = {"room_number": r.room_number, "price": r.price}

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


# ═══════════════════════════════════════════════════════
# 8. ADMIN CONTROL  –  /api/admin/*
# ═══════════════════════════════════════════════════════

@app.route('/api/admin/users', methods=['GET'])
@jwt_required()
def admin_list_users():
    if not is_admin():
        return jsonify({"message": "Admin access required"}), 403

    users = User.query.all()
    return jsonify([{
        "id":         u.id,
        "username":   u.username,
        "email":      u.email,
        "role":       u.role,
        "created_at": str(u.created_at),
        "has_profile": u.student is not None
    } for u in users]), 200


@app.route('/api/admin/promote', methods=['POST'])
@jwt_required()
def promote_user():
    """Admin can promote any user to admin role."""
    if not is_admin():
        return jsonify({"message": "Admin access required"}), 403

    data = request.get_json() or {}
    user_id = data.get('user_id')
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"message": "User not found"}), 404

    user.role = data.get('role', 'admin')   # 'admin' or 'student'
    db.session.commit()
    return jsonify({"message": f"{user.username} is now {user.role}"}), 200


@app.route('/api/admin/dashboard_stats', methods=['GET'])
@jwt_required()
def admin_dashboard_stats():
    """Admin dashboard overview stats."""
    if not is_admin():
        return jsonify({"message": "Admin access required"}), 403

    return jsonify({
        "total_students":   Student.query.count(),
        "pending_approvals": Student.query.filter_by(is_approved=False).count(),
        "total_rooms":      Room.query.count(),
        "available_rooms":  Room.query.filter_by(status='Available').count(),
        "open_complaints":  Complaint.query.filter_by(status='Open').count(),
        "pending_fees":     Fee.query.filter_by(status='Pending').count()
    }), 200


if __name__ == '__main__':
    app.run(debug=True)
