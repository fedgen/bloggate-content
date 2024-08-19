from functools import wraps
import os
import jwt

from flask import Blueprint, Flask, request
from flask_pymongo import PyMongo
from datetime import datetime
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_prometheus import monitor


routes = Blueprint('routes', __name__)

app = Flask(__name__, template_folder='../templates')
CORS(app, supports_credentials=True, resources={
    r"/*": {
        "origins": [
            "https://fedgen.net", 
            "http://localhost:3000", 
            "https://phis.fedgen.net", 
            "http://192.168.8.201:3000", 
            "https://33q79649-3006.uks1.devtunnels.ms"
            ]}})

app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY")
app.config["JWT_TOKEN_LOCATION"] = ["headers"]
app.config["JWT_HEADER_TYPE"] = []
app.config['APPLICATION_ROOT'] = '/config'
jwts = JWTManager(app)
app.config["MONGO_URI"] = "mongodb://localhost:27017/contentDB"
mongo = PyMongo(app)
monitor(app, port=8000)
db = mongo.db

content_col = db.content
drafts_col = db.drafts
preferences_col = db.user_preferences
old_posts_col = db.old_posts
auth_user_col = db.auth_user

content_col.create_index(
    [
        ('body', 'text'),
        ('title', 'text')
    ],
    name="search_index",
    weights={
        'title': 100,
        'body': 25
    }
)

content_col.create_index("slug", name="slug_index", unique=True)

preferences_col.create_index("user_id", name="pref_index", unique=True)
auth_user_col.create_index("auth_user_id", name="auth_user_index", unique=True)
per_page = 10

def admin_required():
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            token = request.headers.get('Authorization')
            if not token:
                return jsonify({"ok": False, "message": "Unathorized"}), 403
            else:
                try:
                    payload = jwt.decode(token, secret, algorithms=['HS256'])
                    
                    if payload['role'] == "S":
                        return fn(*args, **kwargs)
                    else:
                        return jsonify({"ok": False, "message": "Not admin"}), 403
                except jwt.ExpiredSignatureError:
                    return jsonify({"ok": False, "message": "Expired token"}), 403
                
        return decorator
    return wrapper

def author_required():
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            token = request.headers.get('Authorization')
            if not token:
                return jsonify({"ok": False, "message": "Unathorized"}), 403
            else:
                try:
                    payload = jwt.decode(token, secret, algorithms=['HS256'])
                    
                    if payload['role'] != "P":
                        return fn(*args, **kwargs)
                    else:
                        return jsonify({"ok": False, "message": "Not author"}), 403
                except jwt.ExpiredSignatureError:
                    return jsonify({"ok": False, "message": "Expired token"}), 403
                
        return decorator
    return wrapper

def reviewer_required():
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            token = request.headers.get('Authorization')
            if not token:
                return jsonify({"ok": False, "message": "Unathorized"}), 403
            else:
                try:
                    payload = jwt.decode(token, secret, algorithms=['HS256'])
                    role = payload['role']
                    if role == "R" or role == "S":
                        return fn(*args, **kwargs)
                    else:
                        return jsonify({"ok": False, "message": "Not reviewer"}), 403
                except jwt.ExpiredSignatureError:
                    return jsonify({"ok": False, "message": "Expired token"}), 403
                
        return decorator
    return wrapper

def login_required():
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            token = request.headers.get('Authorization')
            if not token:
                return jsonify({"ok": False, "message": "Unathorized"}), 403
            else:
                try:
                    payload = jwt.decode(token, secret, algorithms=['HS256'])
                    if payload is not  None:
                        request.payload = payload
                        return fn(*args, **kwargs)
                    else:
                        return jsonify({"ok": False, "message": "Not reviewer"}), 403
                except jwt.ExpiredSignatureError:
                    return jsonify({"ok": False, "message": "Expired token"}), 403
                
        return decorator
    return wrapper

def public_route():
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            token = request.headers.get('Authorization')
            if not token:
                payload = None
                request.payload = payload
                return fn(*args, **kwargs)
            else:
                try:
                    payload = jwt.decode(token, secret, algorithms=['HS256'])
                    if payload is not  None:
                        request.payload = payload
                        return fn(*args, **kwargs)
                    else:
                        return jsonify({"ok": False, "message": "Not user"}), 403
                except jwt.ExpiredSignatureError:
                    return jsonify({"ok": False, "message": "Expired token"}), 403
                
        return decorator
    return wrapper





now = datetime.now()

from routes.content.main import *
from routes.drafts.main import *
from routes.user_preferences.main import *
from .general_methods import *
