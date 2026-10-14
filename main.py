import os
import json
import re
import asyncio
import requests
import time
from collections import defaultdict, deque
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from database import supabase
from models import ContactCreate, AboutCreate, HomeCreate, NavbarCreate, SiteSettingsCreate, ChatRequest, TranslationRequest, ExperienceItem
from uploadthing_client import (
    UploadThingError,
    delete_file_by_url,
    upload_bytes,
    validate_upload,
)

# ==========================================
# APP CONFIGURATION
# ==========================================
app = FastAPI(
    title="Nang Rotha Portfolio API",
    version="1.0.0"
)

_rate_limits: dict[str, deque] = defaultdict(deque)


def enforce_rate_limit(request: Request, bucket: str, limit: int = 12) -> None:
    client = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else "unknown")
    key = f"{bucket}:{client}"
    now = time.monotonic()
    window = _rate_limits[key]
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= limit:
        raise HTTPException(status_code=429, detail="Too many requests. Please wait a minute and try again.")
    window.append(now)

# ==========================================
# CORS CONFIGURATION
# ==========================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "https://porfolio-rotha-v2-2026-backend.onrender.com",
        "https://porfolio-rotha-v2.vercel.app",
        "http://porfolio-rotha-v2-admin.vercel.app",
        "https://porfolio-rotha-v2-admin.vercel.app",
    ],
    allow_origin_regex=r"^https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# CONSTANTS
# ==========================================
async def upload_to_uploadthing(file: UploadFile, *, document: bool = False) -> str:
    content = await file.read()
    content_type = file.content_type or "application/octet-stream"
    validate_upload(content, content_type, document=document)
    uploaded = await asyncio.to_thread(
        upload_bytes,
        file.filename or ("document.pdf" if document else "image.jpg"),
        content,
        content_type,
    )
    return uploaded.url


async def delete_uploadthing_file(url: str | None) -> None:
    if url:
        await asyncio.to_thread(delete_file_by_url, url)


def call_ai(messages: list[dict], *, max_tokens: int = 700) -> str:
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured")
    response = requests.post(
        os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/chat/completions"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": os.getenv("DEEPSEEK_MODEL", "deepseek-flash"),
            "messages": messages,
            "thinking": {"type": "disabled"},
            "max_tokens": max_tokens,
            "stream": False,
        },
        timeout=45,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def get_singleton(table: str) -> dict:
    response = supabase.table(table).select("*").order("id").limit(1).execute()
    return response.data[0] if response.data else {}


def get_singleton_image(table: str, record_id: int, field: str) -> str | None:
    existing = supabase.table(table).select(field).eq("id", record_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail=f"{table.title()} data not found")
    return existing.data[0].get(field)


async def delete_image_if_unreferenced(url: str | None) -> None:
    if not url:
        return
    references = (
        ("about", "profile_image"), ("about", "resume_url"),
        ("home", "profile_image"), ("navbar", "logo_url"), ("projects", "image_url"),
    )
    for table, field in references:
        result = supabase.table(table).select("id").eq(field, url).limit(1).execute()
        if result.data:
            return
    try:
        await delete_uploadthing_file(url)
    except UploadThingError:
        pass

# ==========================================
# 1. PROJECT CRUD
# ==========================================
@app.get("/api/projects")
def get_projects(category: str | None = None):
    try:
        response = supabase.table("projects").select("*").order("id", desc=True).execute()
        data = response.data or []
        for p in data:
            if isinstance(p.get("tech_stack"), str):
                try:
                    p["tech_stack"] = json.loads(p["tech_stack"])
                except:
                    p["tech_stack"] = [t.strip() for t in p["tech_stack"].split(",") if t.strip()]
            elif not isinstance(p.get("tech_stack"), list):
                p["tech_stack"] = []
        
        if category and category.strip() and category.strip().lower() != "all":
            cat_norm = category.strip().lower()
            def match_cat(c):
                c = (c or "").strip().lower()
                if cat_norm in ["website", "web"]:
                    return c in ["website", "web", "web app", "web development"]
                if cat_norm in ["mobile", "app"]:
                    return c in ["mobile", "app", "mobile app", "android", "ios", "flutter"]
                if cat_norm in ["uxui", "uiux", "ux/ui", "ui/ux", "designer", "design"]:
                    return c in ["uxui", "uiux", "ux/ui", "ui/ux", "designer", "design", "graphic"]
                return c == cat_norm
            data = [p for p in data if match_cat(p.get("category"))]
            
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase error: {str(e)}")

