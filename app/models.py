from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Index

db = SQLAlchemy()

# ─────────────────────────────────────────────
# Members
# ─────────────────────────────────────────────
class Member(db.Model):
    __tablename__ = 'Members'
    member_id   = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name        = db.Column(db.String(100), nullable=False)
    email       = db.Column(db.String(150), unique=True, nullable=False)   # UNIQUE index (auto)
    phone       = db.Column(db.String(20))
    created_at  = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    role        = db.Column(db.String(20), default='user', index=True)    # WHERE role=?

    student               = db.relationship('Student',             back_populates='member',      uselist=False)
    auth                  = db.relationship('Authentication',      back_populates='member',      uselist=False)
    products              = db.relationship('Product',             back_populates='seller',      lazy='dynamic')
    sent_messages         = db.relationship('Chat',                foreign_keys='Chat.sender_id',   back_populates='sender',   lazy='dynamic')
    received_messages     = db.relationship('Chat',                foreign_keys='Chat.receiver_id', back_populates='receiver', lazy='dynamic')
    reviews_given         = db.relationship('Review',              foreign_keys='Review.reviewer_id', back_populates='reviewer', lazy='dynamic')
    reviews_received      = db.relationship('Review',              foreign_keys='Review.reviewed_id', back_populates='reviewed', lazy='dynamic')
    transactions_buyer    = db.relationship('TransactionHistory',  foreign_keys='TransactionHistory.buyer_id',  back_populates='buyer',      lazy='dynamic')
    transactions_seller   = db.relationship('TransactionHistory',  foreign_keys='TransactionHistory.seller_id', back_populates='seller_txn', lazy='dynamic')
    bargaining_sent       = db.relationship('BargainingProposal',  foreign_keys='BargainingProposal.buyer_id',  back_populates='buyer',      lazy='dynamic')
    purchase_requests_sent = db.relationship('PurchaseRequest',    back_populates='buyer',        lazy='dynamic')
    demands               = db.relationship('Demand',              back_populates='member',      lazy='dynamic')
    feedbacks             = db.relationship('Feedback',            back_populates='member',      lazy='dynamic')
    logs                  = db.relationship('Log',                 back_populates='member',      lazy='dynamic')
    notifications         = db.relationship('Notification',        back_populates='member',      lazy='dynamic')


# ─────────────────────────────────────────────
# Students
# ─────────────────────────────────────────────
class Student(db.Model):
    __tablename__ = 'Students'
    student_id   = db.Column(db.Integer, primary_key=True, autoincrement=True)
    member_id    = db.Column(db.Integer, db.ForeignKey('Members.member_id', ondelete='CASCADE'), unique=True, nullable=False)
    college_name = db.Column(db.String(200))
    department   = db.Column(db.String(100))
    year         = db.Column(db.Integer)
    roll_number  = db.Column(db.String(50))
    member = db.relationship('Member', back_populates='student')


# ─────────────────────────────────────────────
# Authentication
# ─────────────────────────────────────────────
class Authentication(db.Model):
    __tablename__ = 'Authentication'
    auth_id       = db.Column(db.Integer, primary_key=True, autoincrement=True)
    member_id     = db.Column(db.Integer, db.ForeignKey('Members.member_id', ondelete='CASCADE'), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    last_login    = db.Column(db.DateTime)
    member = db.relationship('Member', back_populates='auth')


# ─────────────────────────────────────────────
# Products  ← most queried table
# ─────────────────────────────────────────────
class Product(db.Model):
    __tablename__ = 'Products'
    product_id   = db.Column(db.Integer, primary_key=True, autoincrement=True)
    seller_id    = db.Column(db.Integer, db.ForeignKey('Members.member_id', ondelete='CASCADE'), nullable=False, index=True)
    title        = db.Column(db.String(200), nullable=False)
    description  = db.Column(db.Text)
    price        = db.Column(db.Numeric(10, 2), nullable=False, index=True)   # price range filter
    category     = db.Column(db.String(100), index=True)                      # category filter
    condition    = db.Column(db.String(50))
    is_available = db.Column(db.Boolean, default=True, index=True)            # marketplace WHERE
    image_url    = db.Column(db.String(500))
    created_at   = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        # Composite: my-listings page (WHERE seller_id=? AND is_available=?)
        Index('ix_products_seller_avail', 'seller_id', 'is_available'),
        # Composite: marketplace browse (WHERE is_available=1 AND category=?)
        Index('ix_products_avail_cat', 'is_available', 'category'),
        # Composite: price range on available products
        Index('ix_products_avail_price', 'is_available', 'price'),
    )

    seller            = db.relationship('Member',             back_populates='products')
    transactions      = db.relationship('TransactionHistory', back_populates='product',          lazy='dynamic', cascade='all, delete-orphan', passive_deletes=True)
    reviews           = db.relationship('Review',             back_populates='product',          lazy='dynamic', cascade='all, delete-orphan', passive_deletes=True)
    proposals         = db.relationship('BargainingProposal', back_populates='product',          lazy='dynamic', cascade='all, delete-orphan', passive_deletes=True)
    purchase_requests = db.relationship('PurchaseRequest',    back_populates='product',          lazy='dynamic', cascade='all, delete-orphan', passive_deletes=True)


