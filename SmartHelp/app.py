import os
from datetime import datetime
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

from translations import (
    LANGUAGES,
    get_text,
    get_role_name,
    get_status_name,
    get_category_name,
    ROLES_TRANSLATIONS,
    STATUSES_TRANSLATIONS,
    CATEGORIES_TRANSLATIONS,
)

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-this-secret-before-deployment")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///smarthelp.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

ROLES = {
    "superadmin": "Super Administrator",
    "admin": "Administrator",
    "technician": "IT mutaxassisi",
    "user": "Foydalanuvchi",
}

STATUSES = {
    "new": "Yangi",
    "assigned": "Biriktirilgan",
    "in_progress": "Jarayonda",
    "pending_approval": "Tasdiqlash kutilmoqda",
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


class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(80), unique=True, nullable=False)
    floor = db.Column(db.String(40), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    devices = db.relationship("Device", backref="room_rel", cascade="all, delete-orphan", lazy=True, order_by="Device.name")

    @property
    def active_devices(self):
        return [d for d in self.devices if not d.is_deleted]


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

    @property
    def initials(self):
        parts = self.name.strip().split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[1][0]).upper()
        return self.name[:2].upper() if self.name else "U"


class Device(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    inventory_number = db.Column(db.String(80), unique=True, nullable=False)
    room = db.Column(db.String(80), nullable=True)
    room_id = db.Column(db.Integer, db.ForeignKey("room.id"), nullable=True)
    device_type = db.Column(db.String(40), nullable=False, default="computer")
    status = db.Column(db.String(30), nullable=False, default="working")
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)


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
    score = int(impact) + int(severity)
    if score >= 5:
        return "Yuqori"
    if score == 4:
        return "O'rta"
    return "Past"


