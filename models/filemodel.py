from datetime import datetime, timezone
from models import db


def utc_now():
    return datetime.now(timezone.utc)


class ConsignmentFile(db.Model):
    __tablename__ = "consignment_files"

    id = db.Column(db.Integer, primary_key=True)

    # Basic file information

    category = db.Column(
        db.String(30),
        nullable=False,
        index=True,
    )


    bl_number = db.Column(
        db.String(100),
        nullable=False,
        index=True,
        unique=True,
    )

    consignee = db.Column(db.String(255), nullable=False)
    cargo_description = db.Column(db.Text, nullable=False)

    date_opened = db.Column(
        db.Date,
        nullable=False,
        default=lambda: utc_now().date(),
    )

    # Keep the original ETA separate from the latest ETA.
    initial_eta = db.Column(db.Date, nullable=True)
    current_eta = db.Column(db.Date, nullable=True)

    # KWATOS tracking
    kwatos_status = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )

    vessel_name = db.Column(db.String(150), nullable=True)

# Shipping charges workflow
    shipping_charges_requested = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )

    shipping_charges_paid = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )

    charges_requested_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
    )

    shipping_charges_paid_date = db.Column(
        db.Date,
        nullable=True,
    )


# Delivery Order workflow
    do_requested = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )

    do_requested_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
    )

    do_obtained = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )

    do_obtained_date = db.Column(
        db.Date,
        nullable=True,
    )


    # Delivery Order and depot information
    depot_name = db.Column(db.String(200), nullable=True)
    free_days = db.Column(db.Integer, nullable=True)
    guarantee_expiry_date = db.Column(db.Date, nullable=True)

    # Mother entry
    mother_entry_number = db.Column(db.String(100), nullable=True)
    mother_entry_date = db.Column(
    db.DateTime(timezone=True),
    nullable=True,
)

    # File lifecycle
    status = db.Column(
        db.String(30),
        nullable=False,
        default="OPEN",
        index=True,
    )

    ready_to_close = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )

    closed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    closed_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True,
    )

    closure_reason = db.Column(db.Text, nullable=True)

    # Ownership and audit timestamps
    created_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    # Relationships
    containers = db.relationship(
        "Container",
        back_populates="file",
        cascade="all, delete-orphan",
        lazy=True,
    )

    documents = db.relationship(
        "Document",
        back_populates="file",
        cascade="all, delete-orphan",
        lazy=True,
    )

    comments = db.relationship(
        "FileComment",
        back_populates="file",
        cascade="all, delete-orphan",
        lazy=True,
    )

    created_by = db.relationship(
        "User",
        foreign_keys=[created_by_id],
        back_populates="consignment_files"
    )   

    closed_by = db.relationship(
        "User",
        foreign_keys=[closed_by_id],
    )
    
    def to_dict(self, include_containers=True):
        data = {
            "id": self.id,
            "category": self.category,
            "bl_number": self.bl_number,
            "consignee": self.consignee,
            "cargo_description": self.cargo_description,
            "date_opened": (
                self.date_opened.isoformat()
                if self.date_opened else None
            ),
            "initial_eta": (
                self.initial_eta.isoformat()
                if self.initial_eta else None
            ),
            "current_eta": (
                self.current_eta.isoformat()
                if self.current_eta else None
            ),
            "kwatos_status": self.kwatos_status,
            "vessel_name": self.vessel_name,
            "shipping_charges_requested": self.shipping_charges_requested,
            "shipping_charges_paid": self.shipping_charges_paid,
            "charges_requested_at": (
                self.charges_requested_at.isoformat()
                if self.charges_requested_at else None
            ),
            "shipping_charges_paid_date": (
                self.shipping_charges_paid_date.isoformat()
                if self.shipping_charges_paid_date else None
            ),
            "do_requested": self.do_requested,
            "do_obtained": self.do_obtained,
            "do_requested_at": (
                self.do_requested_at.isoformat()
                if self.do_requested_at else None
            ),
            "do_obtained_date": (
                self.do_obtained_date.isoformat()
                if self.do_obtained_date else None
            ),
            "depot_name": self.depot_name,
            "free_days": self.free_days,
            "guarantee_expiry_date": (
                self.guarantee_expiry_date.isoformat()
                if self.guarantee_expiry_date else None
            ),
            "mother_entry_number": self.mother_entry_number,
            "mother_entry_date": (
                self.mother_entry_date.isoformat()
                if self.mother_entry_date else None
            ),
            "status": self.status,
            "ready_to_close": self.ready_to_close,
            "closed_at": (
                self.closed_at.isoformat()
                if self.closed_at else None
            ),
            "closed_by_id": self.closed_by_id,
            "closure_reason": self.closure_reason,
            "created_by_id": self.created_by_id,
            "created_at": (
                self.created_at.isoformat()
                if self.created_at else None
            ),
            "updated_at": (
                self.updated_at.isoformat()
                if self.updated_at else None
            ),
        }

        if include_containers:
            data["containers"] = [
                container.to_dict()
                for container in self.containers
            ]

        return data