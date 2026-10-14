from pydantic import BaseModel, Field
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

class ExperienceItem(BaseModel):
    company: str
    role: str
    period: str
    description: str
    badges: List[str] = []

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
    experience: List[ExperienceItem] = []
    cover_letter_url: Optional[str] = None
    cover_letter_text: Optional[str] = None

class NavbarCreate(BaseModel):
    brand_name: str
    logo_url: Optional[str] = None
    home_label_km: str = "ទំព័រដើម"
    home_label_en: str = "Home"
    about_label_km: str = "អំពីខ្ញុំ"
    about_label_en: str = "About"
    projects_label_km: str = "គម្រោង"
    projects_label_en: str = "Projects"
    contact_label_km: str = "ទាក់ទង"
    contact_label_en: str = "Contact"

class HomeCreate(BaseModel):
    display_name: str
    role: Optional[str] = None
    profile_image: Optional[str] = None
    availability_text: Optional[str] = None
    eyebrow: Optional[str] = None
    headline: Optional[str] = None
    description: Optional[str] = None
    primary_button_text: Optional[str] = None
    secondary_button_text: Optional[str] = None
    tech_stack: List[str] = Field(default_factory=list)
    metric_label: Optional[str] = None
    metric_value: Optional[str] = None

class SiteSettingsCreate(BaseModel):
    maintenance_enabled: bool = False
    maintenance_title: str = "Portfolio is being improved"
    maintenance_message: str = "We are building something better. Please check back soon."
    expected_back_at: Optional[str] = None

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    language: str = "km"
    history: List[ChatMessage] = Field(default_factory=list)

class TranslationRequest(BaseModel):
    text: str
    target_language: str