# ─────────────────────────────────────────────
# TransactionHistory
# ─────────────────────────────────────────────
class TransactionHistory(db.Model):
    __tablename__ = 'TransactionHistory'
    txn_id     = db.Column(db.Integer, primary_key=True, autoincrement=True)
    product_id = db.Column(db.Integer, db.ForeignKey('Products.product_id', ondelete='SET NULL'), nullable=True, index=True)
    buyer_id   = db.Column(db.Integer, db.ForeignKey('Members.member_id', ondelete='CASCADE'), nullable=False, index=True)
    seller_id  = db.Column(db.Integer, db.ForeignKey('Members.member_id', ondelete='CASCADE'), nullable=False, index=True)
    amount     = db.Column(db.Numeric(10, 2), nullable=False)
    status     = db.Column(db.String(50), default='pending', index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        # Composite: buyer purchase history with status filter
        Index('ix_txn_buyer_status',  'buyer_id',  'status'),
        # Composite: seller sales with status filter
        Index('ix_txn_seller_status', 'seller_id', 'status'),
    )

    product    = db.relationship('Product', back_populates='transactions')
    buyer      = db.relationship('Member',  foreign_keys=[buyer_id],  back_populates='transactions_buyer')
    seller_txn = db.relationship('Member',  foreign_keys=[seller_id], back_populates='transactions_seller')


# ─────────────────────────────────────────────
# Reviews
# ─────────────────────────────────────────────
class Review(db.Model):
    __tablename__ = 'Reviews'
    review_id   = db.Column(db.Integer, primary_key=True, autoincrement=True)
    product_id  = db.Column(db.Integer, db.ForeignKey('Products.product_id', ondelete='CASCADE'), nullable=False, index=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('Members.member_id',   ondelete='CASCADE'), nullable=False, index=True)
    reviewed_id = db.Column(db.Integer, db.ForeignKey('Members.member_id',   ondelete='CASCADE'), nullable=False, index=True)
    rating      = db.Column(db.Integer, nullable=False)
    comment     = db.Column(db.Text)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        # Composite: duplicate review check (WHERE product_id=? AND reviewer_id=?)
        Index('ix_reviews_product_reviewer', 'product_id', 'reviewer_id'),
    )

    product  = db.relationship('Product', back_populates='reviews')
    reviewer = db.relationship('Member',  foreign_keys=[reviewer_id], back_populates='reviews_given')
    reviewed = db.relationship('Member',  foreign_keys=[reviewed_id], back_populates='reviews_received')


# ─────────────────────────────────────────────
# Bargaining Proposals
# ─────────────────────────────────────────────
class BargainingProposal(db.Model):
    __tablename__ = 'Bargaining_Proposals'
    proposal_id    = db.Column(db.Integer, primary_key=True, autoincrement=True)
    product_id     = db.Column(db.Integer, db.ForeignKey('Products.product_id', ondelete='CASCADE'), nullable=False, index=True)
    buyer_id       = db.Column(db.Integer, db.ForeignKey('Members.member_id',   ondelete='CASCADE'), nullable=False, index=True)
    proposed_price = db.Column(db.Numeric(10, 2), nullable=False)
    message        = db.Column(db.Text)
    status         = db.Column(db.String(50), default='pending', index=True)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        # Composite: look up buyer's proposal on a specific product
        Index('ix_proposals_product_buyer', 'product_id', 'buyer_id'),
    )

    product = db.relationship('Product', back_populates='proposals')
    buyer   = db.relationship('Member',  back_populates='bargaining_sent')


