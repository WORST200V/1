from app import app, db, User

with app.app_context():
    print("Avval bazada:")
    for u in User.query.all():
        print(" ", u.id, u.email, u.role)

    yangilar = [
        ("azikkoder06@smarthelp.local", "aziz2006", "admin", "SmartHelp Administrator"),
        ("ilhomjon05@smarthelp.local", "ilhom2005", "technician", "IT mutaxassisi"),
    ]

    for email, parol, rol, ism in yangilar:
        u = User.query.filter_by(email=email).first()
        if u:
            u.set_password(parol)
            u.role = rol
            print("Yangilandi:", email)
        else:
            u = User(name=ism, email=email, role=rol)
            u.set_password(parol)
            db.session.add(u)
            print("Yaratildi:", email)

    db.session.commit()

    print("Keyin bazada:")
    for u in User.query.all():
        print(" ", u.id, u.email, u.role)