from flask import Flask, render_template, redirect, request, session, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import os
import csv

import logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.logger.setLevel(logging.DEBUG)
app.config['SECRET_KEY'] = 'secret123'
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)

# ---------------- MODELS ----------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    role = db.Column(db.String(20))
    instructor_id = db.Column(db.Integer)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(500))
    answer = db.Column(db.String(100))

class Result(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer)
    question_id = db.Column(db.Integer)
    selected_answer = db.Column(db.String(100))
    correct_answer = db.Column(db.String(100))
    is_correct = db.Column(db.Boolean)
    attempt = db.Column(db.Integer)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# ---------------- ROUTES ----------------
@app.route('/')
def home():
    return redirect('/login')

@app.route('/register', methods=['GET', 'POST'])
def register():
    instructors = User.query.filter_by(role="instructor").all()

    if request.method == 'POST':
        user = User(
            name=request.form['name'],
            email=request.form['email'],
            password="",
            role="student",
            instructor_id=int(request.form['instructor'])
        )
        db.session.add(user)
        db.session.commit()
        return redirect('/login')

    return render_template('register.html', instructors=instructors)

# LOGIN (no password for students)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        name = request.form.get('name')

        user = User.query.filter_by(email=email).first()

        if user:
            if user.role == "student":
                if user.name.lower() == name.lower():
                    login_user(user)
                    return redirect('/student')
                return "Invalid Name"

            if user.password == request.form['password']:
                login_user(user)
                return redirect(f"/{user.role}")

        return "Invalid Login"

    return render_template('login.html')

# INSTRUCTOR (only their students)
@app.route('/instructor')
@login_required
def instructor():
    if current_user.role != "instructor":
        return "Access Denied"

    students = User.query.filter_by(
        role="student",
        instructor_id=current_user.id
    ).all()

    return render_template('instructor.html', students=students)

# ADMIN
@app.route('/admin')
@login_required
def admin():
    if current_user.role != "admin":
        return "Access Denied"

    users = User.query.all()
    questions = Question.query.all()
    results = Result.query.all()

    return render_template('admin.html',
        users=users,
        questions=questions,
        results=results
    )

# EXPORT CSV
@app.route('/export_results')
@login_required
def export_results():
    if current_user.role not in ["admin", "instructor"]:
        return "Access Denied"

    if current_user.role == "admin":
        results = Result.query.all()
    else:
        students = User.query.filter_by(
            role="student",
            instructor_id=current_user.id
        ).all()
        student_ids = [s.id for s in students]
        results = Result.query.filter(Result.student_id.in_(student_ids)).all()

    def generate():
        yield "Student,Question,Selected,Correct,IsCorrect,Attempt\n"
        for r in results:
            student = db.session.get(User, r.student_id)
            question = db.session.get(Question, r.question_id)

            yield f"{student.name},{question.question},{r.selected_answer},{r.correct_answer},{r.is_correct},{r.attempt}\n"

    return Response(generate(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=results.csv"}
    )

# LOGOUT
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/login')

# ---------------- RUN ----------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()

        if not User.query.filter_by(email="admin@gmail.com").first():
            db.session.add(User(name="Admin", email="admin@gmail.com", password="admin123", role="admin"))
            db.session.add(User(name="Instructor", email="inst@gmail.com", password="inst123", role="instructor"))
            db.session.commit()
