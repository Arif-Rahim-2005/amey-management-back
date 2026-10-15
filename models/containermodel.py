from datetime import datetime, timezone
from models import db

def utc_now():
    return datetime.now(timezone.utc)

class Container(db.Model):
    __tablename__ = "containers"

    id = db.Column(db.Integer, primary_key=True)

    # Link this container to its consignment file
    file_id = db.Column(
        db.Integer,
        db.ForeignKey("consignment_files.id"),
        nullable=False
    )

    # Container information
    container_number = db.Column(
        db.String(100),
        nullable=False,
        index=True
    )

    container_size = db.Column(
        db.String(10),
        nullable=False,
        default="20ft"
    )

    container_type = db.Column(
        db.String(30),
        nullable=False,
        default="DRY"
    )

    truck_number = db.Column(db.String(50), nullable=True)

    # Container tracking dates
    offloaded_at = db.Column(db.DateTime(timezone=True), nullable=True)
    exited_at = db.Column(db.DateTime(timezone=True), nullable=True)
    reached_depot_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Record creation and updates
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now
    )

    # Relationship back to the consignment file
    file = db.relationship("ConsignmentFile", back_populates="containers")

    def to_dict(self):
        return {
            "id": self.id,
            "file_id": self.file_id,
            "container_number": self.container_number,
            "container_size": self.container_size,
            "container_type": self.container_type,
            "truck_number": self.truck_number,
            "offloaded_at": self.offloaded_at.isoformat() if self.offloaded_at else None,
            "exited_at": self.exited_at.isoformat() if self.exited_at else None,
            "reached_depot_at": self.reached_depot_at.isoformat() if self.reached_depot_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
