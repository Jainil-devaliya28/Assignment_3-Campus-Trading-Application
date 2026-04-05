from flask import Flask, render_template, session, request,flash,redirect, url_for
from flask_bcrypt import Bcrypt
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError
from .models import db, Chat, Notification, Log
from .config import Config
from .routes.auth         import auth_bp, bcrypt as auth_bcrypt
from .routes.main         import main_bp
from .routes.products     import products_bp
from .routes.chat         import chat_bp
from .routes.demands      import demands_bp
from .routes.admin        import admin_bp
from .routes.transactions import transactions_bp
from .routes.notifications import notifs_bp
from .routes.benchmark     import bench_bp
# import flash

bcrypt = Bcrypt()


def log_db_error(error_type: str, description: str, path: str = None, user_id: int = None):
    """Log database-related errors."""
    try:
        full_desc = f"{description} | Path: {path or request.path} | User: {user_id or session.get('member_id', 'anonymous')}"
        entry = Log(member_id=user_id, action_type=error_type, description=full_desc)
        db.session.add(entry)
        db.session.commit()
    except Exception:
        # If even logging fails, just print
        print(f"Database error logging failed: {description}")


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024   # 5 MB max upload

    db.init_app(app)
    with app.app_context():
        db.create_all()
    auth_bcrypt.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(demands_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(notifs_bp)
    app.register_blueprint(bench_bp)

    # ── Context processor: unread messages + unread notifications ──
    @app.context_processor
    def inject_counts():
        msg_count   = 0
        notif_count = 0
        if session.get('member_id'):
            try:
                msg_count = Chat.query.filter_by(
                    receiver_id=session['member_id'], is_read=False
                ).count()
                notif_count = Notification.query.filter_by(
                    member_id=session['member_id'], is_read=False
                ).count()
            except Exception as e:
                log_db_error('DB_QUERY_ERROR', f"Context processor query failed: {str(e)}", request.path, session.get('member_id'))
        return dict(unread_count=msg_count, notif_count=notif_count)

    # ── Database error handlers ──
    @app.errorhandler(SQLAlchemyError)
    def handle_sqlalchemy_error(e):
        db.session.rollback()
        log_db_error('DB_SQLALCHEMY_ERROR', f"SQLAlchemy error: {str(e)}", request.path, session.get('member_id'))
        return render_template('500.html'), 500

    @app.errorhandler(IntegrityError)
    def handle_integrity_error(e):
        db.session.rollback()
        log_db_error('DB_INTEGRITY_ERROR', f"Database integrity error: {str(e)}", request.path, session.get('member_id'))
        flash('Database integrity error occurred. Please try again.', 'danger')
        return redirect(request.referrer or url_for('main.dashboard'))

    @app.errorhandler(OperationalError)
    def handle_operational_error(e):
        db.session.rollback()
        log_db_error('DB_OPERATIONAL_ERROR', f"Database operational error: {str(e)}", request.path, session.get('member_id'))
        return render_template('500.html'), 500

    @app.errorhandler(404)
    def not_found(e):
        return render_template('404.html'), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('403.html'), 403

    @app.errorhandler(500)
    def server_error(e):
        log_db_error('INTERNAL_SERVER_ERROR', f"500 error occurred", request.path, session.get('member_id'))
        return render_template('500.html'), 500

    with app.app_context():
        db.create_all()

    return app
