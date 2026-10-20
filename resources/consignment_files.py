from datetime import date, datetime, timezone


from flask import request
from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import IntegrityError

from models import db, User, ConsignmentFile

DATE_FIELDS = {
"date_opened",
"initial_eta",
"current_eta",
"shipping_charges_paid_date",
"do_obtained_date",
"guarantee_expiry_date",
}

DATETIME_FIELDS = {
"charges_requested_at",
"do_requested_at",
"mother_entry_date",
}

BOOLEAN_FIELDS = {
"kwatos_status",
"shipping_charges_requested",
"shipping_charges_paid",
"do_requested",
"do_obtained",
"ready_to_close",
}

STRING_FIELDS = {
"category",
"bl_number",
"consignee",
"cargo_description",
"shipping_line",
"vessel_name",
"depot_name",
"mother_entry_number",
"status",
"closure_reason",
}

INTEGER_FIELDS = {"free_days"}

EDITABLE_FIELDS = (
DATE_FIELDS
| DATETIME_FIELDS
| BOOLEAN_FIELDS
| STRING_FIELDS
| INTEGER_FIELDS
)

def get_current_user():
    identity = get_jwt_identity()
    try:
        return db.session.get(User, int(identity))
    except (TypeError, ValueError):
        return None


def parse_value(field, value):
    if value is None:
        if field in {
            "category",
            "bl_number",
            "consignee",
            "cargo_description",
        }:
            raise ValueError(f"{field} cannot be null")
        return None

    if field in DATE_FIELDS:
        if not isinstance(value, str):
            raise ValueError(f"{field} must be an ISO date string")
        return date.fromisoformat(value)

    if field in DATETIME_FIELDS:
        if not isinstance(value, str):
            raise ValueError(f"{field} must be an ISO datetime string")

        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed

    if field in BOOLEAN_FIELDS:
        if not isinstance(value, bool):
            raise ValueError(f"{field} must be true or false")
        return value

    if field in INTEGER_FIELDS:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{field} must be an integer")
        if value < 0:
            raise ValueError(f"{field} cannot be negative")
        return value

    if field in STRING_FIELDS:
        if not isinstance(value, str):
            raise ValueError(f"{field} must be a string")

        value = value.strip()

        if field in {
            "category",
            "bl_number",
            "consignee",
            "cargo_description",
        } and not value:
            raise ValueError(f"{field} cannot be empty")

        return value or None

    return value

class ConsignmentFileListResource(Resource):
    @jwt_required()
    def get(self):
        user = get_current_user()
        if not user or not user.is_active:
            return {"message": "Invalid or inactive user"}, 403

        files = ConsignmentFile.query.order_by(
            ConsignmentFile.created_at.desc()
        ).all()

        return [file.to_dict() for file in files], 200

    @jwt_required()
    def post(self):
        user = get_current_user()
        if not user or not user.is_active:
            return {"message": "Invalid or inactive user"}, 403

        if user.role != "employee" and user.role != "admin":
            return {"message": "Only authorized users can create consignment files"}, 403

        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return {"message": "Request body must be valid JSON"}, 400

        unknown = set(data) - EDITABLE_FIELDS
        if unknown:
            return {
                "message": "Unknown or non-editable fields",
                "fields": sorted(unknown),
            }, 400

        required = {"category", "bl_number", "consignee", "cargo_description"}
        missing = required - set(data)
        if missing:
            return {
                "message": "Missing required fields",
                "fields": sorted(missing),
            }, 400

        file = ConsignmentFile()

        try:
            for field, value in data.items():
                setattr(file, field, parse_value(field, value))

            db.session.add(file)
            db.session.commit()

        except ValueError as error:
            db.session.rollback()
            return {"message": str(error)}, 400
        except IntegrityError:
            db.session.rollback()
            return {"message": "A file with this BL number already exists"}, 409

        return file.to_dict(), 201

class ConsignmentFileResource(Resource):
    @jwt_required()
    def get(self, file_id):
        user = get_current_user()
        if not user or not user.is_active:
            return {"message": "Invalid or inactive user"}, 403

        file = db.session.get(ConsignmentFile, file_id)
        if not file:
            return {"message": "Consignment file not found"}, 404

        return file.to_dict(), 200

    @jwt_required()
    def patch(self, file_id):
        user = get_current_user()
        if not user or not user.is_active:
            return {"message": "Invalid or inactive user"}, 403

        if user.role != "employee" and user.role != "admin":
            return {"message": "Only authorized users can update consignment files"}, 403

        file = db.session.get(ConsignmentFile, file_id)
        if not file:
            return {"message": "Consignment file not found"}, 404

        data = request.get_json(silent=True)
        if not isinstance(data, dict) or not data:
            return {"message": "Provide a non-empty JSON object"}, 400

        unknown = set(data) - EDITABLE_FIELDS
        if unknown:
            return {
                "message": "Unknown or non-editable fields",
                "fields": sorted(unknown),
            }, 400

        try:
            for field, value in data.items():
                setattr(file, field, parse_value(field, value))

            db.session.commit()

        except ValueError as error:
            db.session.rollback()
            return {"message": str(error)}, 400
        except IntegrityError:
            db.session.rollback()
            return {"message": "Duplicate BL number or invalid update"}, 409

        return {"message": "Consignment file updated successfully", **file.to_dict()}, 200

    @jwt_required()
    def delete(self, file_id):
        user = get_current_user()
        if not user or not user.is_active:
            return {"message": "Invalid or inactive user"}, 403

        if user.role != "employee" and user.role != "admin":
            return {"message": "Only authorized users can delete consignment files"}, 403

        file = db.session.get(ConsignmentFile, file_id)
        if not file:
            return {"message": "Consignment file not found"}, 404

        try:
            db.session.delete(file)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return {"message": "Could not delete the consignment file"}, 409

        return {"message": "Consignment file deleted successfully"}, 200
