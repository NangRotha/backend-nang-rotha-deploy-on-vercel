from mangum import Mangum
from main import app

# Vercel handler
handler = Mangum(app)