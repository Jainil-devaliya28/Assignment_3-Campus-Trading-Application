from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_bcrypt import Bcrypt
from ..models import db, Member, Student, Authentication
from ..helpers import log_action, log_security_event
from datetime import datetime

auth_bp = Blueprint('auth', __name__)
bcrypt = Bcrypt()


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name        = request.form.get('name', '').strip()
        email       = request.form.get('email', '').strip().lower()
        phone       = request.form.get('phone', '').strip()
        password    = request.form.get('password', '')
        confirm     = request.form.get('confirm_password', '')
        college     = request.form.get('college_name', '').strip()
        department  = request.form.get('department', '').strip()
        year        = request.form.get('year', '').strip()
        roll        = request.form.get('roll_number', '').strip()

        # ── Validations ──
        if not name or not email or not password:
            flash('Name, email and password are required.', 'danger')
            return render_template('register.html')

        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html')

        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return render_template('register.html')

        if Member.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return render_template('register.html')

        # ── Create member ──
        member = Member(name=name, email=email, phone=phone, role='user')
        db.session.add(member)
        db.session.flush()   # get member_id before commit

        # ── Create student record ──
        student = Student(
            member_id    = member.member_id,
            college_name = college,
            department   = department,
            year         = int(year) if year.isdigit() else None,
            roll_number  = roll
        )
        db.session.add(student)

        # ── Create auth record ──
        pw_hash = bcrypt.generate_password_hash(password).decode('utf-8')
        auth = Authentication(member_id=member.member_id, password_hash=pw_hash)
        db.session.add(auth)

        db.session.commit()
        log_action('INSERT', f'New user registered: {email}', member.member_id)

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not email or not password:
            flash('Email and password are required.', 'danger')
            return render_template('login.html')

        member = Member.query.filter_by(email=email).first()
        if not member or not member.auth:
            log_security_event(
                'FAILED_LOGIN',
                f"Failed login attempt for non-existent email: {email}",
                request.remote_addr,
                request.headers.get('User-Agent', 'unknown')
            )
            flash('Invalid email or password.', 'danger')
            return render_template('login.html')

        if not bcrypt.check_password_hash(member.auth.password_hash, password):
            log_security_event(
                'FAILED_LOGIN',
                f"Failed login attempt for user: {email}",
                request.remote_addr,
                request.headers.get('User-Agent', 'unknown')
            )
            flash('Invalid email or password.', 'danger')
            return render_template('login.html')

        # ── Update last login ──
        member.auth.last_login = datetime.utcnow()
        db.session.commit()

        # ── Set session ──
        session['member_id'] = member.member_id
        session['name']      = member.name
        session['role']      = member.role

        log_action('LOGIN', f'User logged in: {email}', member.member_id)
        flash(f'Welcome back, {member.name}!', 'success')
        return redirect(url_for('main.dashboard'))

    return render_template('login.html')


@auth_bp.route('/change-password', methods=['GET', 'POST'])
def change_password():
    from ..helpers import login_required as _lr
    from flask import session as _sess
    if 'member_id' not in _sess:
        flash('Please log in first.', 'warning')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        current  = request.form.get('current_password', '')
        new_pw   = request.form.get('new_password', '')
        confirm  = request.form.get('confirm_password', '')

        member = Member.query.get(_sess['member_id'])
        if not member or not member.auth:
            flash('Account not found.', 'danger')
            return render_template('change_password.html')

        if not bcrypt.check_password_hash(member.auth.password_hash, current):
            flash('Current password is incorrect.', 'danger')
            return render_template('change_password.html')

        if len(new_pw) < 6:
            flash('New password must be at least 6 characters.', 'danger')
            return render_template('change_password.html')

        if new_pw != confirm:
            flash('New passwords do not match.', 'danger')
            return render_template('change_password.html')

        member.auth.password_hash = bcrypt.generate_password_hash(new_pw).decode('utf-8')
        db.session.commit()
        log_action('UPDATE', 'User changed password', member.member_id)
        flash('Password changed successfully!', 'success')
        return redirect(url_for('main.profile', member_id=member.member_id))

    return render_template('change_password.html')


@auth_bp.route('/logout')
def logout():
    member_id = session.get('member_id')
    log_action('LOGOUT', 'User logged out', member_id)
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))
