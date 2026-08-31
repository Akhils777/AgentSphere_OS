import os
import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    reload_flag = os.getenv("ENVIRONMENT", "development").lower() == "development"
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=reload_flag)

