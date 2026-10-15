from datetime import datetime, timezone
from models import db


def utc_now():
    return datetime.now(timezone.utc)


class FileComment(db.Model):
    __tablename__ = "file_comments"

    id = db.Column(db.Integer, primary_key=True)

    file_id = db.Column(
        db.Integer,
        db.ForeignKey("consignment_files.id"),
        nullable=False,
        index=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True
    )

    comment = db.Column(db.Text, nullable=False)

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now
    )

    file = db.relationship(
        "ConsignmentFile",
        back_populates="comments"
    )

    user = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "file_id": self.file_id,
            "user_id": self.user_id,
            "comment": self.comment,
            "created_at": (
                self.created_at.isoformat()
                if self.created_at else None
            )
        }
