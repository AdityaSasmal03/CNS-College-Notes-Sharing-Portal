from flask import Flask, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required
from flask_bcrypt import Bcrypt

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = (
        'mssql+pyodbc://LAPTOP-A-LEN-S5/CNS'
        '?driver=ODBC+Driver+17+for+SQL+Server'
        '&trusted_connection=yes'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.secret_key = 'CNS'

    db.init_app(app)
        
    from models import Student, Teacher
    from routes import register_routes

    register_routes(app, db)
    return app

# ADD THIS PART
if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
