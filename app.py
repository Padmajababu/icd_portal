from flask import Flask, render_template, redirect, request, session, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import os
import csv
import logging

# ---------------- APP SETUP ----------------
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

# ---------------- DB INIT (CRITICAL FOR RENDER) ----------------
with app.app_context():
    try:
        db.create_all()
        print("✅ Tables created")

        if not User.query.filter_by(email="admin@gmail.com").first():
            db.session.add(User(name="Admin", email="admin@gmail.com", password="admin123", role="admin"))
            db.session.add(User(name="Instructor", email="inst@gmail.com", password="inst123", role="instructor"))
            db.session.commit()
            print("✅ Default users created")

    except Exception as e:
        print("❌ DB ERROR:", e)

# ---------------- ROUTES ----------------
@app.route('/')
def home():
    return redirect('/login')

# REGISTER (STUDENT)
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

# LOGIN
@app.route('/login', methods=['GET', 'POST'])
def login():
    try:
        if request.method == 'POST':
            email = request.form.get('email')
            name = request.form.get('name')
            password = request.form.get('password')

            user = User.query.filter_by(email=email).first()

            if not user:
                return "User not found"

            # ✅ STUDENT LOGIN
            if user.role == "student":
                if not name:
                    return "Please enter your name"

                if user.name.strip().lower() == name.strip().lower():
                    login_user(user)

                    session['q_index'] = 0
                    return redirect('/student')

                return "Invalid Name"

            # ✅ ADMIN / INSTRUCTOR LOGIN
            if password and user.password == password:
                login_user(user)
                return redirect(f"/{user.role}")

            return "Invalid Password"

        return render_template('login.html')

    except Exception as e:
        app.logger.error(f"LOGIN ERROR: {str(e)}")
        return f"Error: {str(e)}"

# INSTRUCTOR DASHBOARD
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

# ADMIN DASHBOARD
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
# STUDENT DASHBOARD
@app.route('/student')
@login_required
def student():
    if current_user.role != "student":
        return "Access Denied"

    return "Student Dashboard"

# EXPORT RESULTS CSV
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

# ---------------- RUN (NO app.run for Render) ----------------


#--------ADD QUESTION---------------
@app.route('/add_question', methods=['GET', 'POST'])
@login_required
def add_question():
    if current_user.role != "admin":
        return "Access Denied"

    if request.method == 'POST':
        question = request.form.get('question')
        answer = request.form.get('answer')

        # ✅ validation
        if not question or not answer:
            return "Please fill all fields"

        new_q = Question(
            question=question.strip(),
            answer=answer.strip()
        )

        db.session.add(new_q)
        db.session.commit()

        return redirect('/admin')

    return render_template('add_question.html')


 #------------STUDENT QUIZ--------
@app.route('/student', methods=['GET', 'POST'])
@login_required
def student():
    if current_user.role != "student":
        return "Access Denied"

    questions = Question.query.all()

    # ✅ Track question index
    if 'q_index' not in session:
        session['q_index'] = 0

    # ✅ Track score
    if 'score' not in session:
        session['score'] = 0

    index = session['q_index']

    # ✅ Quiz finished
    if index >= len(questions):
        final_score = session.get('score', 0)

        # reset session
        session.pop('q_index', None)
        session.pop('score', None)

        return f"Quiz Completed 🎉 Your Score: {final_score}/{len(questions)}"

    current_q = questions[index]

    if request.method == 'POST':
        user_answer = request.form.get('answer').strip().lower()
        correct_answer = current_q.answer.strip().lower()

        is_correct = user_answer == correct_answer

        # ✅ SAVE RESULT
        result = Result(
            student_id=current_user.id,
            question_id=current_q.id,
            selected_answer=user_answer,
            correct_answer=current_q.answer,
            is_correct=is_correct,
            attempt=1
        )
        db.session.add(result)

        if is_correct:
            session['score'] += 1
            session['q_index'] += 1
            db.session.commit()
            return redirect('/student')
        else:
            db.session.commit()
            return render_template(
                'student.html',
                question=current_q,
                error="Wrong answer!",
                correct=current_q.answer
            )

    return render_template('student.html', question=current_q)