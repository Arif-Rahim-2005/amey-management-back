from datetime import datetime, timezone

from flask import request
from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import IntegrityError

from models import db, User, Container, ConsignmentFile


DATETIME_FIELDS = {
    "offloaded_at",
    "exited_at",
    "reached_depot_at",
}
EDITABLE_FIELDS = {
    "file_id",
    "container_number",
    "container_size",
    "container_type",
    "truck_number",
    "storage_location_type",
    "storage_location_name",
    *DATETIME_FIELDS,
}

CONTAINER_SIZES = {"20ft", "40ft", "45ft"}
CONTAINER_TYPES = {"DRY", "REEFER", "OPEN_TOP", "FLAT_RACK", "TANK"}
STORAGE_LOCATION_TYPES = {"PORT", "CFS"}


def get_current_user():
    identity = get_jwt_identity()

    try:
        return db.session.get(User, int(identity))
    except (TypeError, ValueError):
        return None


def parse_datetime(field, value):
    if value is None:
        return None

    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO datetime string")

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"{field} must be a valid ISO datetime")

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed


def validate_container_data(data, creating=False):
    unknown = set(data) - EDITABLE_FIELDS

    if unknown:
        raise ValueError(
            f"Unknown or non-editable fields: {', '.join(sorted(unknown))}"
        )

    required = {"file_id", "container_number"}

    if creating:
        missing = required - set(data)

        if missing:
            raise ValueError(
                f"Missing required fields: {', '.join(sorted(missing))}"
            )

    cleaned = {}

    for field, value in data.items():
        if field in DATETIME_FIELDS:
            cleaned[field] = parse_datetime(field, value)

        elif field == "file_id":
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError("file_id must be an integer")

            if value <= 0:
                raise ValueError("file_id must be a positive integer")

            if not db.session.get(ConsignmentFile, value):
                raise ValueError("The specified consignment file does not exist")

            cleaned[field] = value

        elif field == "container_number":
            if not isinstance(value, str) or not value.strip():
                raise ValueError("container_number cannot be empty")

            cleaned[field] = value.strip().upper()

        elif field == "container_size":
            if not isinstance(value, str) or value not in CONTAINER_SIZES:
                raise ValueError(
                    f"container_size must be one of: {', '.join(sorted(CONTAINER_SIZES))}"
                )

            cleaned[field] = value

        elif field == "container_type":
            if not isinstance(value, str) or value not in CONTAINER_TYPES:
                raise ValueError(
                    f"container_type must be one of: {', '.join(sorted(CONTAINER_TYPES))}"
                )

            cleaned[field] = value

        elif field == "truck_number":
            if value is not None and not isinstance(value, str):
                raise ValueError("truck_number must be a string or null")

            cleaned[field] = value.strip().upper() if value else None


        elif field == "storage_location_type":
            if value is not None:
                if not isinstance(value, str):
                    raise ValueError(
                        "storage_location_type must be PORT, CFS, or null"
                    )

                value = value.strip().upper()

                if value not in STORAGE_LOCATION_TYPES:
                    raise ValueError(
                        "storage_location_type must be PORT or CFS"
                    )

            cleaned[field] = value

        elif field == "storage_location_name":
            if value is not None and not isinstance(value, str):
                raise ValueError(
                    "storage_location_name must be a string or null"
                )

            if isinstance(value, str):
                value = value.strip()

                if len(value) > 150:
                    raise ValueError(
                        "storage_location_name cannot exceed 150 characters"
                    )

            cleaned[field] = value or None

            

    return cleaned


class ContainerListResource(Resource):

    @jwt_required()
    def get(self):
        user = get_current_user()

        if not user or not user.is_active:
            return {"message": "Invalid or inactive user"}, 403

        query = Container.query

        file_id = request.args.get("file_id")

        if file_id is not None:
            try:
                file_id = int(file_id)

                if file_id <= 0:
                    raise ValueError

            except ValueError:
                return {"message": "file_id must be a positive integer"}, 400

            query = query.filter_by(file_id=file_id)

        containers = query.order_by(Container.created_at.desc()).all()

        return [container.to_dict() for container in containers], 200

    @jwt_required()
    def post(self):
        user = get_current_user()

        if not user or not user.is_active:
            return {"message": "Invalid or inactive user"}, 403

        if user.role != "employee" and user.role != "admin":
            return {"message": "Only authorized users can add containers"}, 403

        data = request.get_json(silent=True)

        if not isinstance(data, dict):
            return {"message": "Request body must be valid JSON"}, 400

        try:
            cleaned = validate_container_data(data, creating=True)
            container = Container(**cleaned)

            db.session.add(container)
            db.session.commit()

        except ValueError as error:
            db.session.rollback()
            return {"message": str(error)}, 400

        except IntegrityError:
            db.session.rollback()
            return {"message": "Could not create container"}, 409

        return container.to_dict(), 201


class ContainerResource(Resource):

    @jwt_required()
    def get(self, container_id):
        user = get_current_user()

        if not user or not user.is_active:
            return {"message": "Invalid or inactive user"}, 403

        container = db.session.get(Container, container_id)

        if not container:
            return {"message": "Container not found"}, 404

        return container.to_dict(), 200

    @jwt_required()
    def patch(self, container_id):
        user = get_current_user()

        if not user or not user.is_active:
            return {"message": "Invalid or inactive user"}, 403

        if user.role != "employee" and user.role != "admin":
            return {"message": "Only authorized users can update containers"}, 403

        container = db.session.get(Container, container_id)

        if not container:
            return {"message": "Container not found"}, 404

        data = request.get_json(silent=True)

        if not isinstance(data, dict) or not data:
            return {"message": "Provide a non-empty JSON object"}, 400

        try:
            cleaned = validate_container_data(data)

            new_location_type = cleaned.get(
                "storage_location_type",
                container.storage_location_type,
            )
            new_location_name = cleaned.get(
                "storage_location_name",
                container.storage_location_name,
            )

            if new_location_type and not new_location_name:
                raise ValueError(
                    "storage_location_name is required when a location type is provided"
                )

            for field, value in cleaned.items():
                setattr(container, field, value)

            db.session.commit()

        except ValueError as error:
            db.session.rollback()
            return {"message": str(error)}, 400

        except IntegrityError:
            db.session.rollback()
            return {"message": "Could not update container"}, 409

        return {"message": "Container updated successfully", **container.to_dict()}, 200

    @jwt_required()
    def delete(self, container_id):
        user = get_current_user()

        if not user or not user.is_active:
            return {"message": "Invalid or inactive user"}, 403

        if user.role != "employee" and user.role != "admin":
            return {"message": "Only authorized users can delete containers"}, 403

        container = db.session.get(Container, container_id)

        if not container:
            return {"message": "Container not found"}, 404

        try:
            db.session.delete(container)
            db.session.commit()

        except IntegrityError:
            db.session.rollback()
            return {"message": "Could not delete container"}, 409

        return {"message": "Container deleted successfully"}, 200