from pydantic import BaseModel, Field


class OnboardingQuestionOut(BaseModel):
    id: str
    text: str
    answer_type: str
    choices: list[str] = Field(default_factory=list)


class OnboardingAnswerIn(BaseModel):
    question_id: str
    answer_value: str
