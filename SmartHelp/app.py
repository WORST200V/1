import os
from datetime import datetime
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-this-secret-before-deployment")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///smarthelp.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

ROLES = {"user": "Foydalanuvchi", "technician": "IT mutaxassisi", "admin": "Administrator"}
STATUSES = {
    "new": "Yangi",
    "assigned": "Biriktirilgan",
    "in_progress": "Jarayonda",
    "resolved": "Hal qilindi",
    "closed": "Yopilgan",
}
CATEGORIES = {
    "computer": "Kompyuter",
    "printer": "Printer",
    "network": "Tarmoq / internet",
    "software": "Dasturiy ta'minot",
    "other": "Boshqa",
}


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    created_tickets = db.relationship("Ticket", foreign_keys="Ticket.creator_id", backref="creator", lazy=True)
    assigned_tickets = db.relationship("Ticket", foreign_keys="Ticket.technician_id", backref="technician", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Device(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    inventory_number = db.Column(db.String(80), unique=True, nullable=False)
    room = db.Column(db.String(80), nullable=True)
    device_type = db.Column(db.String(40), nullable=False, default="computer")
    status = db.Column(db.String(30), nullable=False, default="working")
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(40), nullable=False, default="other")
    impact = db.Column(db.Integer, nullable=False, default=1)
    severity = db.Column(db.Integer, nullable=False, default=1)
    priority = db.Column(db.String(20), nullable=False, default="Past")
    status = db.Column(db.String(30), nullable=False, default="new")
    creator_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    technician_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    device_id = db.Column(db.Integer, db.ForeignKey("device.id"), nullable=True)
    resolution = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    device = db.relationship("Device", backref="tickets")
    history = db.relationship("TicketHistory", backref="ticket", lazy=True, cascade="all, delete-orphan")


class TicketHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("ticket.id"), nullable=False)
    changed_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    old_status = db.Column(db.String(30), nullable=True)
    new_status = db.Column(db.String(30), nullable=False)
    comment = db.Column(db.Text, nullable=True)
    changed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actor = db.relationship("User")


class Solution(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(40), nullable=False)
    problem = db.Column(db.String(180), nullable=False)
    recommended_solution = db.Column(db.Text, nullable=False)


def calculate_priority(impact, severity):
    """O'quv loyihasi uchun oddiy ballga asoslangan ustuvorlik algoritmi."""
    score = int(impact) + int(severity)
    if score >= 5:
        return "Yuqori"
    if score == 4:
        return "O'rta"
    return "Past"


@app.context_processor
def inject_globals():
    return {
        "current_user": get_current_user(),
        "roles": ROLES,
        "statuses": STATUSES,
        "categories": CATEGORIES,
    }


def get_current_user():
    user_id = session.get("user_id")
    return db.session.get(User, user_id) if user_id else None


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not get_current_user():
            flash("Davom etish uchun tizimga kiring.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def role_required(*allowed_roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = get_current_user()
            if not user:
                flash("Avval tizimga kiring.", "warning")
                return redirect(url_for("login"))
            if user.role not in allowed_roles:
                flash("Bu amal uchun huquqingiz yetarli emas.", "danger")
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)
        return wrapped
    return decorator


def add_history(ticket, old_status, new_status, comment=None):
    actor = get_current_user()
    if actor:
        db.session.add(TicketHistory(
            ticket_id=ticket.id,
            changed_by=actor.id,
            old_status=old_status,
            new_status=new_status,
            comment=comment
        ))