@app.get("/api/projects/{id}")
def get_project(id: int):
    try:
        response = supabase.table("projects").select("*").eq("id", id).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Project not found")
        project = response.data[0]
        if isinstance(project.get("tech_stack"), str):
            try:
                project["tech_stack"] = json.loads(project["tech_stack"])
            except:
                project["tech_stack"] = [t.strip() for t in project["tech_stack"].split(",") if t.strip()]
        elif not isinstance(project.get("tech_stack"), list):
            project["tech_stack"] = []
        return project
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase error: {str(e)}")

@app.post("/api/projects/upload-image")
async def upload_project_image(image: UploadFile = File(...)):
    try:
        image_url = await upload_to_uploadthing(image)
        return {"image_url": image_url}
    except UploadThingError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def sync_about_project_count_if_auto():
    try:
        about_res = supabase.table("about").select("id, bio, stats_completed_projects").execute()
        if not about_res.data:
            return
        about_row = about_res.data[0]
        unpacked = unpack_about_metadata(dict(about_row))
        if unpacked.get("stats_completed_projects_auto"):
            proj_res = supabase.table("projects").select("id", count="exact").execute()
            real_count = proj_res.count if proj_res.count is not None else len(proj_res.data or [])
            if real_count != about_row.get("stats_completed_projects"):
                supabase.table("about").update({"stats_completed_projects": real_count}).eq("id", about_row["id"]).execute()
    except Exception as e:
        print(f"Error syncing about project count: {e}")

@app.post("/api/projects")
async def create_project(
    title: str = Form(...),
    description: str = Form(...),
    link: str = Form(""),
    category: str = Form("website"),
    tech_stack: str = Form("[]"),
    demo_link: str = Form(""),
    code_link: str = Form(""),
    rating: float = Form(0),
    status: str = Form("Active"),
    image: UploadFile | None = File(None),
):
    image_url = None
    try:
        if image and image.filename:
            image_url = await upload_to_uploadthing(image)
        try:
            tech_list = json.loads(tech_stack) if tech_stack else []
        except (json.JSONDecodeError, TypeError):
            tech_list = []
        data = {
            "title": title,
            "description": description,
            "link": link or None,
            "category": (category or "website").strip().lower(),
            "tech_stack": tech_list,
            "demo_link": demo_link or None,
            "code_link": code_link or None,
            "rating": rating,
            "status": status,
            "image_url": image_url,
        }
        response = supabase.table("projects").insert(data).execute()
        sync_about_project_count_if_auto()
        return response.data
    except UploadThingError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        if image_url:
            try:
                await delete_uploadthing_file(image_url)
            except UploadThingError:
                pass
        raise HTTPException(status_code=500, detail=f"Supabase error: {str(e)}")

@app.put("/api/projects/{id}")
async def update_project(
    id: int,
    title: str = Form(...),
    description: str = Form(...),
    link: str = Form(""),
    category: str = Form("website"),
    tech_stack: str = Form("[]"),
    demo_link: str = Form(""),
    code_link: str = Form(""),
    rating: float = Form(0),
    status: str = Form("Active"),
    image: UploadFile | None = File(None),
):
    new_image_url = None
    try:
        check = supabase.table("projects").select("id,image_url").eq("id", id).execute()
        if not check.data:
            raise HTTPException(status_code=404, detail="Project not found")
        old_image_url = check.data[0].get("image_url")
        if image and image.filename:
            new_image_url = await upload_to_uploadthing(image)
        try:
            tech_list = json.loads(tech_stack) if tech_stack else []
        except (json.JSONDecodeError, TypeError):
            tech_list = []
        data = {
            "title": title,
            "description": description,
            "link": link or None,
            "category": (category or "website").strip().lower(),
            "tech_stack": tech_list,
            "demo_link": demo_link or None,
            "code_link": code_link or None,
            "rating": rating,
            "status": status,
            "image_url": new_image_url or old_image_url,
        }
        response = supabase.table("projects").update(data).eq("id", id).execute()
        if new_image_url and old_image_url:
            await delete_image_if_unreferenced(old_image_url)
        return response.data
    except UploadThingError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        if new_image_url:
            try:
                await delete_uploadthing_file(new_image_url)
            except UploadThingError:
                pass
        raise HTTPException(status_code=500, detail=f"Supabase error: {str(e)}")

