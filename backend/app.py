import os
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, request, redirect, send_file, session
from flask_sqlalchemy import SQLAlchemy
from datetime import date,timedelta
import pandas as pd
from dotenv import load_dotenv
from io import BytesIO
import openpyxl 
import pytz
from flask import jsonify


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv()

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "..", "frontend", "templates"),
    static_folder=os.path.join(BASE_DIR, "..", "frontend", "static")
)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret")

database_url = os.getenv("DATABASE_URL")

if not database_url:
    raise ValueError("DATABASE_URL is not set")

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
    "pool_timeout": 20,
}

db = SQLAlchemy(app)


# ================= MODELS =================

class Users(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(255))


from datetime import datetime
from sqlalchemy import extract

# ================= MODELS =================

class Entry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher = db.Column(db.String(100), nullable=False)
    student_name = db.Column(db.String(100), nullable=False)
    date = db.Column(db.Date, default=date.today)
    intime = db.Column(db.String(10), nullable=False)
    outtime = db.Column(db.String(10), nullable=False)
    classroom = db.Column(db.String(50), nullable=False)
    hours = db.Column(db.Float, default=0)
# ================= AUTH =================

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":

        username =request.form.get("username")
        password = generate_password_hash(request.form.get("password"))

        if Users.query.filter_by(username=username).first():
            return "User already exists"

        user = Users(username=username, password=password)
        db.session.add(user)
        db.session.commit()

        return redirect("/")

    return render_template("register.html")

@app.route("/login", methods=["POST"])
def aut():
    username = request.form["username"]
    password = request.form["password"]

    user = Users.query.filter_by(username=username).first()

    if user and check_password_hash(user.password, password):
        session["user"] = user.username
        return redirect("/dashboard")

    return "Invalid Credentials"


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/")
# ================= DASHBOARD =================
import pytz

@app.route("/dashboard")
def dashboard():

    if "user" not in session:
        return redirect("/")

    teacher = request.args.get("teacher")
    student = request.args.get("student")

    query = Entry.query

    if teacher:
        query = query.filter(Entry.teacher.contains(teacher))

    if student:
        query = query.filter(Entry.student_name.contains(student))

    entries = query.order_by(Entry.date.desc()).all()
    for e in entries:
        e.intime = datetime.strptime(e.intime, "%H:%M").strftime("%I:%M %p")
        e.outtime = datetime.strptime(e.outtime, "%H:%M").strftime("%I:%M %p")
    ist = pytz.timezone("Asia/Kolkata")
    today = datetime.now(ist).date()
    today_entries = Entry.query.filter_by(date=today).all()
    for e in today_entries:
        e.intime = datetime.strptime(e.intime, "%H:%M").strftime("%I:%M %p")
        e.outtime = datetime.strptime(e.outtime, "%H:%M").strftime("%I:%M %p")
    total_hours = sum(entry.hours for entry in today_entries)

    ist = pytz.timezone("Asia/Kolkata")
    current_time = datetime.now(ist).strftime("%H:%M")

    return render_template(
        "dashboard.html",
        entries=entries,
        total_hours=round(total_hours, 2),
        today_entries=today_entries,
        today_date=today,
        current_time=current_time
    )
    
@app.route("/calculation", methods=["GET", "POST"])
def calculation():

    if "user" not in session:
        return redirect("/")

    teachers = sorted({t[0].strip().title() for t in db.session.query(Entry.teacher).all()})


    monthly_entries = None
    monthly_total = 0
    selected_teacher = None
    from_date = None
    to_date = None

    if request.method == "POST":
        selected_teacher = request.form.get("teacher")
        from_date = request.form.get("from_date")
        to_date = request.form.get("to_date")

        if not selected_teacher or not from_date or not to_date:
            return "All fields required", 400

        from_date_obj = datetime.strptime(from_date, "%Y-%m-%d").date()
        to_date_obj = datetime.strptime(to_date, "%Y-%m-%d").date()

        if from_date_obj > to_date_obj:
            return "From date cannot be after To date", 400

        monthly_entries = Entry.query.filter(
            Entry.teacher == selected_teacher,
            Entry.date >= from_date_obj,
            Entry.date <= to_date_obj
        ).all()
        for e in monthly_entries:
            e.intime = datetime.strptime(e.intime, "%H:%M").strftime("%I:%M %p")
            e.outtime = datetime.strptime(e.outtime, "%H:%M").strftime("%I:%M %p")

        monthly_total = sum(e.hours for e in monthly_entries)

    return render_template(
        "calculation.html",
        teachers=teachers,
        monthly_entries=monthly_entries,
        monthly_total=round(monthly_total, 2),
        selected_teacher=selected_teacher,
        from_date=from_date,
        to_date=to_date
    )
