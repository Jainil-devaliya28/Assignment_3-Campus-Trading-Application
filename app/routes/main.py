from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from ..models import db, Member, Student, TransactionHistory, Product, Feedback, Review, Demand
from ..helpers import login_required, log_action

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    if 'member_id' in session:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))


@main_bp.route('/dashboard')
@login_required
def dashboard():
    member = Member.query.get(session['member_id'])
    recent_products = (Product.query
                       .filter_by(seller_id=member.member_id, is_available=True)
                       .order_by(Product.created_at.desc()).limit(5).all())
    recent_txns = (TransactionHistory.query
                   .filter((TransactionHistory.buyer_id == member.member_id) |
                           (TransactionHistory.seller_id == member.member_id))
                   .order_by(TransactionHistory.created_at.desc()).limit(5).all())
    total_products  = Product.query.filter_by(seller_id=member.member_id).count()
    total_purchases = TransactionHistory.query.filter_by(buyer_id=member.member_id).count()
    total_sales     = TransactionHistory.query.filter_by(seller_id=member.member_id, status='completed').count()
    return render_template('dashboard.html', member=member,
                           recent_products=recent_products, recent_txns=recent_txns,
                           total_products=total_products, total_purchases=total_purchases,
                           total_sales=total_sales)


@main_bp.route('/profile/<int:member_id>')
@login_required
def profile(member_id):
    """
    Portfolio page with access control:
    - Logged-in required (enforced by @login_required)
    - Own profile OR admin  → full view (transactions, email, demands)
    - Other member          → public view only (products + reviews)
    """
    member     = Member.query.get_or_404(member_id)
    viewer_id  = session['member_id']
    is_owner   = (viewer_id == member_id)
    is_admin   = (session.get('role') == 'admin')
    can_see_full = is_owner or is_admin

    # Products — public
    products = (Product.query.filter_by(seller_id=member_id, is_available=True)
                .order_by(Product.created_at.desc()).all())

    # Reviews — public
    reviews    = Review.query.filter_by(reviewed_id=member_id).order_by(Review.created_at.asc()).all()
    avg_rating = (sum(r.rating for r in reviews) / len(reviews)) if reviews else None

    # Transactions — private (owner/admin only)
    txns = []
    if can_see_full:
        txns = (TransactionHistory.query
                .filter((TransactionHistory.buyer_id == member_id) |
                        (TransactionHistory.seller_id == member_id))
                .order_by(TransactionHistory.created_at.desc()).limit(10).all())

    # Demands — private
    demands = []
    if can_see_full:
        demands = (Demand.query.filter_by(member_id=member_id, status='open')
                   .order_by(Demand.created_at.desc()).limit(5).all())

    # Stats
    total_listed  = Product.query.filter_by(seller_id=member_id).count()
    total_sold    = Product.query.filter_by(seller_id=member_id, is_available=False).count()

    return render_template('profile.html', member=member,
                           products=products, txns=txns,
                           reviews=reviews, avg_rating=avg_rating,
                           demands=demands,
                           total_listed=total_listed, total_sold=total_sold,
                           is_owner=is_owner, is_admin=is_admin,
                           can_see_full=can_see_full)


@main_bp.route('/members')
@login_required
def members_directory():
    search  = request.args.get('search', '').strip()
    query   = Member.query
    if search:
        query = query.filter(
            Member.name.ilike(f'%{search}%') | Member.email.ilike(f'%{search}%'))
    members = query.order_by(Member.created_at.desc()).all()
    return render_template('members_directory.html', members=members, search=search)


@main_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    member  = Member.query.get(session['member_id'])
    student = member.student
    if request.method == 'POST':
        member.name  = request.form.get('name', member.name).strip()
        member.phone = request.form.get('phone', member.phone or '').strip()
        if student:
            student.college_name = request.form.get('college_name', '').strip()
            student.department   = request.form.get('department', '').strip()
            yr = request.form.get('year', '')
            student.year         = int(yr) if yr.isdigit() else student.year
            student.roll_number  = request.form.get('roll_number', '').strip()
        db.session.commit()
        log_action('UPDATE', 'User updated profile')
        flash('Profile updated successfully.', 'success')
        return redirect(url_for('main.profile', member_id=member.member_id))
    return render_template('edit_profile.html', member=member)


@main_bp.route('/feedback', methods=['GET', 'POST'])
@login_required
def feedback():
    if request.method == 'POST':
        subject = request.form.get('subject', '').strip()
        message = request.form.get('message', '').strip()
        if not message:
            flash('Message is required.', 'danger')
            return render_template('feedback.html')
        fb = Feedback(member_id=session['member_id'], subject=subject, message=message)
        db.session.add(fb)
        db.session.commit()
        log_action('INSERT', f'User submitted feedback: {subject}')
        flash('Feedback submitted. Thank you!', 'success')
        return redirect(url_for('main.dashboard'))
    return render_template('feedback.html')
