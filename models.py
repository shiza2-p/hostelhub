from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='student')  # 'admin' or 'student'
    created_at = db.Column(db.Date, default=date.today)

    # One user has one student profile
    student = db.relationship('Student', backref='user', uselist=False, lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_number = db.Column(db.String(10), unique=True, nullable=False)
    room_type = db.Column(db.String(50), nullable=True)        # e.g. Single, Double, Triple
    capacity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='Available')     # Available, Full, Maintenance
    description = db.Column(db.Text, nullable=True)

    # Relationship: One room -> many students
    students = db.relationship('Student', backref='room', lazy=True)

    def update_status(self):
        """Auto-update room status based on current occupancy."""
        occupancy = Student.query.filter_by(room_id=self.id).count()
        if occupancy >= self.capacity:
            self.status = 'Full'
        elif self.status != 'Maintenance':
            self.status = 'Available'


class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    address = db.Column(db.Text, nullable=True)
    cnic = db.Column(db.String(20), nullable=True)             # National ID
    emergency_contact = db.Column(db.String(15), nullable=True)
    admission_date = db.Column(db.Date, default=date.today)    # Proper Date type, not String
    is_approved = db.Column(db.Boolean, default=False)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=True)