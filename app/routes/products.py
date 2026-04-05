import os
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from werkzeug.utils import secure_filename
from ..models import db, Product, TransactionHistory, Review, BargainingProposal, Member, PurchaseRequest
from ..helpers import login_required, admin_required, log_action, notify

products_bp = Blueprint('products', __name__)

CATEGORIES = ['Books', 'Electronics', 'Clothing', 'Stationery', 'Sports', 'Other']
CONDITIONS  = ['New', 'Good', 'Fair']
ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT


def save_uploaded_image(file):
    """Save uploaded image to static/uploads, return relative URL or None."""
    if not file or file.filename == '':
        return None
    if not allowed_file(file.filename):
        return None
    ext      = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    file.save(os.path.join(upload_dir, filename))
    return url_for('static', filename=f'uploads/{filename}')


# ─────────────────────────────────────────────
# Marketplace
# ─────────────────────────────────────────────
@products_bp.route('/marketplace')
@login_required
def marketplace():
    query    = Product.query.filter_by(is_available=True)
    category = request.args.get('category', '')
    min_p    = request.args.get('min_price', '')
    max_p    = request.args.get('max_price', '')
    search   = request.args.get('search', '').strip()

    if category:
        query = query.filter_by(category=category)
    if min_p:
        try:
            query = query.filter(Product.price >= float(min_p))
        except ValueError:
            pass
    if max_p:
        try:
            query = query.filter(Product.price <= float(max_p))
        except ValueError:
            pass
    if search:
        query = query.filter(Product.title.ilike(f'%{search}%'))

    products = query.order_by(Product.created_at.desc()).all()
    return render_template('marketplace.html',
                           products=products,
                           categories=CATEGORIES,
                           selected_category=category,
                           min_price=min_p,
                           max_price=max_p,
                           search=search)


# ─────────────────────────────────────────────
# My Listings
# ─────────────────────────────────────────────
@products_bp.route('/my-listings')
@login_required
def my_listings():
    status   = request.args.get('status', '')
    query    = Product.query.filter_by(seller_id=session['member_id'])
    if status == 'available':
        query = query.filter_by(is_available=True)
    elif status == 'sold':
        query = query.filter_by(is_available=False)
    products  = query.order_by(Product.created_at.desc()).all()
    total_val = sum(float(p.price) for p in products if not p.is_available)
    return render_template('my_listings.html',
                           products=products,
                           status_filter=status,
                           total_earned=total_val)


# ─────────────────────────────────────────────
# Add Product
# ─────────────────────────────────────────────
@products_bp.route('/product/add', methods=['GET', 'POST'])
@login_required
def add_product():
    if request.method == 'POST':
        title       = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        price       = request.form.get('price', '')
        category    = request.form.get('category', '')
        condition   = request.form.get('condition', '')

        if not title or not price:
            flash('Title and price are required.', 'danger')
            return render_template('add_product.html', categories=CATEGORIES, conditions=CONDITIONS)

        try:
            price = float(price)
            if price < 0:
                raise ValueError
        except ValueError:
            flash('Enter a valid price.', 'danger')
            return render_template('add_product.html', categories=CATEGORIES, conditions=CONDITIONS)

        # Handle image upload
        image_url = None
        file = request.files.get('image_file')
        if file and file.filename:
            image_url = save_uploaded_image(file)
            if image_url is None:
                flash('Invalid image file. Allowed types: PNG, JPG, GIF, WEBP.', 'warning')

        product = Product(
            seller_id   = session['member_id'],
            title       = title,
            description = description,
            price       = price,
            category    = category,
            condition   = condition,
            image_url   = image_url
        )
        db.session.add(product)
        db.session.commit()
        log_action('INSERT', f'Product added: {title}')
        flash('Product listed successfully!', 'success')
        # Redirect to product detail — URL contains new product_id so test
        # helpers can extract it reliably from resp.url without HTML scraping.
        return redirect(url_for('products.product_detail', product_id=product.product_id))

    return render_template('add_product.html', categories=CATEGORIES, conditions=CONDITIONS)


