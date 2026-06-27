from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.industry_router import router as industry_router
from routers.country_router import router as country_router
from routers.purpose_router import router as purpose_router
from routers.ai_router import router as ai_router
from routers.project_router import router as project_router
from routers.analysis_router import router as analysis_router

app = FastAPI(
    title='AI Feasibility Study & Project Report Generator',
    version='1.0.0'
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(industry_router)
app.include_router(country_router)
app.include_router(purpose_router)
app.include_router(ai_router)
app.include_router(project_router)
app.include_router(analysis_router)

@app.get('/')
def home():
    return {'message': 'Backend is working'}

@app.get('/health')
def health():
    return {'status': 'healthy'}
