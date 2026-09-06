"""BantuDulu marketplace and external identity tables

Revision ID: 20260906_001
Revises:
Create Date: 2026-09-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260906_001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "external_identities",
        sa.Column("id", sa.String(length=12), primary_key=True),
        sa.Column("user_id", sa.String(length=12), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("provider_subject", sa.String(length=320), nullable=False, unique=True),
        sa.Column("email", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_external_identities_user_id", "external_identities", ["user_id"])
    op.create_index("ix_external_identities_provider", "external_identities", ["provider"])
    op.create_index("ix_external_identities_subject", "external_identities", ["subject"])

    op.create_table(
        "mitra",
        sa.Column("id", sa.String(length=12), primary_key=True),
        sa.Column("nama", sa.String(length=120), nullable=False),
        sa.Column("no_hp", sa.String(length=20), nullable=False),
        sa.Column("email", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("aktif", sa.Boolean(), nullable=False),
        sa.Column("rating", sa.Float(), nullable=False),
        sa.Column("total_jobs", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_mitra_no_hp", "mitra", ["no_hp"])
    op.create_index("ix_mitra_status", "mitra", ["status"])
    op.create_index("ix_mitra_aktif", "mitra", ["aktif"])

    op.create_table(
        "mitra_layanan",
        sa.Column("id", sa.String(length=12), primary_key=True),
        sa.Column("key", sa.String(length=64), nullable=False, unique=True),
        sa.Column("mitra_id", sa.String(length=12), sa.ForeignKey("mitra.id"), nullable=False),
        sa.Column("layanan_id", sa.String(length=12), sa.ForeignKey("layanan.id"), nullable=False),
        sa.Column("aktif", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_mitra_layanan_mitra_id", "mitra_layanan", ["mitra_id"])
    op.create_index("ix_mitra_layanan_layanan_id", "mitra_layanan", ["layanan_id"])

    op.create_table(
        "penugasan_mitra",
        sa.Column("id", sa.String(length=12), primary_key=True),
        sa.Column("pesanan_id", sa.String(length=12), sa.ForeignKey("pesanan.id"), nullable=False),
        sa.Column("mitra_id", sa.String(length=12), sa.ForeignKey("mitra.id"), nullable=False),
        sa.Column("assigned_by_user_id", sa.String(length=12), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("aktif", sa.Boolean(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_penugasan_mitra_pesanan_id", "penugasan_mitra", ["pesanan_id"])
    op.create_index("ix_penugasan_mitra_mitra_id", "penugasan_mitra", ["mitra_id"])
    op.create_index("ix_penugasan_mitra_status", "penugasan_mitra", ["status"])
    op.create_index("ix_penugasan_mitra_aktif", "penugasan_mitra", ["aktif"])

    op.create_table(
        "order_status_history",
        sa.Column("id", sa.String(length=12), primary_key=True),
        sa.Column("pesanan_id", sa.String(length=12), sa.ForeignKey("pesanan.id"), nullable=False),
        sa.Column("status_from", sa.String(length=30), nullable=True),
        sa.Column("status_to", sa.String(length=30), nullable=False),
        sa.Column("changed_by_user_id", sa.String(length=12), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("catatan", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_order_status_history_pesanan_id", "order_status_history", ["pesanan_id"])
    op.create_index("ix_order_status_history_status_to", "order_status_history", ["status_to"])

    op.create_table(
        "payment_transactions",
        sa.Column("id", sa.String(length=12), primary_key=True),
        sa.Column("pesanan_id", sa.String(length=12), sa.ForeignKey("pesanan.id"), nullable=False),
        sa.Column("method", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=True),
        sa.Column("reference_id", sa.String(length=120), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_payment_transactions_pesanan_id", "payment_transactions", ["pesanan_id"])
    op.create_index("ix_payment_transactions_method", "payment_transactions", ["method"])
    op.create_index("ix_payment_transactions_status", "payment_transactions", ["status"])


def downgrade() -> None:
    op.drop_table("payment_transactions")
    op.drop_table("order_status_history")
    op.drop_table("penugasan_mitra")
    op.drop_table("mitra_layanan")
    op.drop_table("mitra")
    op.drop_table("external_identities")