# ─────────────────────────────────────────────
# Product Detail
# ─────────────────────────────────────────────
@products_bp.route('/product/<int:product_id>')
@login_required
def product_detail(product_id):
    product   = Product.query.get_or_404(product_id)
    reviews   = Review.query.filter_by(product_id=product_id).order_by(Review.created_at.asc()).all()
    avg_r     = (sum(r.rating for r in reviews) / len(reviews)) if reviews else None
    proposals = []

    if session['member_id'] == product.seller_id or session.get('role') == 'admin':
        proposals = BargainingProposal.query.filter_by(product_id=product_id).order_by(BargainingProposal.created_at.asc()).all()

    already_reviewed = Review.query.filter_by(
        product_id=product_id, reviewer_id=session['member_id']
    ).first()

    # My own proposal on this product (for buyer to see status)
    is_owner    = (session['member_id'] == product.seller_id)
    my_proposal = None
    my_purchase_request = None

    if not is_owner:
        my_proposal = BargainingProposal.query.filter_by(
            product_id=product_id, buyer_id=session['member_id']
        ).order_by(BargainingProposal.created_at.desc()).first()

        my_purchase_request = PurchaseRequest.query.filter_by(
            product_id=product_id, buyer_id=session['member_id']
        ).order_by(PurchaseRequest.created_at.desc()).first()

    # Seller sees all pending purchase requests
    purchase_requests = []
    if is_owner or session.get('role') == 'admin':
        purchase_requests = PurchaseRequest.query.filter_by(
            product_id=product_id
        ).order_by(PurchaseRequest.created_at.desc()).all()

    return render_template('product_detail.html',
                           product=product,
                           reviews=reviews,
                           avg_rating=avg_r,
                           proposals=proposals,
                           already_reviewed=already_reviewed,
                           my_proposal=my_proposal,
                           is_owner=is_owner,
                           my_purchase_request=my_purchase_request,
                           purchase_requests=purchase_requests)


# ─────────────────────────────────────────────
# Edit Product
# ─────────────────────────────────────────────
@products_bp.route('/product/<int:product_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)

    if product.seller_id != session['member_id']:
        flash('You can only edit your own products.', 'danger')
        return redirect(url_for('products.marketplace'))

    if request.method == 'POST':
        product.title       = request.form.get('title', product.title).strip()
        product.description = request.form.get('description', '').strip()
        price               = request.form.get('price', '')
        try:
            product.price = float(price)
        except ValueError:
            flash('Invalid price.', 'danger')
            return render_template('add_product.html', product=product,
                                   categories=CATEGORIES, conditions=CONDITIONS, edit=True)

        product.category  = request.form.get('category', product.category)
        product.condition = request.form.get('condition', product.condition)

        # New image upload (only replace if a new file is provided)
        file = request.files.get('image_file')
        if file and file.filename:
            new_url = save_uploaded_image(file)
            if new_url:
                product.image_url = new_url
            else:
                flash('Invalid image file. Keeping existing image.', 'warning')

        db.session.commit()
        log_action('UPDATE', f'Product updated: {product.title}')
        flash('Product updated.', 'success')
        return redirect(url_for('products.product_detail', product_id=product_id))

    return render_template('add_product.html',
                           product=product,
                           categories=CATEGORIES,
                           conditions=CONDITIONS,
                           edit=True)


# ─────────────────────────────────────────────
# Delete Product
# ─────────────────────────────────────────────
@products_bp.route('/product/<int:product_id>/delete', methods=['POST'])
@login_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)

    if product.seller_id != session['member_id'] and session.get('role') != 'admin':
        flash('Permission denied.', 'danger')
        return redirect(url_for('products.marketplace'))

    title = product.title
    db.session.delete(product)
    db.session.commit()
    log_action('DELETE', f'Product deleted: {title}')
    flash('Product deleted.', 'success')
    return redirect(url_for('products.marketplace'))


