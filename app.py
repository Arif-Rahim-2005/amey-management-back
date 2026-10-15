import os
import cloudinary
from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_restful import Api
# from flask_sqlalchemy import SQLAlchemy
from models import db
from datetime import timedelta

load_dotenv()

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

app = Flask(__name__)

# -------------------------
# Configuration
# -------------------------

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(minutes=30)

# -------------------------
# Extensions
# -------------------------

# db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
api = Api(app)

db.init_app(app)
migrate.init_app(app, db)
jwt.init_app(app)

CORS(app)

# -------------------------
# Routes
# -------------------------

@app.route("/")
def home():
    return jsonify({
        "message": "Madrasatul Kheirat API is running"
    })



if __name__ == "__main__":
    app.run(debug=True)