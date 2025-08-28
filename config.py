# filepath: flask-app/config.py
import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'clave-secreta'
    SQLALCHEMY_DATABASE_URI = (
        'mysql+mysqlconnector://admin:12345678@database-1.cf0ey64ia6yt.us-east-2.rds.amazonaws.com:3306/andamiosdb'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False