@app.delete("/api/projects/{id}")
async def delete_project(id: int):
    try:
        check = supabase.table("projects").select("image_url").eq("id", id).execute()
        if not check.data:
            raise HTTPException(status_code=404, detail="Project not found")
        old_url = check.data[0].get("image_url")
        supabase.table("projects").delete().eq("id", id).execute()
        sync_about_project_count_if_auto()
        await delete_image_if_unreferenced(old_url)
        return {"message": "Project deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase error: {str(e)}")


# ==========================================
# 2. CONTACT
# ==========================================
@app.get("/api/contacts")
def get_contacts():
    try:
        response = supabase.table("contacts").select("*").execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase error: {str(e)}")

@app.post("/api/contacts")
def create_contact(contact: ContactCreate):
    try:
        response = supabase.table("contacts").insert(contact.model_dump()).execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase error: {str(e)}")

@app.get("/api/contacts/{id}")
def get_contact_by_id(id: int):
    try:
        response = supabase.table("contacts").select("*").eq("id", id).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Contact not found")
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase error: {str(e)}")

@app.put("/api/contacts/{id}")
def update_contact(id: int, contact: ContactCreate):
    try:
        response = supabase.table("contacts").update(contact.model_dump()).eq("id", id).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Contact not found")
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase error: {str(e)}")

@app.delete("/api/contacts/{id}")
def delete_contact(id: int):
    try:
        response = supabase.table("contacts").delete().eq("id", id).execute()
        return {"message": "Contact deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase error: {str(e)}")


# ==========================================
# 3. NAVBAR CRUD (INDEPENDENT DATA)
# ==========================================
@app.get("/api/navbar")
def get_navbar():
    try:
        return get_singleton("navbar")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase error: {str(e)}")


@app.post("/api/navbar")
def create_navbar(navbar: NavbarCreate):
    try:
        if get_singleton("navbar"):
            raise HTTPException(status_code=409, detail="Navbar data already exists")
        return supabase.table("navbar").insert(navbar.model_dump()).execute().data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase error: {str(e)}")


@app.put("/api/navbar/{id}")
async def update_navbar(id: int, navbar: NavbarCreate):
    try:
        old_url = get_singleton_image("navbar", id, "logo_url")
        response = supabase.table("navbar").update(navbar.model_dump()).eq("id", id).execute().data
        if old_url != navbar.logo_url:
            await delete_image_if_unreferenced(old_url)
        return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase error: {str(e)}")


@app.delete("/api/navbar/{id}")
async def delete_navbar(id: int):
    try:
        existing = supabase.table("navbar").select("logo_url").eq("id", id).execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Navbar data not found")
        supabase.table("navbar").delete().eq("id", id).execute()
        await delete_image_if_unreferenced(existing.data[0].get("logo_url"))
        return {"message": "Navbar data deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase error: {str(e)}")


@app.post("/api/navbar/upload-logo")
async def upload_navbar_logo(image: UploadFile = File(...)):
    try:
        return {"logo_url": await upload_to_uploadthing(image)}
    except UploadThingError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# 4. HOME CRUD (INDEPENDENT DATA)
# ==========================================
@app.get("/api/home")
def get_home():
    try:
        data = get_singleton("home")
        if data and not isinstance(data.get("tech_stack"), list):
            try:
                data["tech_stack"] = json.loads(data.get("tech_stack") or "[]")
            except (json.JSONDecodeError, TypeError):
                data["tech_stack"] = []
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase error: {str(e)}")


@app.post("/api/home")
def create_home(home: HomeCreate):
    try:
        if get_singleton("home"):
            raise HTTPException(status_code=409, detail="Home data already exists")
        return supabase.table("home").insert(home.model_dump()).execute().data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase error: {str(e)}")


@app.put("/api/home/{id}")
async def update_home(id: int, home: HomeCreate):
    try:
        old_url = get_singleton_image("home", id, "profile_image")
        response = supabase.table("home").update(home.model_dump()).eq("id", id).execute().data
        if old_url != home.profile_image:
            await delete_image_if_unreferenced(old_url)
        return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase error: {str(e)}")


