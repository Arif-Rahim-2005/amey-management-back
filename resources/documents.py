import cloudinary.uploader

from flask import request
from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import SQLAlchemyError

from models import db, User, Document, ConsignmentFile


EDITABLE_FIELDS = {"title", "document_type" }
AUTHORISED_ROLES = {"admin", "employee"}


def get_current_user():
    identity = get_jwt_identity()

    try:
        return db.session.get(User, int(identity))
    except (TypeError, ValueError):
        return None


def document_to_dict(document):
    return {
        "id": document.id,
        "file_id": document.file_id,
        "title": document.title,
        "filename": document.filename,
        "url": document.url,
        "document_type": document.document_type,
        "uploaded_at": (
            document.uploaded_at.isoformat()
            if document.uploaded_at else None
        ),
        "updated_at": (
            document.updated_at.isoformat()
            if document.updated_at else None
        ),
    }


def get_document_or_404(document_id):
    document = db.session.get(Document, document_id)

    if not document:
        return None, ({"message": "Document not found"}, 404)

    return document, None


def validate_metadata(data, creating=False):
    if not isinstance(data, dict):
        raise ValueError("Request body must be a JSON object")

    allowed_fields = EDITABLE_FIELDS | ({"file_id"} if creating else set())
    unknown_fields = set(data) - allowed_fields

    if unknown_fields:
        raise ValueError(
            f"Unsupported field(s): {', '.join(sorted(unknown_fields))}"
        )

    cleaned = {}

    if creating:
        file_id = data.get("file_id")

        if file_id is None or isinstance(file_id, bool):
            raise ValueError("file_id is required and must be an integer")

        try:
            file_id = int(file_id)
        except (TypeError, ValueError):
            raise ValueError("file_id must be a valid integer")

        if file_id <= 0:
            raise ValueError("file_id must be a positive integer")

        if not db.session.get(ConsignmentFile, file_id):
            raise LookupError("Consignment file not found")

        cleaned["file_id"] = file_id

    for field in EDITABLE_FIELDS:
        if field not in data:
            continue

        value = data[field]

        if field == "title":
            if not isinstance(value, str) or not value.strip():
                raise ValueError("title must be a non-empty string")
            cleaned[field] = value.strip()

        else:
            if value is not None and not isinstance(value, str):
                raise ValueError(f"{field} must be a string or null")

            cleaned[field] = value.strip() or None if value is not None else None

    if creating and "title" not in cleaned:
        raise ValueError("title is required")

    return cleaned


class DocumentListResource(Resource):

    @jwt_required()
    def get(self):
        user = get_current_user()

        if not user or not user.is_active:
            return {"message": "Invalid or inactive user"}, 403

        query = Document.query

        file_id = request.args.get("file_id")

        if file_id is not None:
            try:
                file_id = int(file_id)
                if file_id <= 0:
                    raise ValueError
            except (TypeError, ValueError):
                return {"message": "file_id must be a positive integer"}, 400

            query = query.filter_by(file_id=file_id)

        documents = query.order_by(Document.uploaded_at.desc()).all()

        return [document_to_dict(doc) for doc in documents], 200

    @jwt_required()
    def post(self):
        user = get_current_user()

        if not user or not user.is_active:
            return {"message": "Invalid or inactive user"}, 403

        if user.role not in AUTHORISED_ROLES:
            return {"message": "You are not authorized to upload documents"}, 403

        uploaded_file = request.files.get("document")

        if not uploaded_file or not uploaded_file.filename:
            return {"message": "A document file is required"}, 400

        title = request.form.get("title", "").strip()
        document_type = request.form.get("document_type", "").strip() or None
        file_id = request.form.get("file_id", "").strip()

        if not title:
            return {"message": "Document title is required"}, 400

        try:
            cleaned = validate_metadata(
                {
                    "file_id": file_id,
                    "title": title,
                    "document_type": document_type,
                },
                creating=True,
            )
        except LookupError as error:
            return {"message": str(error)}, 404
        except ValueError as error:
            return {"message": str(error)}, 400

        try:
            upload_result = cloudinary.uploader.upload(
                uploaded_file,
                resource_type="raw",
            )

            public_id = upload_result["public_id"]
            secure_url = upload_result["secure_url"]

        except Exception as error:
            return {
                "message": "Cloudinary upload failed",
                "error": str(error),
            }, 502

        document = Document(
            file_id=cleaned["file_id"],
            title=cleaned["title"],
            filename=uploaded_file.filename,
            url=secure_url,
            public_id=public_id,
            document_type=cleaned.get("document_type"),
        )

        try:
            db.session.add(document)
            db.session.commit()

        except SQLAlchemyError:
            db.session.rollback()

            try:
                cloudinary.uploader.destroy(
                    public_id,
                    resource_type="raw",
                )
            except Exception:
                pass

            return {
                "message": "Document could not be saved to the database"
            }, 500

        return {
            "message": "Document uploaded successfully",
            "document": document_to_dict(document),
        }, 201


