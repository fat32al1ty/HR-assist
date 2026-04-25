from app.models.application import Application
from app.models.auth_otp_code import AuthOtpCode
from app.models.esco import (
    EscoOccupation,
    EscoOccupationSkill,
    EscoSkill,
    EscoSkillRelation,
)
from app.models.match_telemetry import MatchClick, MatchDwell, MatchImpression
from app.models.recommendation_correction import RecommendationCorrection
from app.models.recommendation_job import RecommendationJob
from app.models.resume import Resume
from app.models.resume_audit import ResumeAudit
from app.models.resume_clarification import ResumeClarification
from app.models.resume_profile import ResumeProfile
from app.models.resume_user_skill import ResumeUserSkill
from app.models.resume_vacancy_score import ResumeVacancyScore
from app.models.track_gap_analysis import TrackGapAnalysis
from app.models.user import User
from app.models.user_daily_spend import UserDailySpend
from app.models.user_login_event import UserLoginEvent
from app.models.user_vacancy_feedback import UserVacancyFeedback
from app.models.user_vacancy_seen import UserVacancySeen
from app.models.vacancy import Vacancy
from app.models.vacancy_profile import VacancyProfile
from app.models.vacancy_strategy import VacancyStrategy

__all__ = [
    "Application",
    "AuthOtpCode",
    "EscoOccupation",
    "EscoOccupationSkill",
    "EscoSkill",
    "EscoSkillRelation",
    "MatchClick",
    "MatchDwell",
    "MatchImpression",
    "RecommendationCorrection",
    "RecommendationJob",
    "Resume",
    "ResumeAudit",
    "ResumeClarification",
    "ResumeVacancyScore",
    "ResumeProfile",
    "ResumeUserSkill",
    "User",
    "UserDailySpend",
    "UserLoginEvent",
    "UserVacancyFeedback",
    "UserVacancySeen",
    "TrackGapAnalysis",
    "Vacancy",
    "VacancyProfile",
    "VacancyStrategy",
]