@app.delete("/api/home/{id}")
async def delete_home(id: int):
    try:
        existing = supabase.table("home").select("profile_image").eq("id", id).execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Home data not found")
        supabase.table("home").delete().eq("id", id).execute()
        await delete_image_if_unreferenced(existing.data[0].get("profile_image"))
        return {"message": "Home data deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase error: {str(e)}")


@app.post("/api/home/upload-image")
async def upload_home_image(image: UploadFile = File(...)):
    try:
        return {"image_url": await upload_to_uploadthing(image)}
    except UploadThingError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# 5. SITE SETTINGS / MAINTENANCE CRUD
# ==========================================
@app.get("/api/site-settings")
def get_site_settings():
    try:
        return get_singleton("site_settings")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase error: {str(e)}")


@app.post("/api/site-settings")
def create_site_settings(settings: SiteSettingsCreate):
    try:
        if get_singleton("site_settings"):
            raise HTTPException(status_code=409, detail="Site settings already exist")
        return supabase.table("site_settings").insert(settings.model_dump()).execute().data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase error: {str(e)}")


@app.put("/api/site-settings/{id}")
def update_site_settings(id: int, settings: SiteSettingsCreate):
    try:
        existing = supabase.table("site_settings").select("id").eq("id", id).execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Site settings not found")
        return supabase.table("site_settings").update(settings.model_dump()).eq("id", id).execute().data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase error: {str(e)}")


@app.delete("/api/site-settings/{id}")
def delete_site_settings(id: int):
    try:
        existing = supabase.table("site_settings").select("id").eq("id", id).execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Site settings not found")
        supabase.table("site_settings").delete().eq("id", id).execute()
        return {"message": "Site settings deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase error: {str(e)}")


# ==========================================
# 6. ABOUT (PROFILE) CRUD
# ==========================================
def unpack_about_metadata(data: dict) -> dict:
    if not data:
        return data
    bio = data.get('bio') or ''
    meta_match = re.search(r'<!--\s*META:({.*?})\s*-->', bio, re.DOTALL)
    experience = []
    cover_letter_url = None
    cover_letter_text = None
    contact_meta = {}
    if meta_match:
        try:
            meta_json = json.loads(meta_match.group(1))
            experience = meta_json.get('experience', [])
            cover_letter_url = meta_json.get('cover_letter_url')
            cover_letter_text = meta_json.get('cover_letter_text')
            contact_meta = {
                'phone': meta_json.get('phone', ''),
                'telegram': meta_json.get('telegram', ''),
                'availability_status': meta_json.get('availability_status', 'Available for projects'),
                'reply_time': meta_json.get('reply_time', 'ឆ្លើយតបក្នុងរយៈពេល ២៤ ម៉ោង'),
                'contact_title_km': meta_json.get('contact_title_km', 'ទាក់ទងខ្ញុំ'),
                'contact_title_en': meta_json.get('contact_title_en', 'Contact Me'),
                'contact_subtitle_km': meta_json.get('contact_subtitle_km', 'មានគម្រោងក្នុងចិត្ត? ចូរទម្លាក់សារមកខ្ញុំ... ខ្ញុំនឹងឆ្លើយតបអ្នកវិញក្នុងរយៈពេល ២៤ ម៉ោង។'),
                'contact_subtitle_en': meta_json.get('contact_subtitle_en', 'Have a project in mind? Drop me a message and I will reply within 24 hours.'),
            }
            clean_bio = bio[:meta_match.start()] + bio[meta_match.end():]
            data['bio'] = clean_bio.strip()
            data['stats_completed_projects_auto'] = meta_json.get('stats_completed_projects_auto', False)
        except Exception as e:
            print(f"Failed to parse bio metadata: {e}")
    data['experience'] = experience if isinstance(experience, list) else []
    data['cover_letter_url'] = cover_letter_url
    data['cover_letter_text'] = cover_letter_text
    data['stats_completed_projects_auto'] = data.get('stats_completed_projects_auto', False)
    for k, v in contact_meta.items():
        if k not in data or data[k] is None:
            data[k] = v
    if not data.get('availability_status'):
        data['availability_status'] = 'Available for projects'
    return data

