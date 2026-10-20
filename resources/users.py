from html import parser

from flask_restful import Resource, reqparse
from flask_bcrypt import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from models import db, User
from datetime import timedelta
from datetime import datetime
from sqlalchemy.exc import IntegrityError



class LogInResource(Resource):
    parser = reqparse.RequestParser()
    parser.add_argument("email", required=True, help="email is required")
    parser.add_argument("password", required=True, help="password is required")

    def post(self):
        data = self.parser.parse_args()

        user = User.query.filter_by(email=data["email"]).first()

        if user is None:
            return {"message": "invalid email or password. If you don't have an account, please signup"}, 403

        if user.is_active is False:
            return {"message": "Your account is deactivated. Please contact the admin."}, 403

        # validate password
        if check_password_hash(user.password_hash.decode('utf-8') if isinstance(user.password_hash, bytes) else user.password_hash, data["password"]):

            # then generate access token
            access_token = create_access_token(
                identity=str(user.id),
                expires_delta=timedelta(hours=24),
            )

            return {
                "message": "Logged in successfully",
                "access_token": access_token,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": user.role,
                    "is_active": user.is_active,
                },
            }, 200
        else:
            return {"message": "invalid email or password"}, 403


class SignupResource(Resource):
    parser = reqparse.RequestParser()
    parser.add_argument("username", type=str, required=True, help="Username is required")
    parser.add_argument("email", type=str, required=True, help="Email is required")
    parser.add_argument("password", type=str, required=True, help="Password is required")

    def post(self):
        data = SignupResource.parser.parse_args()
        username = data["username"]
        email = data["email"]
        password = data["password"]

        # ✅ Optional: check if username or email exists

        if User.query.filter_by(email=email).first():
            return {"message": "Email already registered"}, 400

        try:
            hashed_password = generate_password_hash(password).decode('utf-8')

            new_user = User(
                username=username,
                email=email,
                password_hash=hashed_password,
                role="user",  # Default role
                created_at=datetime.utcnow(),
            )
                        # generate access Token
            db.session.add(new_user)
            db.session.commit()

            access_token = create_access_token(
                identity=str(new_user.id),
                expires_delta=timedelta(hours=24),
            )

            return {
                "message": "Account created successfully",
                "access_token": access_token,
                "user": {
                    "id": new_user.id,
                    "username": new_user.username,
                    "email": new_user.email,
                    "role": new_user.role,
                    "is_active": new_user.is_active
                },
            }, 201

        except IntegrityError as e:
            db.session.rollback()
            return {"message": "User already exists", "error": str(e)}, 400

        except Exception as e:
            db.session.rollback()
            import traceback
            print("⚠️ ERROR IN SIGNUP ⚠️")
            traceback.print_exc()
            return {"message": "Error", "error": str(e)}, 500



class UserResource(Resource):
    parser = reqparse.RequestParser()
    parser.add_argument("username", type=str)
    parser.add_argument("email", type=str)
    parser.add_argument("role", type=str)
    parser.add_argument("is_active", type=str, choices=("true", "false", "True", "False"))

    @jwt_required()
    def get(self, user_id=None):
        current_user_id = get_jwt_identity()
        current_user = db.session.get(User, int(current_user_id))

        if not current_user:
            return {"message": "Invalid user"}, 404

        # Viewing one user: admins can view anyone; users can view themselves.
        if user_id is not None:
            user = db.session.get(User, user_id)

            if not user:
                return {"message": "User not found"}, 404

            if current_user.role != "admin" and current_user.id != user.id:
                return {"message": "You are not authorized to view this user"}, 403

            return {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "is_active": user.is_active,
            }, 200

        # Listing all users is admin-only.
        if current_user.role != "admin":
            return {"message": "Only admins can view all users"}, 403

        users = User.query.all()

        return [
            {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "is_active": user.is_active,
            }
            for user in users
        ], 200



    @jwt_required()
    def patch(self, user_id):
        current_user_id = get_jwt_identity()
        current_user = db.session.get(User, int(current_user_id))

        if not current_user or not current_user.is_active:
            return {"message": "Invalid or inactive user"}, 403

        user = db.session.get(User, user_id)
        if not user:
            return {"message": "User not found"}, 404

        # Only admins can update other users.
        if current_user.role != "admin" and current_user.id != user.id:
            return {"message": "You are not authorized to update this user"}, 403

        data = self.parser.parse_args()

        # Normal users may only change username and email.
        if current_user.role != "admin":
            if data["role"] is not None or data["is_active"] is not None:
                return {
                    "message": "Only admins can change roles or account status"
                }, 403

        # Validate role changes before making any changes.
        if data["role"] is not None:
            if data["role"] not in ["user", "admin", "employee"]:
                return {"message": "Invalid role"}, 400

            # Prevent accidentally removing the last admin.
            if user.role == "admin" and data["role"] != "admin":
                other_admins = User.query.filter(
                    User.role == "admin",
                    User.id != user.id
                ).count()

                if other_admins == 0:
                    return {
                        "message": "Cannot remove the last admin"
                    }, 400

        # Update supplied fields only.
        if data["username"] is not None:
            username = data["username"].strip()
            if not username:
                return {"message": "Username cannot be empty"}, 400
            user.username = username

        if data["email"] is not None:
            email = data["email"].strip().lower()

            if not email:
                return {"message": "Email cannot be empty"}, 400

            existing_user = User.query.filter(
                User.email == email,
                User.id != user.id
            ).first()

            if existing_user:
                return {"message": "Email already registered"}, 400

            user.email = email

        if data["role"] is not None:
            user.role = data["role"]

        # Only admins can change account status.
        if data["is_active"] is not None:
            user.is_active = data["is_active"].lower() == "true"

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return {"message": "Could not update user; check for duplicate values"}, 400

        return {
            "message": "User updated successfully",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "is_active": user.is_active,
            },
        }, 200

    @jwt_required()
    def delete(self, user_id):
        current_user_id = get_jwt_identity()
        current_user = db.session.get(User, int(current_user_id))

        if not current_user or not current_user.is_active:
            return {"message": "Invalid or inactive user"}, 403

        if current_user.role != "admin":
            return {"message": "Only admins can delete user accounts"}, 403

        user = db.session.get(User, user_id)
        if not user:
            return {"message": "User not found"}, 404

        # Prevent deletion of the last administrator.
        if user.role == "admin":
            other_admins = User.query.filter(
                User.role == "admin",
                User.id != user.id
            ).count()

            if other_admins == 0:
                return {"message": "Cannot delete the last admin"}, 400

        try:
            db.session.delete(user)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return {
                "message": "Cannot delete this user because other records still reference the account"
            }, 409

        return {"message": "User account deleted successfully"}, 200



class AdminResource(Resource):
    @jwt_required()
    def get(self):
        user_id = get_jwt_identity()
        user = db.session.get(User, int(user_id))

        if not user:
            return {"message": "User not found"}, 404

        if not user.is_active:
            return {"message": "Account is deactivated"}, 403

        if user.role != "admin":
            return {"message": "Admin access required"}, 403

        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "is_active": user.is_active,
        }, 200