# ─────────────────────────────────────────────
# Demands
# ─────────────────────────────────────────────
class Demand(db.Model):
    __tablename__ = 'Demands'
    demand_id   = db.Column(db.Integer, primary_key=True, autoincrement=True)
    member_id   = db.Column(db.Integer, db.ForeignKey('Members.member_id', ondelete='CASCADE'), nullable=False, index=True)
    title       = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category    = db.Column(db.String(100), index=True)
    budget      = db.Column(db.Numeric(10, 2))
    status      = db.Column(db.String(50), default='open', index=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        # Composite: open demands by category
        Index('ix_demands_status_cat', 'status', 'category'),
    )

    member = db.relationship('Member', back_populates='demands')


# ─────────────────────────────────────────────
# Chat  ← high frequency
# ─────────────────────────────────────────────
class Chat(db.Model):
    __tablename__ = 'Chat'
    chat_id     = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sender_id   = db.Column(db.Integer, db.ForeignKey('Members.member_id', ondelete='CASCADE'), nullable=False, index=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey('Members.member_id', ondelete='CASCADE'), nullable=False, index=True)
    message     = db.Column(db.Text, nullable=False)
    is_read     = db.Column(db.Boolean, default=False, index=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        # Composite: fetch conversation between two users
        Index('ix_chat_sender_receiver', 'sender_id', 'receiver_id'),
        # Composite: unread count per receiver — runs on every page load
        Index('ix_chat_receiver_read',   'receiver_id', 'is_read'),
    )

    sender   = db.relationship('Member', foreign_keys=[sender_id],   back_populates='sent_messages')
    receiver = db.relationship('Member', foreign_keys=[receiver_id], back_populates='received_messages')


# ─────────────────────────────────────────────
# Logs
# ─────────────────────────────────────────────
class Log(db.Model):
    __tablename__ = 'Logs'
    log_id      = db.Column(db.Integer, primary_key=True, autoincrement=True)
    member_id   = db.Column(db.Integer, db.ForeignKey('Members.member_id', ondelete='SET NULL'), nullable=True, index=True)
    action_type = db.Column(db.String(50), nullable=False, index=True)
    description = db.Column(db.Text)
    timestamp   = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index('ix_logs_member_action', 'member_id', 'action_type'),
    )

    member = db.relationship('Member', back_populates='logs')


# ─────────────────────────────────────────────
# Feedbacks
# ─────────────────────────────────────────────
class Feedback(db.Model):
    __tablename__ = 'Feedbacks'
    feedback_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    member_id   = db.Column(db.Integer, db.ForeignKey('Members.member_id', ondelete='CASCADE'), nullable=False, index=True)
    subject     = db.Column(db.String(200))
    message     = db.Column(db.Text, nullable=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    member = db.relationship('Member', back_populates='feedbacks')


# ─────────────────────────────────────────────
# Notifications
# ─────────────────────────────────────────────
class Notification(db.Model):
    __tablename__ = 'Notifications'
    notif_id   = db.Column(db.Integer, primary_key=True, autoincrement=True)
    member_id  = db.Column(db.Integer, db.ForeignKey('Members.member_id', ondelete='CASCADE'), nullable=False, index=True)
    title      = db.Column(db.String(200), nullable=False)
    message    = db.Column(db.Text, nullable=False)
    link       = db.Column(db.String(500))
    is_read    = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        # Composite: unread notification count — runs on every page load
        Index('ix_notifs_member_read', 'member_id', 'is_read'),
    )

    member = db.relationship('Member', back_populates='notifications')


# ─────────────────────────────────────────────
# Purchase Requests
# ─────────────────────────────────────────────
class PurchaseRequest(db.Model):
    __tablename__ = 'PurchaseRequests'
    request_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    product_id = db.Column(db.Integer, db.ForeignKey('Products.product_id', ondelete='CASCADE'), nullable=False, index=True)
    buyer_id   = db.Column(db.Integer, db.ForeignKey('Members.member_id',   ondelete='CASCADE'), nullable=False, index=True)
    message    = db.Column(db.Text)
    status     = db.Column(db.String(20), default='pending', index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    product = db.relationship('Product', back_populates='purchase_requests')
    buyer   = db.relationship('Member',  back_populates='purchase_requests_sent')
