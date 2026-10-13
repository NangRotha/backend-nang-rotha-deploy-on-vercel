import os
import json
import asyncio
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from database import supabase
from models import ContactCreate, AboutCreate
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

# ==========================================
# 1. PROJECT CRUD
# ==========================================
@app.get("/api/projects")
def get_projects():
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
            "category": category,
            "tech_stack": tech_list,
            "demo_link": demo_link or None,
            "code_link": code_link or None,
            "rating": rating,
            "status": status,
            "image_url": image_url,
        }
        response = supabase.table("projects").insert(data).execute()
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
            "category": category,
            "tech_stack": tech_list,
            "demo_link": demo_link or None,
            "code_link": code_link or None,
            "rating": rating,
            "status": status,
            "image_url": new_image_url or old_image_url,
        }
        response = supabase.table("projects").update(data).eq("id", id).execute()
        if new_image_url and old_image_url:
            try:
                await delete_uploadthing_file(old_image_url)
            except UploadThingError:
                pass
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
        try:
            await delete_uploadthing_file(old_url)
        except UploadThingError:
            pass
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


# ==========================================
# 3. ABOUT (PROFILE) CRUD
# ==========================================
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
                
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase error: {str(e)}")

@app.post("/api/about")
async def create_about(about: AboutCreate):
    try:
        data = about.model_dump()
        data['skills'] = json.dumps([s.model_dump() for s in about.skills])
        data['education'] = json.dumps([e.model_dump() for e in about.education])
        response = supabase.table("about").insert(data).execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase error: {str(e)}")

@app.put("/api/about/{id}")
async def update_about(id: int, about: AboutCreate):
    try:
        existing = supabase.table("about").select("profile_image,resume_url").eq("id", id).execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Profile not found")
        old_profile_image = existing.data[0].get("profile_image")
        old_resume_url = existing.data[0].get("resume_url")
        data = about.model_dump()
        data['skills'] = json.dumps([s.model_dump() for s in about.skills])
        data['education'] = json.dumps([e.model_dump() for e in about.education])
        response = supabase.table("about").update(data).eq("id", id).execute()
        replaced_urls = []
        if old_profile_image and old_profile_image != about.profile_image:
            replaced_urls.append(old_profile_image)
        if old_resume_url and old_resume_url != about.resume_url:
            replaced_urls.append(old_resume_url)
        for old_url in replaced_urls:
            try:
                await delete_uploadthing_file(old_url)
            except UploadThingError:
                pass
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
        return {"cv_url": cv_url}
    except UploadThingError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# 5. AI CHATBOT API
# ==========================================
@app.post("/api/chat")
async def chat_with_bot(request: dict):
    user_input = request.get("message", "").lower()
    
    try:
        about_res = supabase.table("about").select("*").execute()
        projects_res = supabase.table("projects").select("*").execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase error: {str(e)}")
    
    about_data = about_res.data[0] if about_res.data else {}
    projects = projects_res.data if projects_res.data else []

    skills = []
    if about_data.get('skills'):
        if isinstance(about_data['skills'], str):
            try:
                skills = json.loads(about_data['skills'])
            except:
                skills = []
        elif isinstance(about_data['skills'], list):
            skills = about_data['skills']

    response_text = "សូមទោស ខ្ញុំមិនទាន់មានព័ត៌មានអំពីសំណួរនេះនៅឡើយទេ។ សូមទាក់ទងមកខ្ញុំដោយផ្ទាល់នៅលើទំព័រ Contact សម្រាប់សំណួរកាន់តែលម្អិត។"

    if any(word in user_input for word in ["ឈ្មោះ", "name", "who"]):
        response_text = f"ឈ្មោះរបស់ខ្ញុំគឺ **{about_data.get('full_name', 'Nang Rotha')}**។ ខ្ញុំជា {about_data.get('job_title', 'Developer')}។"
        
    elif any(word in user_input for word in ["ជំនាញ", "skill", "know"]):
        if skills:
            skill_names = ", ".join([s['name'] for s in skills])
            response_text = f"ជំនាញដែលខ្ញុំពូកែមានដូចជា៖ **{skill_names}**។"
        else:
            response_text = "បច្ចុប្បន្នខ្ញុំមិនទាន់បានកត់ត្រាជំនាញរបស់ខ្ញុំនៅឡើយទេ។"

    elif any(word in user_input for word in ["គម្រោង", "project", "portfolio", "work"]):
        if projects:
            titles = ", ".join([p['title'] for p in projects[:5]])
            response_text = f"គម្រោងសំខាន់ៗដែលខ្ញុំបានធ្វើរួចមានដូចជា៖ **{titles}**។ អ្នកអាចចូលទៅមើលគម្រោងទាំងអស់បាននៅក្នុងទំព័រ Projects។"
        else:
            response_text = "បច្ចុប្បន្នខ្ញុំមិនទាន់មានគម្រោងដែលបានចុះផ្សាយនៅឡើយទេ។"

    elif any(word in user_input for word in ["ទីតាំង", "location", "live", "address"]):
        response_text = f"ខ្ញុំរស់នៅ **{about_data.get('location', 'Cambodia')}**។"

    elif any(word in user_input for word in ["ទាក់ទង", "contact", "email", "phone"]):
        response_text = f"អ្នកអាចទាក់ទងមកខ្ញុំតាមរយៈអ៊ីមែល៖ **{about_data.get('email', 'N/A')}** ឬតាមរយៈទំព័រ Contact របស់គេហទំព័រ។"

    elif any(word in user_input for word in ["សួស្តី", "hi", "hello", "good morning"]):
        response_text = f"សួស្តី! រីករាយដែលបានស្គាល់អ្នក។ ខ្ញុំគឺ {about_data.get('full_name', 'Nang Rotha')}។ តើខ្ញុំអាចជួយអ្នកយ៉ាងដូចម្តេចខ្លះ?"

    return {"response": response_text}


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
