from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models.project_model import Project
from models.report_model import Report
from schemas.project_schema import ProjectCreate, ProjectResponse
from schemas.report_schema import ReportCreate, ReportResponse

router = APIRouter(prefix="/projects", tags=["Projects"])

# Create a new project
@router.post("/", response_model=ProjectResponse)
def create_project(data: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(**data.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project

# Get all projects
@router.get("/", response_model=List[ProjectResponse])
def get_projects(db: Session = Depends(get_db)):
    return db.query(Project).order_by(Project.created_at.desc()).all()

# Get one project by ID
@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

# Save report for a project
@router.post("/{project_id}/report", response_model=ReportResponse)
def save_report(project_id: int, data: ReportCreate, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check if report already exists
    existing = db.query(Report).filter(Report.project_id == project_id).first()
    if existing:
        existing.report_content = data.report_content
        existing.report_format = data.report_format
        existing.financial_format = data.financial_format
        existing.status = "completed"
        db.commit()
        db.refresh(existing)
        return existing

    report = Report(
        project_id=project_id,
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

# Get report for a project
@router.get("/{project_id}/report", response_model=ReportResponse)
def get_report(project_id: int, db: Session = Depends(get_db)):
    report = db.query(Report).filter(Report.project_id == project_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report

# Delete a project
@router.delete("/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()
    return {"message": "Project deleted"}