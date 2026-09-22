import os
import uuid
import json
from fastapi import FastAPI, HTTPException, UploadFile, File, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from database import supabase
from models import ProjectCreate, ContactCreate, AboutCreate

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
BUCKET_NAME = "portfolio-images"
CV_BUCKET_NAME = "cv-files"

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
        file_extension = image.filename.split(".")[-1]
        unique_filename = f"project_{uuid.uuid4()}.{file_extension}"
        file_content = await image.read()
        supabase.storage.from_(BUCKET_NAME).upload(unique_filename, file_content, {"content-type": image.content_type})
        image_url = supabase.storage.from_(BUCKET_NAME).get_public_url(unique_filename)
        return {"image_url": image_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/projects")
async def create_project(request: Request):
    try:
        content_type = request.headers.get("content-type", "")
        if content_type.startswith("multipart/form-data") or content_type.startswith("application/x-www-form-urlencoded"):
            form_data = await request.form()
            title = form_data.get("title")
            description = form_data.get("description")
            link = form_data.get("link") or None
            category = form_data.get("category", "website")
            tech_stack_raw = form_data.get("tech_stack")
            demo_link = form_data.get("demo_link") or None
            code_link = form_data.get("code_link") or None
            rating_raw = form_data.get("rating", 0)
            status = form_data.get("status", "Active")
            image_file = form_data.get("image")

            tech_stack = []
            if tech_stack_raw:
                try:
                    tech_stack = json.loads(tech_stack_raw) if isinstance(tech_stack_raw, str) else tech_stack_raw
                except:
                    tech_stack = [t.strip() for t in str(tech_stack_raw).split(",") if t.strip()]

            try:
                rating = float(rating_raw) if rating_raw else 0.0
            except (ValueError, TypeError):
                rating = 0.0

            image_url = None
            if image_file and hasattr(image_file, "filename") and image_file.filename:
                file_extension = image_file.filename.split(".")[-1]
                unique_filename = f"project_{uuid.uuid4()}.{file_extension}"
                file_content = await image_file.read()
                supabase.storage.from_(BUCKET_NAME).upload(
                    unique_filename,
                    file_content,
                    {"content-type": getattr(image_file, "content_type", "image/jpeg")}
                )
                image_url = supabase.storage.from_(BUCKET_NAME).get_public_url(unique_filename)

            project_dict = {
                "title": title,
                "description": description,
                "category": category,
                "tech_stack": tech_stack,
                "status": status,
                "rating": rating
            }
            if link:
                project_dict["link"] = link
            if demo_link:
                project_dict["demo_link"] = demo_link
            if code_link:
                project_dict["code_link"] = code_link
            if image_url:
                project_dict["image_url"] = image_url

            response = supabase.table("projects").insert(project_dict).execute()
            return response.data
        else:
            body = await request.json()
            project = ProjectCreate(**body)
            data = project.model_dump()
            response = supabase.table("projects").insert(data).execute()
            return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating project: {str(e)}")

@app.put("/api/projects/{id}")
async def update_project(id: int, request: Request):
    try:
        check = supabase.table("projects").select("*").eq("id", id).execute()
        if not check.data:
            raise HTTPException(status_code=404, detail="Project not found")
        existing = check.data[0]

        content_type = request.headers.get("content-type", "")
        if content_type.startswith("multipart/form-data") or content_type.startswith("application/x-www-form-urlencoded"):
            form_data = await request.form()
            title = form_data.get("title", existing.get("title"))
            description = form_data.get("description", existing.get("description"))
            link = form_data.get("link") if "link" in form_data else existing.get("link")
            category = form_data.get("category", existing.get("category", "website"))
            tech_stack_raw = form_data.get("tech_stack")
            demo_link = form_data.get("demo_link") if "demo_link" in form_data else existing.get("demo_link")
            code_link = form_data.get("code_link") if "code_link" in form_data else existing.get("code_link")
            rating_raw = form_data.get("rating", existing.get("rating", 0))
            status = form_data.get("status", existing.get("status", "Active"))
            image_file = form_data.get("image")

            tech_stack = existing.get("tech_stack", [])
            if tech_stack_raw is not None:
                try:
                    tech_stack = json.loads(tech_stack_raw) if isinstance(tech_stack_raw, str) else tech_stack_raw
                except:
                    tech_stack = [t.strip() for t in str(tech_stack_raw).split(",") if t.strip()]

            try:
                rating = float(rating_raw) if rating_raw is not None else 0.0
            except (ValueError, TypeError):
                rating = 0.0

            project_dict = {
                "title": title,
                "description": description,
                "category": category,
                "tech_stack": tech_stack,
                "status": status,
                "rating": rating,
                "link": link or None,
                "demo_link": demo_link or None,
                "code_link": code_link or None
            }

            if image_file and hasattr(image_file, "filename") and image_file.filename:
                file_extension = image_file.filename.split(".")[-1]
                unique_filename = f"project_{uuid.uuid4()}.{file_extension}"
                file_content = await image_file.read()
                supabase.storage.from_(BUCKET_NAME).upload(
                    unique_filename,
                    file_content,
                    {"content-type": getattr(image_file, "content_type", "image/jpeg")}
                )
                new_image_url = supabase.storage.from_(BUCKET_NAME).get_public_url(unique_filename)
                project_dict["image_url"] = new_image_url

                if existing.get("image_url"):
                    try:
                        old_filename = existing["image_url"].split("/")[-1].split("?")[0]
                        supabase.storage.from_(BUCKET_NAME).remove([old_filename])
                    except:
                        pass

            response = supabase.table("projects").update(project_dict).eq("id", id).execute()
            return response.data
        else:
            body = await request.json()
            project = ProjectCreate(**body)
            data = project.model_dump()
            response = supabase.table("projects").update(data).eq("id", id).execute()
            return response.data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating project: {str(e)}")

@app.delete("/api/projects/{id}")
def delete_project(id: int):
    try:
        check = supabase.table("projects").select("image_url").eq("id", id).execute()
        if check.data and check.data[0]["image_url"]:
            old_url = check.data[0]["image_url"]
            try:
                old_filename = old_url.split("/")[-1].split("?")[0]
                supabase.storage.from_(BUCKET_NAME).remove([old_filename])
            except:
                pass
        response = supabase.table("projects").delete().eq("id", id).execute()
        return {"message": "Project deleted successfully"}
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
        data = about.model_dump()
        data['skills'] = json.dumps([s.model_dump() for s in about.skills])
        data['education'] = json.dumps([e.model_dump() for e in about.education])
        response = supabase.table("about").update(data).eq("id", id).execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase error: {str(e)}")


# ==========================================
# 4. UPLOAD APIs
# ==========================================
@app.post("/api/about/upload-image")
async def upload_about_image(image: UploadFile = File(...)):
    try:
        file_extension = image.filename.split(".")[-1]
        unique_filename = f"profile_{uuid.uuid4()}.{file_extension}"
        file_content = await image.read()
        supabase.storage.from_(BUCKET_NAME).upload(unique_filename, file_content, {"content-type": image.content_type})
        image_url = supabase.storage.from_(BUCKET_NAME).get_public_url(unique_filename)
        return {"image_url": image_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/about/upload-cv")
async def upload_cv(cv: UploadFile = File(...)):
    try:
        file_extension = cv.filename.split(".")[-1]
        unique_filename = f"cv_{uuid.uuid4()}.{file_extension}"
        file_content = await cv.read()
        supabase.storage.from_(CV_BUCKET_NAME).upload(unique_filename, file_content, {"content-type": cv.content_type})
        cv_url = supabase.storage.from_(CV_BUCKET_NAME).get_public_url(unique_filename)
        return {"cv_url": cv_url}
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