class DocumentResource(Resource):

    @jwt_required()
    def get(self, document_id):
        user = get_current_user()

        if not user or not user.is_active:
            return {"message": "Invalid or inactive user"}, 403

        document, error = get_document_or_404(document_id)

        if error:
            return error

        return document_to_dict(document), 200

    @jwt_required()
    def patch(self, document_id):
        user = get_current_user()

        if not user or not user.is_active:
            return {"message": "Invalid or inactive user"}, 403

        if user.role not in AUTHORISED_ROLES:
            return {"message": "You are not authorized to edit documents"}, 403

        document, error = get_document_or_404(document_id)

        if error:
            return error

        data = request.get_json(silent=True)

        if not isinstance(data, dict) or not data:
            return {"message": "A non-empty JSON object is required"}, 400

        try:
            cleaned = validate_metadata(data)
        except ValueError as error:
            return {"message": str(error)}, 400

        for field, value in cleaned.items():
            setattr(document, field, value)

        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            return {"message": "Could not update document"}, 500

        return {
            "message": "Document updated successfully",
            "document": document_to_dict(document),
        }, 200

    @jwt_required()
    def delete(self, document_id):
        user = get_current_user()

        if not user or not user.is_active:
            return {"message": "Invalid or inactive user"}, 403

        if user.role not in AUTHORISED_ROLES:
            return {"message": "You are not authorized to delete documents"}, 403

        document, error = get_document_or_404(document_id)

        if error:
            return error

        # Delete the Cloudinary resource first.
        try:
            result = cloudinary.uploader.destroy(
                document.public_id,
                resource_type="raw",
            )
        except Exception:
            return {
                "message": "Cloudinary deletion failed; document was not removed from the database"
            }, 502

        # Do not remove the database record if Cloudinary reports failure.
        if result.get("result") not in {"ok", "not found"}:
            return {
                "message": "Cloudinary did not confirm document deletion",
                "cloudinary_result": result.get("result"),
            }, 502

        try:
            db.session.delete(document)
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            return {
                "message": "Cloudinary resource was deleted, but the database record could not be removed"
            }, 500

        return {"message": "Document deleted successfully"}, 200


class DocumentReplaceResource(Resource):
    @jwt_required()
    def put(self, document_id):
        user = get_current_user()

        if not user or not user.is_active:
            return {"message": "Invalid or inactive user"}, 403

        if user.role not in AUTHORISED_ROLES:
            return {"message": "You are not authorized to replace documents"}, 403

        document, error = get_document_or_404(document_id)

        if error:
            return error

        uploaded_file = request.files.get("document")

        if not uploaded_file or not uploaded_file.filename:
            return {"message": "A replacement document is required"}, 400

        # Upload the replacement file to Cloudinary first.
        try:
            upload_result = cloudinary.uploader.upload(
                uploaded_file,
                resource_type="raw"
            )

            new_public_id = upload_result["public_id"]
            new_url = upload_result["secure_url"]

        except Exception as error:
            return {
                "message": "Replacement upload failed",
                "error": str(error)
            }, 502

        # Keep the old file details in case the database update fails.
        old_public_id = document.public_id
        old_filename = document.filename
        old_url = document.url

        try:
            document.filename = uploaded_file.filename
            document.url = new_url
            document.public_id = new_public_id

            # Update these only when supplied.
            if "title" in request.form:
                title = request.form.get("title", "").strip()

                if not title:
                    cloudinary.uploader.destroy(
                        new_public_id,
                        resource_type="raw"
                    )
                    return {"message": "Title cannot be empty"}, 400

                document.title = title

            if "document_type" in request.form:
                document_type = request.form.get(
                    "document_type", ""
                ).strip()

                document.document_type = document_type or None

            db.session.commit()

        except SQLAlchemyError:
            db.session.rollback()

            # Clean up the newly uploaded file if saving fails.
            try:
                cloudinary.uploader.destroy(
                    new_public_id,
                    resource_type="raw"
                )
            except Exception:
                pass

            return {
                "message": "Could not save replacement document"
            }, 500

        # The database now points to the replacement.
        # Delete the previous Cloudinary file afterward.
        try:
            if old_public_id != new_public_id:
                cloudinary.uploader.destroy(
                    old_public_id,
                    resource_type="raw"
                )
        except Exception:
            # The replacement is already saved; old-file cleanup
            # can be retried if Cloudinary deletion fails.
            pass

        return {
            "message": "Document replaced successfully",
            "document": document_to_dict(document)
        }, 200