# ─────────────────────────────────────────────
# Request to Buy (replaces instant Buy Now)
# ─────────────────────────────────────────────
@products_bp.route('/product/<int:product_id>/request-buy', methods=['POST'])
@login_required
def request_buy(product_id):
    """Buyer sends a purchase request — seller must approve before product is delisted."""
    product = Product.query.get_or_404(product_id)

    if not product.is_available:
        flash('This product is no longer available.', 'warning')
        return redirect(url_for('products.product_detail', product_id=product_id))

    if product.seller_id == session['member_id']:
        flash("You can't buy your own product.", 'warning')
        return redirect(url_for('products.product_detail', product_id=product_id))

    # Check for existing pending request from this buyer
    existing = PurchaseRequest.query.filter_by(
        product_id=product_id,
        buyer_id=session['member_id'],
        status='pending'
    ).first()
    if existing:
        flash('You already have a pending purchase request for this product.', 'warning')
        return redirect(url_for('products.product_detail', product_id=product_id))

    message = request.form.get('buy_message', '').strip()

    purchase_req = PurchaseRequest(
        product_id = product_id,
        buyer_id   = session['member_id'],
        message    = message,
        status     = 'pending'
    )
    db.session.add(purchase_req)
    db.session.commit()

    # Notify seller
    buyer = Member.query.get(session['member_id'])
    notify(
        member_id = product.seller_id,
        title     = '🛒 New purchase request!',
        message   = f'{buyer.name} wants to buy "{product.title}" for ₹{product.price}. Approve or reject on the product page.',
        link      = url_for('products.product_detail', product_id=product_id)
    )

    log_action('INSERT', f'Purchase request sent for: {product.title}')
    flash('Purchase request sent! The seller will be notified and must approve it.', 'success')
    return redirect(url_for('products.product_detail', product_id=product_id))


# ─────────────────────────────────────────────
# Seller: Approve or Reject Purchase Request
# ─────────────────────────────────────────────
@products_bp.route('/purchase-request/<int:req_id>/respond', methods=['POST'])
@login_required
def respond_purchase_request(req_id):
    """Seller approves or rejects a buyer's purchase request.
    Uses SELECT FOR UPDATE on both rows to eliminate the TOCTOU window
    that would allow double-approval under concurrent workers.
    """
    # Lock both rows — prevents concurrent approval of the same request
    purchase_req = db.session.query(PurchaseRequest).with_for_update().get(req_id)
    if purchase_req is None:
        from flask import abort; abort(404)

    product = db.session.query(Product).with_for_update().get(purchase_req.product_id)
    if product is None:
        db.session.rollback(); from flask import abort; abort(404)

    # Only the seller can respond
    if product.seller_id != session['member_id']:
        db.session.rollback()
        flash('Permission denied.', 'danger')
        return redirect(url_for('products.marketplace'))

    action = request.form.get('action')  # 'approved' or 'rejected'

    if action not in ('approved', 'rejected'):
        db.session.rollback()
        flash('Invalid action.', 'danger')
        return redirect(url_for('products.product_detail', product_id=product.product_id))

    # Guard: must still be pending (prevents re-processing an already-handled request)
    if purchase_req.status != 'pending':
        db.session.rollback()
        flash('This purchase request has already been processed.', 'warning')
        return redirect(url_for('products.product_detail', product_id=product.product_id))

    buyer  = purchase_req.buyer
    seller = Member.query.get(session['member_id'])

    if action == 'approved':
        # Atomic availability check under lock — product must still be available
        if not product.is_available:
            purchase_req.status = 'rejected'
            db.session.commit()
            flash('Product is no longer available — another request was approved first.', 'warning')
            return redirect(url_for('products.product_detail', product_id=product.product_id))

        # Single atomic commit: approve + delist + create txn + reject others
        purchase_req.status  = action
        product.is_available = False

        txn = TransactionHistory(
            product_id = product.product_id,
            buyer_id   = purchase_req.buyer_id,
            seller_id  = product.seller_id,
            amount     = product.price,
            status     = 'completed'
        )
        PurchaseRequest.query.filter(
            PurchaseRequest.product_id == product.product_id,
            PurchaseRequest.request_id != req_id,
            PurchaseRequest.status == 'pending'
        ).update({'status': 'rejected'})

        db.session.add(txn)
        db.session.commit()

        # Notify buyer (separate commit, outside the lock)
        notify(
            member_id = purchase_req.buyer_id,
            title     = '✅ Purchase approved!',
            message   = f'{seller.name} approved your purchase of "{product.title}" for ₹{product.price}. The product is now yours!',
            link      = url_for('transactions.my_transactions')
        )

        log_action('UPDATE', f'Purchase request approved: {product.title} → {buyer.name}')
        flash(f'Purchase approved! "{product.title}" is now sold to {buyer.name}.', 'success')

    else:  # rejected
        purchase_req.status = action
        db.session.commit()

        notify(
            member_id = purchase_req.buyer_id,
            title     = '❌ Purchase request declined',
            message   = f'{seller.name} declined your purchase request for "{product.title}".',
            link      = url_for('products.product_detail', product_id=product.product_id)
        )

        log_action('UPDATE', f'Purchase request rejected: {product.title} for {buyer.name}')
        flash(f'Purchase request from {buyer.name} rejected.', 'info')

    return redirect(url_for('products.product_detail', product_id=product.product_id))


