"""SQLAlchemy models for the ESCO reference tables.

Four read-only tables loaded from the ESCO v1.1 CSV dump:

- ``EscoOccupation`` — ~3000 job roles, with ISCO group + broader-role FK.
- ``EscoSkill`` — ~13500 skills, each tagged with a reuse level.
- ``EscoOccupationSkill`` — essential/optional skills per occupation.
- ``EscoSkillRelation`` — broader/narrower skill hierarchy.

The tables are populated by ``backend/scripts/import_esco.py`` and
queried by ``app.services.esco`` for lookup + role distance. Nothing
else writes to them at runtime.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class EscoOccupation(Base):
    __tablename__ = "esco_occupation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    esco_uri: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    preferred_label_ru: Mapped[str | None] = mapped_column(Text, nullable=True)
    preferred_label_en: Mapped[str] = mapped_column(Text)
    alt_labels_ru: Mapped[list[str]] = mapped_column(ARRAY(Text()), server_default="{}")
    alt_labels_en: Mapped[list[str]] = mapped_column(ARRAY(Text()), server_default="{}")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    isco_group: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    broader_occupation_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("esco_occupation.id", ondelete="SET NULL"),
        nullable=True,
    )

    broader = relationship("EscoOccupation", remote_side="EscoOccupation.id")


class EscoSkill(Base):
    __tablename__ = "esco_skill"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    esco_uri: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    preferred_label_ru: Mapped[str | None] = mapped_column(Text, nullable=True)
    preferred_label_en: Mapped[str] = mapped_column(Text)
    alt_labels: Mapped[list[str]] = mapped_column(ARRAY(Text()), server_default="{}")
    reuse_level: Mapped[str | None] = mapped_column(String(40), nullable=True)
    skill_type: Mapped[str | None] = mapped_column(String(40), nullable=True)


class EscoOccupationSkill(Base):
    __tablename__ = "esco_occupation_skill"
    __table_args__ = (
        CheckConstraint(
            "relation IN ('essential', 'optional')",
            name="ck_esco_occupation_skill_relation",
        ),
    )

    occupation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("esco_occupation.id", ondelete="CASCADE"),
        primary_key=True,
    )
    skill_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("esco_skill.id", ondelete="CASCADE"),
        primary_key=True,
    )
    relation: Mapped[str] = mapped_column(String(20), primary_key=True)


class EscoSkillRelation(Base):
    __tablename__ = "esco_skill_relation"
    __table_args__ = (
        CheckConstraint(
            "relation IN ('broader', 'narrower')",
            name="ck_esco_skill_relation_kind",
        ),
    )

    from_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("esco_skill.id", ondelete="CASCADE"),
        primary_key=True,
    )
    to_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("esco_skill.id", ondelete="CASCADE"),
        primary_key=True,
    )
    relation: Mapped[str] = mapped_column(String(20), primary_key=True)
