from flask import Flask, render_template, redirect, url_for, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask import session

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)

# ---------------- DATABASE MODEL ----------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    role = db.Column(db.String(20))  # student / instructor / admin
    instructor_id = db.Column(db.Integer)  #NEW
 
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
    return User.query.get(int(user_id))

# ---------------- HOME ----------------
@app.route('/')
def home():
    return redirect('/login')

# ---------------- REGISTER (STUDENT) ----------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    instructors = User.query.filter_by(role="instructor").all()

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        instructor_id = request.form['instructor']

        user = User(
            name=name,
            email=email,
            password="",
            role="student",
            instructor_id=instructor_id
        )

        db.session.add(user)
        db.session.commit()

        return redirect('/login')

    return render_template('register.html', instructors=instructors)

# ---------------- LOGIN ----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()

        if user:
            # STUDENT (no password)
            if user.role == "student":
                login_user(user)
                return redirect('/student')

            # INSTRUCTOR / ADMIN
            if user.password == password:
                login_user(user)

                if user.role == "instructor":
                    return redirect('/instructor')
                elif user.role == "admin":
                    return redirect('/admin')

        return "Invalid Login"

    return render_template('login.html')



# ---------------- INSTRUCTOR ----------------
@app.route('/instructor')
@login_required
def instructor():
    if current_user.role != "instructor":
        return "Access Denied"

    students = User.query.filter_by(role="student").all()
    return render_template('instructor.html', students=students)

# ---------------- ADMIN ----------------
@app.route('/admin')
@login_required
def admin():
    if current_user.role != "admin":
        return "Access Denied"

    users = User.query.all()
    questions = Question.query.all()
    results = Result.query.all()

    # Instructor mapping
    instructors = {
        u.id: u.name for u in User.query.filter_by(role="instructor").all()
    }

    # 📊 STATS
    total_students = User.query.filter_by(role="student").count()
    total_instructors = User.query.filter_by(role="instructor").count()
    total_questions = Question.query.count()

    # total attempts (unique attempt numbers)
    attempts = set([r.attempt for r in results])
    total_attempts = len(attempts)

    # average score
    correct = sum(1 for r in results if r.is_correct)
    total_answers = len(results)
    avg_score = round((correct / total_answers) * 100, 2) if total_answers > 0 else 0

    return render_template(
        'admin.html',
        users=users,
        questions=questions,
        results=results,
        instructors=instructors,
        total_students=total_students,
        total_instructors=total_instructors,
        total_questions=total_questions,
        total_attempts=total_attempts,
        avg_score=avg_score
    )
# ---------------- LOGOUT ----------------
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/login')

# ---------------- RUN ----------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()

        # CREATE DEFAULT ADMIN
        if not User.query.filter_by(email="admin@gmail.com").first():
            admin = User(name="Admin", email="admin@gmail.com", password="admin123", role="admin")
            instructor = User(name="Instructor", email="inst@gmail.com", password="inst123", role="instructor")

            db.session.add(admin)
            db.session.add(instructor)
            db.session.commit()

    if __name__ == "__main__":
         app.run()



@app.route('/add_question', methods=['GET', 'POST'])
@login_required
def add_question():
    if current_user.role != "admin":
        return "Access Denied"

    if request.method == 'POST':
        q = request.form['question']
        a = request.form['answer']

        new_q = Question(question=q, answer=a)
        db.session.add(new_q)
        db.session.commit()

        return "Question Added Successfully"

    return render_template('add_question.html')

# ---------------- STUDENT ----------------

@app.route('/student', methods=['GET', 'POST'])
@login_required
def student():
    if current_user.role != "student":
        return "Access Denied"

    if 'q_index' not in session:
        session['q_index'] = 0
        session['score'] = 0

    if 'attempt' not in session:
        session['attempt'] = 1

    questions = Question.query.all()

    if len(questions) == 0:
        return "No questions available"

    current_q = questions[session['q_index']]

    if request.method == 'POST':
        user_answer = request.form['answer']
        correct_answer = current_q.answer

        is_correct = (user_answer.strip().upper() == correct_answer.strip().upper())

        # Update score
        if is_correct:
            session['score'] += 1

        # Save result
        result = Result(
            student_id=current_user.id,
            question_id=current_q.id,
            selected_answer=user_answer,
            correct_answer=correct_answer,
            is_correct=is_correct,
            attempt=session['attempt']   # ✅ FIXED
        )
        db.session.add(result)
        db.session.commit()

        # Move to next question
        session['q_index'] += 1

        # If test finished
        if session['q_index'] >= len(questions):
            final_score = session['score']
            total = len(questions)
            current_attempt = session['attempt']

            # Increase attempt for next test
            session['attempt'] += 1 

            # Reset for next attempt
            session['q_index'] = 0
            session['score'] = 0

            return render_template(
                'final_score.html',
                score=final_score,
                total=total,
                attempt=current_attempt
            )

        # Otherwise show feedback
        return render_template(
            'feedback.html',
            is_correct=is_correct,
            correct_answer=correct_answer
        )

    return render_template('student.html', question=current_q)

# ---------------- PROGRESS----------------

@app.route('/progress')
@login_required
def progress():
    if current_user.role != "student":
        return "Access Denied"

    results = Result.query.filter_by(student_id=current_user.id).all()

    progress_data = {}

    for r in results:
        if r.attempt not in progress_data:
            progress_data[r.attempt] = {"correct": 0, "total": 0}

        progress_data[r.attempt]["total"] += 1
        if r.is_correct:
            progress_data[r.attempt]["correct"] += 1

    # Convert to lists for graph
    attempts = []
    scores = []

    for attempt in sorted(progress_data.keys()):
        attempts.append(attempt)
        scores.append(progress_data[attempt]["correct"])

    return render_template(
        'progress.html',
        attempts=attempts,
        scores=scores
    )


@app.route('/add_instructor', methods=['GET', 'POST'])
@login_required
def add_instructor():
    if current_user.role != "admin":
        return "Access Denied"

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        instructor = User(
            name=name,
            email=email,
            password=password,
            role="instructor"
        )

        db.session.add(instructor)
        db.session.commit()

        return "Instructor Added Successfully"

    return render_template('add_instructor.html')



    with app.app_context():
         db.create_all()