# ─────────────────────────────────────────────
# Buyer: Cancel their own pending request
# ─────────────────────────────────────────────
@products_bp.route('/purchase-request/<int:req_id>/cancel', methods=['POST'])
@login_required
def cancel_purchase_request(req_id):
    purchase_req = PurchaseRequest.query.get_or_404(req_id)

    if purchase_req.buyer_id != session['member_id']:
        flash('Permission denied.', 'danger')
        return redirect(url_for('products.marketplace'))

    product_id = purchase_req.product_id
    db.session.delete(purchase_req)
    db.session.commit()
    log_action('DELETE', f'Purchase request cancelled for product {product_id}')
    flash('Purchase request cancelled.', 'info')
    return redirect(url_for('products.product_detail', product_id=product_id))


# ─────────────────────────────────────────────
# Toggle Availability
# ─────────────────────────────────────────────
@products_bp.route('/product/<int:product_id>/toggle-availability', methods=['POST'])
@login_required
def toggle_availability(product_id):
    product = Product.query.get_or_404(product_id)

    if product.seller_id != session['member_id']:
        flash('Permission denied.', 'danger')
        return redirect(url_for('products.my_listings'))

    product.is_available = not product.is_available
    db.session.commit()
    action = 'relisted' if product.is_available else 'marked as sold'
    log_action('UPDATE', f'Product {action}: {product.title}')
    flash(f'Product {action}.', 'success')
    return redirect(url_for('products.my_listings'))


# ─────────────────────────────────────────────
# Add Review
# ─────────────────────────────────────────────
@products_bp.route('/product/<int:product_id>/review', methods=['POST'])
@login_required
def add_review(product_id):
    product = Product.query.get_or_404(product_id)

    if product.seller_id == session['member_id']:
        flash("You can't review your own product.", 'warning')
        return redirect(url_for('products.product_detail', product_id=product_id))

    rating  = request.form.get('rating', '')
    comment = request.form.get('comment', '').strip()

    # Validate rating FIRST — ensures bad input always produces a 'danger' flash
    # regardless of whether this user has already reviewed the product.
    try:
        rating = int(rating)
        if rating < 1 or rating > 5:
            raise ValueError
    except ValueError:
        flash('Rating must be between 1 and 5.', 'danger')
        return redirect(url_for('products.product_detail', product_id=product_id))

    existing = Review.query.filter_by(
        product_id=product_id, reviewer_id=session['member_id']
    ).first()
    if existing:
        flash('You have already reviewed this product.', 'warning')
        return redirect(url_for('products.product_detail', product_id=product_id))

    review = Review(
        product_id  = product_id,
        reviewer_id = session['member_id'],
        reviewed_id = product.seller_id,
        rating      = rating,
        comment     = comment
    )
    db.session.add(review)
    db.session.commit()

    # Notify seller about new review
    reviewer = Member.query.get(session['member_id'])
    notify(
        member_id = product.seller_id,
        title     = 'New review on your product',
        message   = f'{reviewer.name} left a {rating}★ review on "{product.title}".',
        link      = url_for('products.product_detail', product_id=product_id)
    )

    log_action('INSERT', f'Review added for product: {product.title}')
    flash('Review submitted!', 'success')
    return redirect(url_for('products.product_detail', product_id=product_id))


