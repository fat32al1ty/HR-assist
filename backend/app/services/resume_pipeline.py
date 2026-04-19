from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.repositories.resumes import create_resume_record, update_resume_processing_result
from app.services.file_storage import save_upload
from app.services.resume_analyzer import analyze_resume_text
from app.services.resume_parser import extract_text
from app.services.resume_profile_pipeline import persist_resume_profile


def process_resume_upload(db: Session, *, user_id: int, upload: UploadFile, content: bytes):
    storage_path = save_upload(content, upload.filename or "resume")
    resume = create_resume_record(
        db,
        user_id=user_id,
        original_filename=upload.filename or "resume",
        content_type=upload.content_type or "application/octet-stream",
        storage_path=storage_path,
    )

    try:
        resume = update_resume_processing_result(db, resume, status="processing")
        extracted_text = extract_text(content, resume.content_type)
        if not extracted_text.strip():
            raise ValueError("Could not extract text from the uploaded resume")

        resume = update_resume_processing_result(
            db,
            resume,
            status="processing",
            extracted_text=extracted_text,
        )
        analysis = analyze_resume_text(extracted_text)
        persist_resume_profile(db, resume_id=resume.id, user_id=user_id, profile=analysis)
        return update_resume_processing_result(
            db,
            resume,
            status="completed",
            extracted_text=extracted_text,
            analysis=analysis,
        )
    except Exception as error:
        return update_resume_processing_result(
            db,
            resume,
            status="failed",
            extracted_text=resume.extracted_text,
            error_message=str(error),
        )