# ================= ADD TEACHER =================

@app.route("/add_entry", methods=["POST"])
def add():

    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        teacher = request.form.get("teacher_name").strip().title()
        student = request.form.get("student_name")
        date_value = request.form.get("date")
        intime = request.form.get("in_time")
        outtime = request.form.get("out_time")
        classroom = request.form.get("room_number")

        # convert date
        entry_date = datetime.strptime(date_value, "%Y-%m-%d").date()

        # calculate hours
        total_hours = calculate_hours(intime, outtime)

        entry = Entry(
            teacher=teacher,
            student_name=student,
            date=entry_date,
            intime=intime,
            outtime=outtime,
            classroom=classroom,
            hours=total_hours
        )

        db.session.add(entry)
        db.session.commit()

        return jsonify({
            "status": "success",
            "id": entry.id,
            "teacher": entry.teacher,
            "student_name": entry.student_name,
            "date": entry.date.strftime("%d/%m/%Y"),
            "intime": datetime.strptime(entry.intime, "%H:%M").strftime("%I:%M %p"),
            "outtime": datetime.strptime(entry.outtime, "%H:%M").strftime("%I:%M %p"),
            "classroom": entry.classroom,
            "hours": entry.hours
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ================= EDIT =================
def calculate_hours(intime, outtime):
    fmt = "%H:%M"

    t1 = datetime.strptime(intime, fmt)
    t2 = datetime.strptime(outtime, fmt)

    if t2 < t1:
        t2 += timedelta(days=1)

    diff = t2 - t1

    return round(diff.total_seconds() / 3600, 2)
#@app.route("/download_month/<string:month>")
#@app.route("/download_month/<string:teacher>/<string:month>")
def download_month(month, teacher=None):

    if "user" not in session:
        return redirect("/")

    # Validate month
    try:
        year, month_number = month.split("-")
        year = int(year)
        month_number = int(month_number)
    except ValueError:
        return "Invalid month format. Use YYYY-MM", 400

    # Base query
    query = Entry.query.filter(
        extract('year', Entry.date) == year,
        extract('month', Entry.date) == month_number
    )

    # Apply teacher filter only if provided
    if teacher:
        query = query.filter(Entry.teacher == teacher)

    entries = query.all()

    if not entries:
        return "No data found", 404

    data = []
    for e in entries:
        data.append({
            "Date": e.date,
            "Teacher": e.teacher,
            "Student": e.student_name,
            "In Time": e.intime,
            "Out Time": e.outtime,
            "Hours": e.hours,
            "Classroom": e.classroom
        })

    df = pd.DataFrame(data)

    output = BytesIO()
    df.to_excel(output, index=False, engine="openpyxl")
    output.seek(0)

    filename = f"{teacher + '_' if teacher else ''}{month}.xlsx"

    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
# ================= DELETE =================
@app.route('/delete/<int:id>', methods=['DELETE'])
def delete_entry(id):
    entry = Entry.query.get_or_404(id)
    db.session.delete(entry)
    db.session.commit()
    return jsonify({"status": "success", "deleted_id": id})


@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit(id):
    if "user" not in session:
        return redirect("/")

    entry = Entry.query.get_or_404(id)

    if request.method == "POST":
        entry.teacher = request.form["teacher_name"]
        entry.student_name = request.form["student_name"]
        entry.date = datetime.strptime(request.form["date"], "%Y-%m-%d").date()
        entry.intime = request.form["in_time"]
        entry.outtime = request.form["out_time"]
        entry.classroom = request.form["room_number"]
        entry.hours = calculate_hours(entry.intime, entry.outtime)

        db.session.commit()
        return redirect("/dashboard")

    return render_template("edit.html", entry=entry)

@app.route("/download_range/<teacher>/<from_date>/<to_date>")
def download_range(teacher, from_date, to_date):

    if "user" not in session:
        return redirect("/")

    from_date_obj = datetime.strptime(from_date, "%Y-%m-%d").date()
    to_date_obj = datetime.strptime(to_date, "%Y-%m-%d").date()

    entries = Entry.query.filter(
        Entry.teacher == teacher,
        Entry.date >= from_date_obj,
        Entry.date <= to_date_obj
    ).all()

    data = []
    for e in entries:
        data.append({
            "Date": e.date,
            "Teacher": e.teacher,
            "Student": e.student_name,
            "In Time": e.intime,
            "Out Time": e.outtime,
            "Hours": e.hours,
            "Classroom": e.classroom
        })

    df = pd.DataFrame(data)

    output = BytesIO()
    df.to_excel(output, index=False, engine="openpyxl")
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name=f"{teacher}_{from_date}_to_{to_date}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

if __name__ == "__main__":
    app.run()