# ─────────────────────────────────────────────
# Send Bargaining Proposal
# ─────────────────────────────────────────────
@products_bp.route('/product/<int:product_id>/bargain', methods=['POST'])
@login_required
def send_proposal(product_id):
    product = Product.query.get_or_404(product_id)

    if product.seller_id == session['member_id']:
        flash("You can't bargain on your own product.", 'warning')
        return redirect(url_for('products.product_detail', product_id=product_id))

    proposed_price = request.form.get('proposed_price', '')
    message        = request.form.get('message', '').strip()

    try:
        proposed_price = float(proposed_price)
        if proposed_price <= 0:
            raise ValueError
    except ValueError:
        flash('Enter a valid proposed price.', 'danger')
        return redirect(url_for('products.product_detail', product_id=product_id))

    proposal = BargainingProposal(
        product_id     = product_id,
        buyer_id       = session['member_id'],
        proposed_price = proposed_price,
        message        = message
    )
    db.session.add(proposal)
    db.session.commit()

    # Notify seller about new bargain offer
    buyer = Member.query.get(session['member_id'])
    notify(
        member_id = product.seller_id,
        title     = 'New bargain offer received',
        message   = f'{buyer.name} offered ₹{proposed_price} for "{product.title}".',
        link      = url_for('products.product_detail', product_id=product_id)
    )

    log_action('INSERT', f'Bargaining proposal sent for: {product.title}')
    flash('Bargaining proposal sent!', 'success')
    return redirect(url_for('products.product_detail', product_id=product_id))


# ─────────────────────────────────────────────
# Respond to Proposal  ← BUYER GETS NOTIFIED HERE
# ─────────────────────────────────────────────
@products_bp.route('/proposal/<int:proposal_id>/respond', methods=['POST'])
@login_required
def respond_proposal(proposal_id):
    proposal = BargainingProposal.query.get_or_404(proposal_id)
    product  = proposal.product

    if product.seller_id != session['member_id']:
        flash('Permission denied.', 'danger')
        return redirect(url_for('products.marketplace'))

    action = request.form.get('action')
    if action in ('accepted', 'rejected'):
        proposal.status = action
        db.session.commit()
        log_action('UPDATE', f'Proposal {action} for product: {product.title}')

        # ── Notify the buyer ──────────────────────────────────
        seller = Member.query.get(session['member_id'])
        if action == 'accepted':
            notify(
                member_id = proposal.buyer_id,
                title     = '🎉 Your bargain offer was accepted!',
                message   = (f'{seller.name} accepted your offer of ₹{proposal.proposed_price} '
                             f'for "{product.title}". Go buy it now!'),
                link      = url_for('products.product_detail', product_id=product.product_id)
            )
        else:
            notify(
                member_id = proposal.buyer_id,
                title     = 'Your bargain offer was declined',
                message   = (f'{seller.name} declined your offer of ₹{proposal.proposed_price} '
                             f'for "{product.title}".'),
                link      = url_for('products.product_detail', product_id=product.product_id)
            )

        flash(f'Proposal {action}. Buyer has been notified.', 'success')

    return redirect(url_for('products.product_detail', product_id=product.product_id))