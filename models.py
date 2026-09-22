from pydantic import BaseModel
from typing import Optional, List

# Schema for creating/updating a Project
class ProjectCreate(BaseModel):
    title: str
    description: str
    image_url: Optional[str] = None
    link: Optional[str] = None
    category: Optional[str] = "website"
    tech_stack: Optional[List[str]] = []
    demo_link: Optional[str] = None
    code_link: Optional[str] = None
    rating: Optional[float] = 0.0
    status: Optional[str] = "Active"

# Schema for Contact messages
class ContactCreate(BaseModel):
    name: str
    email: str
    message: str

class SkillItem(BaseModel):
    name: str
    percent: int

class EducationItem(BaseModel):
    year: str
    degree: str
    school: str
    description: str
    badges: List[str]

class AboutCreate(BaseModel):
    full_name: str
    job_title: Optional[str] = None
    profile_image: Optional[str] = None
    email: Optional[str] = None
    location: Optional[str] = None
    languages: Optional[str] = None
    bio: Optional[str] = None
    resume_url: Optional[str] = None
    stats_completed_projects: Optional[int] = 0
    stats_years_experience: Optional[int] = 0
    stats_happy_clients: Optional[int] = 0
    skills: List[SkillItem] = []
    education: List[EducationItem] = []
    quote: Optional[str] = None