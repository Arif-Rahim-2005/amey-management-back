from datetime import datetime, timezone
from models import db


def utc_now():
    return datetime.now(timezone.utc)


class Document(db.Model):
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)

    # Link this document to a consignment file
    file_id = db.Column(
        db.Integer,
        db.ForeignKey("consignment_files.id"),
        nullable=False,
        index=True
    )

    title = db.Column(db.String(500), nullable=False)
    filename = db.Column(db.String(500), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    public_id = db.Column(db.String(500), nullable=False)

    document_type = db.Column(db.String(50), nullable=True)
    
    uploaded_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        nullable=False
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False
    )

    file = db.relationship("ConsignmentFile", back_populates="documents")