@app.context_processor
def inject_globals():
    lang = session.get("lang", "uz")
    if lang not in LANGUAGES:
        lang = "uz"

    # Chiqitdondagi elementlar soni
    trash_count = 0
    try:
        trash_count = (
            Room.query.filter_by(is_deleted=True).count()
            + Device.query.filter_by(is_deleted=True).count()
        )
    except Exception:
        pass

    return {
        "current_user": get_current_user(),
        "roles": ROLES,
        "statuses": STATUSES,
        "categories": CATEGORIES,
        "current_lang": lang,
        "languages": LANGUAGES,
        "t": lambda k, default=None: get_text(k, lang, default),
        "_": lambda k, default=None: get_text(k, lang, default),
        "get_role_label": lambda r: get_role_name(r, lang),
        "get_status_label": lambda s: get_status_name(s, lang),
        "get_category_label": lambda c: get_category_name(c, lang),
        "roles_translated": ROLES_TRANSLATIONS.get(lang, ROLES_TRANSLATIONS["uz"]),
        "statuses_translated": STATUSES_TRANSLATIONS.get(lang, STATUSES_TRANSLATIONS["uz"]),
        "categories_translated": CATEGORIES_TRANSLATIONS.get(lang, CATEGORIES_TRANSLATIONS["uz"]),
        "trash_count": trash_count,
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


@app.route("/set-language/<lang>")
def set_language(lang):
    if lang in LANGUAGES:
        session["lang"] = lang
    return redirect(request.referrer or url_for("index"))


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


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = get_current_user()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        new_password = request.form.get("new_password", "")
        if not name:
            flash("Ism-familiya bo'sh bo'lishi mumkin emas.", "danger")
            return render_template("profile.html", user=user)
        user.name = name
        if new_password:
            if len(new_password) < 8:
                flash("Yangi parol kamida 8 belgidan iborat bo'lishi kerak.", "danger")
                return render_template("profile.html", user=user)
            user.set_password(new_password)
        db.session.commit()
        flash("Profil ma'lumotlari muvaffaqiyatli yangilandi.", "success")
        return redirect(url_for("profile"))
    return render_template("profile.html", user=user)


@app.route("/dashboard")
@login_required
def dashboard():
    user = get_current_user()

    if user.role == "user":
        user_tickets = Ticket.query.filter_by(creator_id=user.id)
        tickets = user_tickets.order_by(Ticket.created_at.desc()).limit(8).all()
        total = user_tickets.count()
        open_count = user_tickets.filter(Ticket.status.in_(["new", "assigned", "in_progress"])).count()
        resolved_count = user_tickets.filter(Ticket.status.in_(["resolved", "closed"])).count()
        stats = {
            "card1_label": "Jami murojaatlar",
            "card1_val": total,
            "card1_sub": "Siz ko‘rishingiz mumkin bo‘lgan murojaatlar",
            "card1_theme": "purple",
            "card2_label": "Ochiq murojaatlar",
            "card2_val": open_count,
            "card2_sub": "Yangi yoki hal qilinayotgan",
            "card2_theme": "warn",
            "card3_label": "Hal qilingan",
            "card3_val": resolved_count,
            "card3_sub": "Yakunlangan ishlar",
            "card3_theme": "ok",
        }
        category_counts = []
        for key, label in CATEGORIES.items():
            count_q = user_tickets.filter_by(category=key).count()
            category_counts.append({"label": label, "count": count_q})

    elif user.role == "technician":
        tech_tickets = Ticket.query.filter_by(technician_id=user.id)
        tickets = tech_tickets.order_by(Ticket.created_at.desc()).limit(8).all()
        assigned_count = tech_tickets.filter_by(status="assigned").count()
        in_progress_count = tech_tickets.filter_by(status="in_progress").count()
        resolved_count = tech_tickets.filter(Ticket.status.in_(["pending_approval", "resolved", "closed"])).count()
        total = tech_tickets.count()
        stats = {
            "card1_label": "Biriktirilgan murojaatlar",
            "card1_val": assigned_count,
            "card1_sub": "Admin sizga biriktirgan ishlar",
            "card1_theme": "purple",
            "card2_label": "Jarayonda",
            "card2_val": in_progress_count,
            "card2_sub": "Tuzatish ishlari olib borilmoqda",
            "card2_theme": "warn",
            "card3_label": "Hal qilingan / Kutilmoqda",
            "card3_val": resolved_count,
            "card3_sub": "Tugallangan va tasdiq kutilayotgan",
            "card3_theme": "ok",
        }
        category_counts = []
        for key, label in CATEGORIES.items():
            count_q = tech_tickets.filter_by(category=key).count()
            category_counts.append({"label": label, "count": count_q})

    else:  # admin or superadmin
        all_tickets = Ticket.query
        tickets = all_tickets.order_by(Ticket.created_at.desc()).limit(8).all()
        total = all_tickets.count()
        open_count = all_tickets.filter(Ticket.status.in_(["new", "assigned", "in_progress"])).count()
        resolved_count = all_tickets.filter(Ticket.status.in_(["resolved", "closed"])).count()
        room_count = Room.query.filter_by(is_deleted=False).count()
        stats = {
            "card1_label": "Jami murojaatlar",
            "card1_val": total,
            "card1_sub": "Siz ko‘rishingiz mumkin bo‘lgan murojaatlar",
            "card1_theme": "purple",
            "card2_label": "Ochiq murojaatlar",
            "card2_val": open_count,
            "card2_sub": "Yangi yoki hal qilinayotgan",
            "card2_theme": "warn",
            "card3_label": "Hal qilingan",
            "card3_val": resolved_count,
            "card3_sub": "Yakunlangan ishlar",
            "card3_theme": "ok",
            "card4_label": "Xonalar (Inventar)",
            "card4_val": room_count,
            "card4_sub": "Katalogdagi xonalar soni",
            "card4_theme": "blue",
        }
        category_counts = []
        for key, label in CATEGORIES.items():
            count_q = all_tickets.filter_by(category=key).count()
            category_counts.append({"label": label, "count": count_q})

    pending_tickets = (
        Ticket.query.filter_by(status="pending_approval").order_by(Ticket.updated_at.desc()).all()
        if user.role in ("admin", "superadmin")
        else []
    )

    return render_template(
        "dashboard.html",
        tickets=tickets,
        stats=stats,
        total=total,
        category_counts=category_counts,
        pending_tickets=pending_tickets,
    )


@app.route("/tickets")
@login_required
def tickets():
    user = get_current_user()
    query = Ticket.query
    if user.role == "user":
        query = query.filter_by(creator_id=user.id)
    elif user.role == "technician":
        query = query.filter_by(technician_id=user.id)
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
    rooms = Room.query.filter_by(is_deleted=False).order_by(Room.number.asc()).all()
    devices = Device.query.filter_by(is_deleted=False).order_by(Device.name.asc()).all()
    return render_template("ticket_new.html", rooms=rooms, devices=devices)


@app.route("/tickets/<int:ticket_id>")
@login_required
def ticket_detail(ticket_id):
    ticket = db.get_or_404(Ticket, ticket_id)
    user = get_current_user()
    if user.role == "user" and ticket.creator_id != user.id:
        flash("Bu murojaatni ko'rishga ruxsatingiz yo'q.", "danger")
        return redirect(url_for("tickets"))
    if user.role == "technician" and ticket.technician_id != user.id:
        flash("Bu murojaat sizga biriktirilmagan.", "danger")
        return redirect(url_for("tickets"))
    technicians = User.query.filter(User.role.in_(["technician", "admin", "superadmin"])).order_by(User.name).all()
    return render_template("ticket_detail.html", ticket=ticket, technicians=technicians)


@app.route("/tickets/<int:ticket_id>/update", methods=["POST"])
@login_required
def update_ticket(ticket_id):
    ticket = db.get_or_404(Ticket, ticket_id)
    user = get_current_user()
    if user.role == "user":
        flash("Murojaatni faqat IT mutaxassisi yoki administrator yangilashi mumkin.", "danger")
        return redirect(url_for("ticket_detail", ticket_id=ticket.id))
    if user.role == "technician" and ticket.technician_id != user.id:
        flash("Bu murojaat sizga biriktirilmagan.", "danger")
        return redirect(url_for("tickets"))

    old_status = ticket.status
    new_status = request.form.get("status", ticket.status)
    comment = request.form.get("comment", "").strip()
    resolution = request.form.get("resolution", "").strip()

    if user.role == "technician":
        allowed_tech_statuses = ["assigned", "in_progress", "pending_approval"]
        if new_status not in allowed_tech_statuses:
            flash("Noto'g'ri holat tanlandi.", "danger")
            return redirect(url_for("ticket_detail", ticket_id=ticket.id))
        ticket.status = new_status
        if resolution:
            ticket.resolution = resolution
        if new_status == "pending_approval" and not comment:
            comment = "Muammo hal qilindi va tasdiqlash uchun adminga yuborildi."

    elif user.role in ("admin", "superadmin"):
        if new_status not in STATUSES:
            flash("Murojaat holati noto'g'ri.", "danger")
            return redirect(url_for("ticket_detail", ticket_id=ticket.id))
        ticket.status = new_status
        assignee = request.form.get("technician_id", "")
        if assignee.isdigit():
            target = db.session.get(User, int(assignee))
            if target and target.role in ("technician", "admin", "superadmin"):
                ticket.technician_id = target.id
                if ticket.status == "new":
                    ticket.status = "assigned"
        if resolution:
            ticket.resolution = resolution

    add_history(ticket, old_status, ticket.status, comment or None)
    db.session.commit()
    flash("Murojaat holati muvaffaqiyatli saqlandi.", "success")
    return redirect(url_for("ticket_detail", ticket_id=ticket.id))


@app.route("/tickets/<int:ticket_id>/approve", methods=["POST"])
@login_required
@role_required("admin", "superadmin")
def approve_ticket(ticket_id):
    ticket = db.get_or_404(Ticket, ticket_id)
    old_status = ticket.status
    ticket.status = "closed"
    add_history(ticket, old_status, "closed", "Administrator tomonidan tasdiqlandi va yopildi.")
    db.session.commit()
    flash(f"#{ticket.id} murojaat muvaffaqiyatli tasdiqlandi va yopildi.", "success")
    return redirect(url_for("ticket_detail", ticket_id=ticket.id))


# ==========================================================================
# Xonalar va Qurilmalar inventari (Rooms & Devices Catalog)
# Oddiy foydalanuvchilar (user) ham ko'ra oladi!
# ==========================================================================
@app.route("/devices")
@login_required
def devices():
    rooms = Room.query.filter_by(is_deleted=False).order_by(Room.number.asc()).all()
    unassigned_devices = Device.query.filter_by(is_deleted=False, room_id=None).all()
    return render_template("devices.html", rooms=rooms, unassigned_devices=unassigned_devices)


@app.route("/rooms/new", methods=["POST"])
@login_required
@role_required("admin", "superadmin")
def new_room():
    number = request.form.get("number", "").strip()
    floor = request.form.get("floor", "").strip()
    notes = request.form.get("notes", "").strip()
    if not number:
        flash("Xona raqami yoki nomini kiriting.", "danger")
        return redirect(url_for("devices"))
    existing = Room.query.filter_by(number=number).first()
    if existing:
        if existing.is_deleted:
            # Agar oldin o'chirilgan bo'lsa, uni tiklaymiz
            existing.is_deleted = False
            existing.deleted_at = None
            existing.floor = floor
            existing.notes = notes
            db.session.commit()
            flash(f"'{number}' xonasi chiqitdondan qaytarildi va yangilandi.", "success")
            return redirect(url_for("devices"))
        flash("Bu xona allaqachon mavjud.", "danger")
        return redirect(url_for("devices"))
    room = Room(number=number, floor=floor, notes=notes)
    db.session.add(room)
    db.session.commit()
    flash(f"'{number}' xonasi katalogga qo'shildi.", "success")
    return redirect(url_for("devices"))


@app.route("/rooms/<int:room_id>")
@login_required
def room_detail(room_id):
    room = db.get_or_404(Room, room_id)
    if room.is_deleted:
        flash("Bu xona chiqitdonga o'tkazilgan.", "warning")
        return redirect(url_for("devices"))
    return render_template("room_detail.html", room=room)


@app.route("/rooms/<int:room_id>/edit", methods=["POST"])
@login_required
@role_required("admin", "superadmin")
def edit_room(room_id):
    room = db.get_or_404(Room, room_id)
    number = request.form.get("number", "").strip()
    floor = request.form.get("floor", "").strip()
    notes = request.form.get("notes", "").strip()
    if not number:
        flash("Xona raqami bo'sh bo'lishi mumkin emas.", "danger")
        return redirect(url_for("devices"))
    existing = Room.query.filter_by(number=number).first()
    if existing and existing.id != room.id:
        flash("Bu xona raqami allaqachon mavjud.", "danger")
        return redirect(url_for("devices"))
    room.number = number
    room.floor = floor
    room.notes = notes
    db.session.commit()
    flash("Xona ma'lumotlari yangilandi.", "success")
    return redirect(url_for("devices"))


@app.route("/rooms/<int:room_id>/delete", methods=["POST"])
@login_required
@role_required("admin", "superadmin")
def delete_room(room_id):
    room = db.get_or_404(Room, room_id)
    name = room.number
    now = datetime.utcnow()
    room.is_deleted = True
    room.deleted_at = now
    # Xonaga tegishli qurilmalar ham soft-delete bo'ladi
    for d in room.devices:
        d.is_deleted = True
        d.deleted_at = now
    db.session.commit()
    flash(f"'{name}' xonasi va undagi qurilmalar chiqitdonga o'tkazildi.", "info")
    return redirect(url_for("devices"))


@app.route("/rooms/<int:room_id>/devices/new", methods=["POST"])
@login_required
@role_required("admin", "superadmin")
def new_room_device(room_id):
    room = db.get_or_404(Room, room_id)
    name = request.form.get("name", "").strip()
    inventory_number = request.form.get("inventory_number", "").strip()
    device_type = request.form.get("device_type", "computer")
    status = request.form.get("status", "working")
    notes = request.form.get("notes", "").strip()
    if not name or not inventory_number:
        flash("Qurilma nomi va inventar raqami to'ldirilishi shart.", "danger")
        return redirect(url_for("room_detail", room_id=room.id))
    existing = Device.query.filter_by(inventory_number=inventory_number).first()
    if existing:
        if existing.is_deleted:
            existing.is_deleted = False
            existing.deleted_at = None
            existing.name = name
            existing.room = room.number
            existing.room_id = room.id
            existing.device_type = device_type
            existing.status = status
            existing.notes = notes
            db.session.commit()
            flash(f"'{name}' qurilmasi chiqitdondan qaytarildi va {room.number}ga biriktirildi.", "success")
            return redirect(url_for("room_detail", room_id=room.id))
        flash("Bu inventar raqami allaqachon mavjud.", "danger")
        return redirect(url_for("room_detail", room_id=room.id))
    device = Device(
        name=name,
        inventory_number=inventory_number,
        room=room.number,
        room_id=room.id,
        device_type=device_type,
        status=status,
        notes=notes
    )
    db.session.add(device)
    db.session.commit()
    flash(f"'{name}' qurilmasi {room.number}ga qo'shildi.", "success")
    return redirect(url_for("room_detail", room_id=room.id))


@app.route("/devices/<int:device_id>/edit", methods=["POST"])
@login_required
@role_required("admin", "superadmin")
def edit_device(device_id):
    device = db.get_or_404(Device, device_id)
    name = request.form.get("name", "").strip()
    inventory_number = request.form.get("inventory_number", "").strip()
    device_type = request.form.get("device_type", device.device_type)
    status = request.form.get("status", device.status)
    notes = request.form.get("notes", "").strip()
    if not name or not inventory_number:
        flash("Qurilma nomi va inventar raqami kerak.", "danger")
        return redirect(url_for("room_detail", room_id=device.room_id) if device.room_id else url_for("devices"))
    existing = Device.query.filter_by(inventory_number=inventory_number).first()
    if existing and existing.id != device.id:
        flash("Bu inventar raqami boshqa qurilmaga tegishli.", "danger")
        return redirect(url_for("room_detail", room_id=device.room_id) if device.room_id else url_for("devices"))
    device.name = name
    device.inventory_number = inventory_number
    device.device_type = device_type
    device.status = status
    device.notes = notes
    db.session.commit()
    flash("Qurilma ma'lumotlari yangilandi.", "success")
    return redirect(url_for("room_detail", room_id=device.room_id) if device.room_id else url_for("devices"))


@app.route("/devices/<int:device_id>/delete", methods=["POST"])
@login_required
@role_required("admin", "superadmin")
def delete_device(device_id):
    device = db.get_or_404(Device, device_id)
    room_id = device.room_id
    device.is_deleted = True
    device.deleted_at = datetime.utcnow()
    db.session.commit()
    flash(f"'{device.name}' qurilmasi chiqitdonga o'tkazildi.", "info")
    return redirect(url_for("room_detail", room_id=room_id) if room_id else url_for("devices"))


# ==========================================================================
# Chiqitdon (Trash / Recycle Bin)
# Faqat Super Admin va Adminlar uchun
# ==========================================================================
@app.route("/trash")
@login_required
@role_required("admin", "superadmin")
def trash():
    deleted_rooms = Room.query.filter_by(is_deleted=True).order_by(Room.deleted_at.desc()).all()
    deleted_devices = Device.query.filter_by(is_deleted=True).order_by(Device.deleted_at.desc()).all()
    return render_template("trash.html", deleted_rooms=deleted_rooms, deleted_devices=deleted_devices)


@app.route("/trash/room/<int:room_id>/restore", methods=["POST"])
@login_required
@role_required("admin", "superadmin")
def restore_room(room_id):
    room = db.get_or_404(Room, room_id)
    room.is_deleted = False
    room.deleted_at = None
    for d in room.devices:
        d.is_deleted = False
        d.deleted_at = None
    db.session.commit()
    flash(f"'{room.number}' xonasi va uning qurilmalari tiklandi.", "success")
    return redirect(url_for("trash"))


@app.route("/trash/room/<int:room_id>/purge", methods=["POST"])
@login_required
@role_required("admin", "superadmin")
def purge_room(room_id):
    room = db.get_or_404(Room, room_id)
    name = room.number
    db.session.delete(room)
    db.session.commit()
    flash(f"'{name}' xonasi butkul o'chirildi.", "info")
    return redirect(url_for("trash"))


@app.route("/trash/device/<int:device_id>/restore", methods=["POST"])
@login_required
@role_required("admin", "superadmin")
def restore_device(device_id):
    device = db.get_or_404(Device, device_id)
    device.is_deleted = False
    device.deleted_at = None
    # Agar xonasi ham o'chirilgan bo'lsa, xonani ham tiklaymiz
    if device.room_rel and device.room_rel.is_deleted:
        device.room_rel.is_deleted = False
        device.room_rel.deleted_at = None
    db.session.commit()
    flash(f"'{device.name}' qurilmasi tiklandi.", "success")
    return redirect(url_for("trash"))


@app.route("/trash/device/<int:device_id>/purge", methods=["POST"])
@login_required
@role_required("admin", "superadmin")
def purge_device(device_id):
    device = db.get_or_404(Device, device_id)
    name = device.name
    db.session.delete(device)
    db.session.commit()
    flash(f"'{name}' qurilmasi butkul o'chirildi.", "info")
    return redirect(url_for("trash"))


@app.route("/trash/clear-all", methods=["POST"])
@login_required
@role_required("admin", "superadmin")
def clear_all_trash():
    del_devices = Device.query.filter_by(is_deleted=True).all()
    for d in del_devices:
        db.session.delete(d)
    del_rooms = Room.query.filter_by(is_deleted=True).all()
    for r in del_rooms:
        db.session.delete(r)
    db.session.commit()
    flash("Chiqitdon to'liq tozalandi.", "info")
    return redirect(url_for("trash"))


# ==========================================================================
# Foydalanuvchilar va rollar boshqaruvi
# Super Admin: rollarni o'zgartira oladi, yangi xodim qo'sha oladi, o'chira oladi.
# Admin: faqat foydalanuvchilar ro'yxatini ko'ra oladi (o'zgartira olmaydi).
# ==========================================================================
@app.route("/admin/users", methods=["GET", "POST"])
@login_required
@role_required("admin", "superadmin")
def users():
    current_user = get_current_user()
    if request.method == "POST":
        # FAQAT superadmin foydalanuvchi rolini o'zgartirishi mumkin!
        if current_user.role != "superadmin":
            flash("Foydalanuvchilar rolini faqat Super Administrator o'zgartirishi mumkin.", "danger")
            return redirect(url_for("users"))

        user_id = request.form.get("user_id", "")
        role = request.form.get("role", "")
        target = db.session.get(User, int(user_id)) if user_id.isdigit() else None
        if target and role in ROLES:
            if target.id == current_user.id and role != "superadmin":
                flash("O'zingizning super-admin rolingizni pasaytira olmaysiz.", "warning")
            else:
                target.role = role
                db.session.commit()
                flash(f"'{target.name}' foydalanuvchisining roli yangilandi.", "success")
        else:
            flash("Foydalanuvchi yoki rol noto'g'ri.", "danger")
        return redirect(url_for("users"))

    items = User.query.order_by(User.created_at.desc()).all()
    return render_template("users.html", users=items)


@app.route("/admin/users/new", methods=["POST"])
@login_required
@role_required("superadmin")
def new_user_by_superadmin():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    role = request.form.get("role", "user")

    if not name or not email or len(password) < 8:
        flash("Barcha maydonlarni to'ldiring. Parol kamida 8 belgidan iborat bo'lsin.", "danger")
        return redirect(url_for("users"))

    if role not in ROLES:
        role = "user"

    if User.query.filter_by(email=email).first():
        flash("Ushbu email bilan foydalanuvchi allaqachon mavjud.", "danger")
        return redirect(url_for("users"))

    new_user = User(name=name, email=email, role=role)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()
    flash(f"Yangi foydalanuvchi '{name}' ({ROLES.get(role, role)}) muvaffaqiyatli qo'shildi.", "success")
    return redirect(url_for("users"))


@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@login_required
@role_required("superadmin")
def delete_user_by_superadmin(user_id):
    current_user = get_current_user()
    if user_id == current_user.id:
        flash("O'z profilingizni o'chira olmaysiz.", "danger")
        return redirect(url_for("users"))

    target = db.get_or_404(User, user_id)
    name = target.name
    db.session.delete(target)
    db.session.commit()
    flash(f"'{name}' foydalanuvchisi tizimdan o'chirildi.", "info")
    return redirect(url_for("users"))


@app.route("/api/health")
def api_health():
    return jsonify({"status": "ok", "application": "SmartHelp"})


@app.cli.command("init-db")
def init_db():
    db.create_all()
    if not User.query.filter_by(email="admin@smarthelp.local").first() and not User.query.filter_by(email="azikkoder06@smarthelp.local").first():
        superadmin = User(name="SmartHelp Super Administrator", email="admin@smarthelp.local", role="superadmin")
        superadmin.set_password(os.getenv("DEMO_ADMIN_PASSWORD", "Admin123!"))
        tech = User(name="IT mutaxassisi", email="tech@smarthelp.local", role="technician")
        tech.set_password(os.getenv("DEMO_TECH_PASSWORD", "Tech12345!"))
        user = User(name="Demo foydalanuvchi", email="user@smarthelp.local", role="user")
        user.set_password(os.getenv("DEMO_USER_PASSWORD", "User12345!"))
        db.session.add_all([superadmin, tech, user])
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

    if not Room.query.first():
        r204 = Room(number="204-auditoriya", floor="2-qavat")
        r205 = Room(number="205-auditoriya", floor="2-qavat")
        r302 = Room(number="302-auditoriya", floor="3-qavat")
        r_srv = Room(number="Server xona", floor="1-qavat")
        db.session.add_all([r204, r205, r302, r_srv])
        db.session.flush()

        for d in Device.query.all():
            if not d.room_id:
                if "204" in (d.room or "") or "204" in d.name:
                    d.room_id = r204.id
                elif "205" in (d.room or "") or "205" in d.name:
                    d.room_id = r205.id
                elif "302" in (d.room or "") or "302" in d.name:
                    d.room_id = r302.id
                elif "server" in (d.room or "").lower():
                    d.room_id = r_srv.id
                else:
                    d.room_id = r204.id

        db.session.commit()
    print("SmartHelp bazasi tayyor. Demo hisoblar README.md faylida berilgan.")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=os.getenv("FLASK_DEBUG", "1") == "1")