@app.route("/")
def index():
    if get_current_user():
        return redirect(url_for("dashboard"))
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or len(password) < 8:
            flash("Barcha maydonlarni to'ldiring. Parol kamida 8 belgidan iborat bo'lsin.", "danger")
            return render_template("register.html")
        if User.query.filter_by(email=email).first():
            flash("Bu email allaqachon ro'yxatdan o'tgan.", "danger")
            return render_template("register.html")
        user = User(name=name, email=email, role="user")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        session["user_id"] = user.id
        flash("Hisob yaratildi. Xush kelibsiz!", "success")
        return redirect(url_for("dashboard"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash("Email yoki parol noto'g'ri.", "danger")
            return render_template("login.html")
        session.clear()
        session["user_id"] = user.id
        flash("Tizimga muvaffaqiyatli kirdingiz.", "success")
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Tizimdan chiqdingiz.", "info")
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    user = get_current_user()
    query = Ticket.query
    if user.role == "user":
        query = query.filter_by(creator_id=user.id)
    elif user.role == "technician":
        query = query.filter((Ticket.technician_id == user.id) | (Ticket.technician_id.is_(None)))
    tickets = query.order_by(Ticket.created_at.desc()).limit(8).all()
    all_query = Ticket.query
    if user.role == "user":
        all_query = all_query.filter_by(creator_id=user.id)
    total = all_query.count()
    open_count = all_query.filter(Ticket.status.in_(["new", "assigned", "in_progress"])).count()
    resolved_count = all_query.filter(Ticket.status.in_(["resolved", "closed"])).count()
    device_count = Device.query.count() if user.role in ("admin", "technician") else None
    category_counts = []
    for key, label in CATEGORIES.items():
        count_q = all_query.filter_by(category=key).count()
        category_counts.append({"label": label, "count": count_q})
    return render_template(
        "dashboard.html", tickets=tickets, total=total, open_count=open_count,
        resolved_count=resolved_count, device_count=device_count,
        category_counts=category_counts
    )


@app.route("/tickets")
@login_required
def tickets():
    user = get_current_user()
    query = Ticket.query
    if user.role == "user":
        query = query.filter_by(creator_id=user.id)
    elif user.role == "technician":
        query = query.filter((Ticket.technician_id == user.id) | (Ticket.technician_id.is_(None)))
    status = request.args.get("status", "")
    category = request.args.get("category", "")
    search = request.args.get("q", "").strip()
    if status in STATUSES:
        query = query.filter_by(status=status)
    if category in CATEGORIES:
        query = query.filter_by(category=category)
    if search:
        query = query.filter(db.or_(Ticket.title.ilike(f"%{search}%"), Ticket.description.ilike(f"%{search}%")))
    items = query.order_by(Ticket.created_at.desc()).all()
    return render_template("tickets.html", tickets=items, selected_status=status, selected_category=category, search=search)


@app.route("/tickets/new", methods=["GET", "POST"])
@login_required
def new_ticket():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "other")
        device_id = request.form.get("device_id") or None
        try:
            impact = int(request.form.get("impact", 1))
            severity = int(request.form.get("severity", 1))
        except ValueError:
            impact, severity = 1, 1
        if not title or not description:
            flash("Sarlavha va muammo tavsifini kiriting.", "danger")
            return redirect(url_for("new_ticket"))
        if category not in CATEGORIES or impact not in (1, 2, 3) or severity not in (1, 2, 3):
            flash("Kiritilgan qiymatlardan biri noto'g'ri.", "danger")
            return redirect(url_for("new_ticket"))
        device = db.session.get(Device, int(device_id)) if device_id and device_id.isdigit() else None
        ticket = Ticket(
            title=title, description=description, category=category,
            impact=impact, severity=severity,
            priority=calculate_priority(impact, severity),
            creator_id=get_current_user().id,
            device_id=device.id if device else None,
            status="new"
        )
        db.session.add(ticket)
        db.session.flush()
        add_history(ticket, None, "new", "Murojaat yaratildi")
        db.session.commit()
        flash(f"#{ticket.id} murojaat yaratildi.", "success")
        return redirect(url_for("ticket_detail", ticket_id=ticket.id))
    devices = Device.query.order_by(Device.name).all()
    return render_template("ticket_new.html", devices=devices)


@app.route("/tickets/<int:ticket_id>")
@login_required
def ticket_detail(ticket_id):
    ticket = db.get_or_404(Ticket, ticket_id)
    user = get_current_user()
    if user.role == "user" and ticket.creator_id != user.id:
        flash("Bu murojaatni ko'rishga ruxsatingiz yo'q.", "danger")
        return redirect(url_for("tickets"))
    technicians = User.query.filter(User.role.in_(["technician", "admin"])).order_by(User.name).all()
    return render_template("ticket_detail.html", ticket=ticket, technicians=technicians)


@app.route("/tickets/<int:ticket_id>/update", methods=["POST"])
@login_required
def update_ticket(ticket_id):
    ticket = db.get_or_404(Ticket, ticket_id)
    user = get_current_user()
    if user.role == "user":
        flash("Murojaatni faqat IT mutaxassisi yoki administrator yangilashi mumkin.", "danger")
        return redirect(url_for("ticket_detail", ticket_id=ticket.id))
    old_status = ticket.status
    new_status = request.form.get("status", ticket.status)
    if new_status not in STATUSES:
        flash("Murojaat holati noto'g'ri.", "danger")
        return redirect(url_for("ticket_detail", ticket_id=ticket.id))
    ticket.status = new_status
    if user.role == "admin" or user.role == "technician":
        assignee = request.form.get("technician_id", "")
        if assignee.isdigit():
            target = db.session.get(User, int(assignee))
            if target and target.role in ("technician", "admin"):
                ticket.technician_id = target.id
                if ticket.status == "new":
                    ticket.status = "assigned"
        resolution = request.form.get("resolution", "").strip()
        if resolution:
            ticket.resolution = resolution
    add_history(ticket, old_status, ticket.status, request.form.get("comment", "").strip() or None)
    db.session.commit()
    flash("Murojaat yangilandi.", "success")
    return redirect(url_for("ticket_detail", ticket_id=ticket.id))


@app.route("/devices")
@login_required
@role_required("admin", "technician")
def devices():
    items = Device.query.order_by(Device.name).all()
    return render_template("devices.html", devices=items)


@app.route("/devices/new", methods=["GET", "POST"])
@login_required
@role_required("admin")
def new_device():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        inventory_number = request.form.get("inventory_number", "").strip()
        room = request.form.get("room", "").strip()
        device_type = request.form.get("device_type", "computer")
        notes = request.form.get("notes", "").strip()
        if not name or not inventory_number or device_type not in CATEGORIES:
            flash("Qurilma nomi, inventar raqami va turi kerak.", "danger")
            return redirect(url_for("new_device"))
        if Device.query.filter_by(inventory_number=inventory_number).first():
            flash("Bu inventar raqami allaqachon mavjud.", "danger")
            return redirect(url_for("new_device"))
        db.session.add(Device(name=name, inventory_number=inventory_number, room=room, device_type=device_type, notes=notes))
        db.session.commit()
        flash("Qurilma qo'shildi.", "success")
        return redirect(url_for("devices"))
    return render_template("device_new.html")


@app.route("/admin/users", methods=["GET", "POST"])
@login_required
@role_required("admin")
def users():
    if request.method == "POST":
        user_id = request.form.get("user_id", "")
        role = request.form.get("role", "")
        target = db.session.get(User, int(user_id)) if user_id.isdigit() else None
        if target and role in ROLES:
            target.role = role
            db.session.commit()
            flash("Foydalanuvchi roli yangilandi.", "success")
        else:
            flash("Foydalanuvchi yoki rol noto'g'ri.", "danger")
        return redirect(url_for("users"))
    items = User.query.order_by(User.created_at.desc()).all()
    return render_template("users.html", users=items)


@app.route("/api/health")
def api_health():
    return jsonify({"status": "ok", "application": "SmartHelp"})


@app.cli.command("init-db")
def init_db():
    """Jadvallarni yaratish va demo ma'lumotlarini qo'shish."""
    db.create_all()
    if not User.query.filter_by(email="azikkoder06@smarthelp.local").first():
        admin = User(name="SmartHelp Administrator", email="admin@smarthelp.local", role="admin")
        admin.set_password(os.getenv("DEMO_ADMIN_PASSWORD", "Admin123!"))
        tech = User(name="IT mutaxassisi", email="tech@smarthelp.local", role="technician")
        tech.set_password(os.getenv("DEMO_TECH_PASSWORD", "Tech12345!"))
        user = User(name="Demo foydalanuvchi", email="user@smarthelp.local", role="user")
        user.set_password(os.getenv("DEMO_USER_PASSWORD", "User12345!"))
        db.session.add_all([admin, tech, user])
        db.session.flush()
        if not Device.query.first():
            db.session.add_all([
                Device(name="Auditoriya kompyuteri", inventory_number="PC-001", room="204", device_type="computer"),
                Device(name="Tarmoq printeri", inventory_number="PR-001", room="201", device_type="printer"),
                Device(name="Wi-Fi router", inventory_number="NET-001", room="Server xona", device_type="network"),
            ])
        if not Solution.query.first():
            db.session.add_all([
                Solution(category="network", problem="Internetga ulanmayapti", recommended_solution="Kabel yoki Wi-Fi ulanishini, IP sozlamalarini va DNS holatini tekshiring."),
                Solution(category="computer", problem="Kompyuter sekin ishlayapti", recommended_solution="Task Manager orqali CPU, RAM va disk yuklanishini tekshiring."),
                Solution(category="printer", problem="Printer chop etmayapti", recommended_solution="Quvvat, tarmoq ulanishi, qog'oz va printer navbatini tekshiring."),
            ])
        db.session.commit()
    print("SmartHelp bazasi tayyor. Demo hisoblar README.md faylida berilgan.")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=os.getenv("FLASK_DEBUG", "1") == "1")
