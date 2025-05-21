from app import db
from flask_login import UserMixin

# Teacher Database
class Teacher(db.Model, UserMixin):
    __tablename__ = "teachers"
    T_ID = db.Column(db.Integer, primary_key=True)
    TeacherName = db.Column(db.String(255), nullable=False)
    Initials = db.Column(db.String(50), nullable=False)
    Password = db.Column(db.String(50), nullable=False)
    Email = db.Column(db.String(50), nullable=True)

    def get_id(self):
        return f"teacher id = {self.T_ID}"


class Student(db.Model, UserMixin):
    __tablename__ = "student"
    S_ID = db.Column(db.Integer, primary_key=True)
    StudentName = db.Column(db.String(255), nullable=False)
    Initials = db.Column(db.String(50), nullable=False)
    Role = db.Column(db.String(50), nullable=True)
    Password = db.Column(db.String(50), nullable=False)
    Branch = db.Column(db.String(50), nullable=True)
    Semester = db.Column(db.String(50), nullable=True)
    Email = db.Column(db.String(50), nullable=True)

    def get_id(self):
        return f"student id = {self.S_ID}"

class Semester(db.Model):
    __tablename__ = 'Semester'
    SemesterID = db.Column(db.Integer, primary_key=True)
    SemesterName = db.Column(db.String(10), nullable=False)

    branches = db.relationship('Branch', backref='semester', lazy=True)


class Branch(db.Model):
    __tablename__ = 'Branch'
    BranchID = db.Column(db.Integer, primary_key=True)
    BranchName = db.Column(db.String(100), nullable=False)
    SemesterID = db.Column(db.Integer, db.ForeignKey('Semester.SemesterID'), nullable=False)

class Links(db.Model):
    # here we will add the link table
    __tablename__ = 'Link'
    L_ID = db.Column(db.Integer, primary_key=True)
    Branch = db.Column(db.String(100), nullable=False)
    Semester = db.Column(db.String(100), nullable=False)
    Subject = db.Column(db.String(100), nullable=False)
    Link = db.Column(db.String(1000), nullable=True)
    Comment = db.Column(db.String(1000), nullable=True)