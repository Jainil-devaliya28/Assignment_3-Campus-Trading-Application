from flask import Blueprint, render_template, request, session
from ..models import TransactionHistory
from ..helpers import login_required

transactions_bp = Blueprint('transactions', __name__)


@transactions_bp.route('/transactions')
@login_required
def my_transactions():
    me   = session['member_id']
    role = request.args.get('role', '')   # 'buyer' | 'seller' | ''

    query = TransactionHistory.query.filter(
        (TransactionHistory.buyer_id == me) |
        (TransactionHistory.seller_id == me)
    )
    if role == 'buyer':
        query = TransactionHistory.query.filter_by(buyer_id=me)
    elif role == 'seller':
        query = TransactionHistory.query.filter_by(seller_id=me)

    txns = query.order_by(TransactionHistory.created_at.desc()).all()

    total_spent = sum(
        float(t.amount) for t in txns if t.buyer_id == me and t.status == 'completed'
    )
    total_earned = sum(
        float(t.amount) for t in txns if t.seller_id == me and t.status == 'completed'
    )

    return render_template('transactions.html',
                           txns=txns,
                           role_filter=role,
                           total_spent=total_spent,
                           total_earned=total_earned)
