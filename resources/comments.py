from flask import request
from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import SQLAlchemyError

from models import db, User, FileComment, ConsignmentFile


MANAGER_ROLES = {"admin", "employee"}


def get_current_user():
    identity = get_jwt_identity()

    try:
        return db.session.get(User, int(identity))
    except (TypeError, ValueError):
        return None


def comment_to_dict(comment):
    return {
        "id": comment.id,
        "file_id": comment.file_id,
        "comment": comment.comment,
        "created_at": (
            comment.created_at.isoformat()
            if comment.created_at else None
        )
    }


def get_comment_or_404(comment_id):
    comment = db.session.get(FileComment, comment_id)

    if not comment:
        return None, ({"message": "Comment not found"}, 404)

    return comment, None


class CommentListResource(Resource):

    @jwt_required()
    def get(self):
        user = get_current_user()

        if not user or not user.is_active:
            return {"message": "Invalid or inactive user"}, 403

        query = FileComment.query

        file_id = request.args.get("file_id")

        if file_id is not None:
            try:
                file_id = int(file_id)

                if file_id <= 0:
                    raise ValueError

            except (TypeError, ValueError):
                return {"message": "Invalid file_id"}, 400

            query = query.filter_by(file_id=file_id)

        comments = query.order_by(
            FileComment.created_at.desc()
        ).all()

        return [comment_to_dict(comment) for comment in comments], 200

    @jwt_required()
    def post(self):
        user = get_current_user()

        if not user or not user.is_active:
            return {"message": "Invalid or inactive user"}, 403

        if user.role not in MANAGER_ROLES:
            return {"message": "Permission denied"}, 403

        data = request.get_json(silent=True)

        if not isinstance(data, dict):
            return {"message": "Request body must be valid JSON"}, 400

        file_id = data.get("file_id")
        comment_text = data.get("comment")

        if file_id is None or isinstance(file_id, bool):
            return {"message": "file_id is required"}, 400

        try:
            file_id = int(file_id)

            if file_id <= 0:
                raise ValueError

        except (TypeError, ValueError):
            return {"message": "Invalid file_id"}, 400

        if not isinstance(comment_text, str) or not comment_text.strip():
            return {"message": "Comment cannot be empty"}, 400

        consignment_file = db.session.get(ConsignmentFile, file_id)

        if not consignment_file:
            return {"message": "Consignment file not found"}, 404

        new_comment = FileComment(
            file_id=file_id,
            comment=comment_text.strip()
        )

        try:
            db.session.add(new_comment)
            db.session.commit()

        except SQLAlchemyError:
            db.session.rollback()
            return {"message": "Could not create comment"}, 500

        return {
            "message": "Comment created successfully",
            "comment": comment_to_dict(new_comment)
        }, 201


class CommentResource(Resource):

    @jwt_required()
    def get(self, comment_id):
        user = get_current_user()

        if not user or not user.is_active:
            return {"message": "Invalid or inactive user"}, 403

        comment, error = get_comment_or_404(comment_id)

        if error:
            return error

        return comment_to_dict(comment), 200

    @jwt_required()
    def patch(self, comment_id):
        user = get_current_user()

        if not user or not user.is_active:
            return {"message": "Invalid or inactive user"}, 403

        if user.role not in MANAGER_ROLES:
            return {"message": "Permission denied"}, 403

        comment, error = get_comment_or_404(comment_id)

        if error:
            return error

        data = request.get_json(silent=True)

        if not isinstance(data, dict):
            return {"message": "Request body must be valid JSON"}, 400

        if set(data) != {"comment"}:
            return {
                "message": "Only the comment field can be updated"
            }, 400

        comment_text = data.get("comment")

        if not isinstance(comment_text, str) or not comment_text.strip():
            return {"message": "Comment cannot be empty"}, 400

        comment.comment = comment_text.strip()

        try:
            db.session.commit()

        except SQLAlchemyError:
            db.session.rollback()
            return {"message": "Could not update comment"}, 500

        return {
            "message": "Comment updated successfully",
            "comment": comment_to_dict(comment)
        }, 200

    @jwt_required()
    def delete(self, comment_id):
        user = get_current_user()

        if not user or not user.is_active:
            return {"message": "Invalid or inactive user"}, 403

        if user.role not in MANAGER_ROLES:
            return {"message": "Permission denied"}, 403

        comment, error = get_comment_or_404(comment_id)

        if error:
            return error

        try:
            db.session.delete(comment)
            db.session.commit()

        except SQLAlchemyError:
            db.session.rollback()
            return {"message": "Could not delete comment"}, 500

        return {"message": "Comment deleted successfully"}, 200