def prepare_about_save_data(about: AboutCreate) -> dict:
    data = about.model_dump()
    exp = data.pop('experience', []) or []
    cl_url = data.pop('cover_letter_url', None)
    cl_text = data.pop('cover_letter_text', None)
    stats_completed_projects_auto = data.pop('stats_completed_projects_auto', False)

    # If auto sync projects is enabled, calculate real projects count from Supabase
    if stats_completed_projects_auto:
        try:
            proj_res = supabase.table("projects").select("id", count="exact").execute()
            real_count = proj_res.count if proj_res.count is not None else len(proj_res.data or [])
            if real_count > 0:
                data['stats_completed_projects'] = real_count
        except Exception as pe:
            print(f"Failed to auto-count projects on save: {pe}")

    # Extract contact meta fields to avoid Supabase unknown column errors
    phone = data.pop('phone', None)
    telegram = data.pop('telegram', None)
    availability_status = data.pop('availability_status', None)
    reply_time = data.pop('reply_time', None)
    contact_title_km = data.pop('contact_title_km', None)
    contact_title_en = data.pop('contact_title_en', None)
    contact_subtitle_km = data.pop('contact_subtitle_km', None)
    contact_subtitle_en = data.pop('contact_subtitle_en', None)

    bio = data.get('bio') or ''
    # Strip any existing metadata block
    bio = re.sub(r'<!--\s*META:({.*?})\s*-->', '', bio, flags=re.DOTALL).strip()
    
    meta_dict = {
        'experience': [e.model_dump() if hasattr(e, 'model_dump') else e for e in exp],
        'cover_letter_url': cl_url,
        'cover_letter_text': cl_text,
        'phone': phone,
        'telegram': telegram,
        'availability_status': availability_status,
        'reply_time': reply_time,
        'contact_title_km': contact_title_km,
        'contact_title_en': contact_title_en,
        'contact_subtitle_km': contact_subtitle_km,
        'contact_subtitle_en': contact_subtitle_en,
        'stats_completed_projects_auto': bool(stats_completed_projects_auto),
    }
    meta_str = json.dumps(meta_dict, ensure_ascii=False)
    bio = f"{bio}\n\n<!-- META:{meta_str} -->"
    data['bio'] = bio
    data['skills'] = json.dumps([s.model_dump() if hasattr(s, 'model_dump') else s for s in about.skills])
    data['education'] = json.dumps([e.model_dump() if hasattr(e, 'model_dump') else e for e in about.education])
    return data

@app.get("/api/about")
def get_about():
    try:
        response = supabase.table("about").select("*").execute()
        if not response.data:
            return {}
        
        data = response.data[0]
        
        if isinstance(data.get('skills'), str):
            try:
                data['skills'] = json.loads(data['skills'])
            except:
                data['skills'] = []
        
        if isinstance(data.get('education'), str):
            try:
                data['education'] = json.loads(data['education'])
            except:
                data['education'] = []
                
        data = unpack_about_metadata(data)

        # Count actual projects in database
        real_projects_count = 0
        try:
            proj_res = supabase.table("projects").select("id", count="exact").execute()
            real_projects_count = proj_res.count if proj_res.count is not None else len(proj_res.data or [])
        except Exception as pe:
            print(f"Failed to count projects in get_about: {pe}")

        data['auto_completed_projects'] = real_projects_count

        # If user enabled auto sync OR if stats_completed_projects is 0/empty, automatically provide real_projects_count
        if data.get('stats_completed_projects_auto') or not data.get('stats_completed_projects'):
            if real_projects_count > 0:
                data['stats_completed_projects'] = real_projects_count

        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase error: {str(e)}")

@app.post("/api/about")
async def create_about(about: AboutCreate):
    try:
        data = prepare_about_save_data(about)
        response = supabase.table("about").insert(data).execute()
        if response.data:
            return unpack_about_metadata(response.data[0])
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase error: {str(e)}")

@app.put("/api/about/{id}")
async def update_about(id: int, about: AboutCreate):
    try:
        existing = supabase.table("about").select("profile_image,resume_url,bio").eq("id", id).execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Profile not found")
        old_profile_image = existing.data[0].get("profile_image")
        old_resume_url = existing.data[0].get("resume_url")
        old_meta = unpack_about_metadata(dict(existing.data[0]))
        old_cover_letter_url = old_meta.get("cover_letter_url")

        data = prepare_about_save_data(about)
        response = supabase.table("about").update(data).eq("id", id).execute()
        
        replaced_urls = []
        if old_profile_image and old_profile_image != about.profile_image:
            replaced_urls.append(old_profile_image)
        if old_resume_url and old_resume_url != about.resume_url:
            replaced_urls.append(old_resume_url)
        if old_cover_letter_url and old_cover_letter_url != about.cover_letter_url:
            replaced_urls.append(old_cover_letter_url)
        for old_url in replaced_urls:
            await delete_image_if_unreferenced(old_url)
            
        if response.data:
            return unpack_about_metadata(response.data[0])
        return response.data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase error: {str(e)}")


