from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models.project_model import Project
from models.report_model import Report
from models.user_model import User
from schemas.project_schema import ProjectCreate, ProjectResponse
from schemas.report_schema import ReportCreate, ReportResponse
from dependencies import get_current_user, get_owned_project

router = APIRouter(prefix="/projects", tags=["Projects"])

@router.post("/", response_model=ProjectResponse)
def create_project(
    data: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Ownership comes from the JWT, never from the request body.
    project = Project(**data.model_dump())
    project.user_id = current_user.id
    db.add(project)
    db.commit()
    db.refresh(project)
    return project

@router.get("/", response_model=List[ProjectResponse])
def get_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(Project).filter(
        Project.user_id == current_user.id
    ).order_by(Project.created_at.desc()).all()

@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project: Project = Depends(get_owned_project)):
    return project

@router.post("/{project_id}/report", response_model=ReportResponse)
def save_report(
    data: ReportCreate,
    project: Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    existing = db.query(Report).filter(Report.project_id == project.id).first()
    if existing:
        existing.report_content = data.report_content
        existing.report_format = data.report_format
        existing.financial_format = data.financial_format
        existing.status = "completed"
        db.commit()
        db.refresh(existing)
        return existing
    report = Report(
        project_id=project.id,
        report_content=data.report_content,
        report_format=data.report_format,
        financial_format=data.financial_format,
        status="completed"
    )
    db.add(report)
    project.status = "completed"
    db.commit()
    db.refresh(report)
    return report

@router.get("/{project_id}/report", response_model=ReportResponse)
def get_report(
    project: Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    report = db.query(Report).filter(Report.project_id == project.id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report

@router.delete("/{project_id}")
def delete_project(
    project: Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    db.delete(project)
    db.commit()
    return {"message": "Project deleted"}