# ==========================================
# 4. UPLOAD APIs
# ==========================================
@app.post("/api/about/upload-image")
async def upload_about_image(image: UploadFile = File(...)):
    try:
        image_url = await upload_to_uploadthing(image)
        return {"image_url": image_url}
    except UploadThingError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/about/upload-cv")
async def upload_cv(cv: UploadFile = File(...)):
    try:
        cv_url = await upload_to_uploadthing(cv, document=True)
        return {"cv_url": cv_url, "resume_url": cv_url}
    except UploadThingError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/about/upload-cover-letter")
async def upload_cover_letter(file: UploadFile = File(...)):
    try:
        url = await upload_to_uploadthing(file, document=True)
        return {"cover_letter_url": url}
    except UploadThingError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# 5. AI CHATBOT API
# ==========================================
@app.post("/api/chat")
async def chat_with_bot(payload: ChatRequest, request: Request):
    enforce_rate_limit(request, "chat", 12)
    if not payload.message.strip() or len(payload.message) > 2000:
        raise HTTPException(status_code=400, detail="Message must contain 1–2000 characters")
    try:
        about_res = supabase.table("about").select("*").execute()
        home_res = supabase.table("home").select("*").execute()
        navbar_res = supabase.table("navbar").select("*").execute()
        projects_res = supabase.table("projects").select("*").execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase error: {str(e)}")
    
    context = {
        "profile": about_res.data[0] if about_res.data else {},
        "home": home_res.data[0] if home_res.data else {},
        "navbar": navbar_res.data[0] if navbar_res.data else {},
        "projects": (projects_res.data or [])[:20],
    }
    language_name = "Khmer" if payload.language == "km" else "English"
    system_prompt = (
        "You are Nang Rotha's concise, friendly portfolio assistant. "
        f"Always answer in {language_name}. Use only the supplied portfolio data for personal facts; "
        "if information is missing, say so and suggest the Contact page. Never invent credentials, clients, or experience. "
        f"PORTFOLIO DATA: {json.dumps(context, ensure_ascii=False, default=str)}"
    )
    history = [m.model_dump() for m in payload.history[-8:] if m.role in {"user", "assistant"}]
    try:
        response_text = await asyncio.to_thread(
            call_ai,
            [{"role": "system", "content": system_prompt}, *history, {"role": "user", "content": payload.message}],
        )
        return {"response": response_text, "provider": "deepseek"}
    except (requests.RequestException, RuntimeError, KeyError, IndexError, TypeError, ValueError) as e:
        raise HTTPException(status_code=503, detail=f"AI assistant is temporarily unavailable: {str(e)[:160]}")


@app.post("/api/translate")
async def translate_text(payload: TranslationRequest, request: Request):
    enforce_rate_limit(request, "translate", 30)
    if payload.target_language not in {"km", "en"}:
        raise HTTPException(status_code=400, detail="target_language must be 'km' or 'en'")
    if not payload.text.strip() or len(payload.text) > 5000:
        raise HTTPException(status_code=400, detail="Text must contain 1–5000 characters")
    target = "natural Khmer" if payload.target_language == "km" else "natural English"
    try:
        translated = await asyncio.to_thread(
            call_ai,
            [
                {"role": "system", "content": f"Translate the user text into {target}. Preserve names, URLs, code, formatting, and meaning. Return only the translation."},
                {"role": "user", "content": payload.text},
            ],
            max_tokens=1200,
        )
        return {"translation": translated, "language": payload.target_language}
    except (requests.RequestException, RuntimeError, KeyError, IndexError, TypeError, ValueError) as e:
        raise HTTPException(status_code=503, detail=f"Translation is temporarily unavailable: {str(e)[:160]}")


# ==========================================
# 6. ROOT
# ==========================================
@app.get("/")
def root():
    return {"message": "Nang Rotha Portfolio API is running!"}


# ==========================================
# 7. FOR LOCAL DEVELOPMENT (មិនប្រើលើ Vercel)
# ==========================================
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
