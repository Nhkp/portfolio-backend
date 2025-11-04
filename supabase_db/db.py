import base64
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()


url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)


pdfs = {
    "english_cv": {
        "path" : "/app/local_data/English_CV_2025.pdf",
        "table_name": "cv",
    },
    "hyperparameter_article": {
        "path": "/app/local_data/hyperparameters_analysis.pdf",
        "table_name": "papers",
    },
    "openradioss_article": {
        "path": "/app/local_data/openradioss_article_v2.pdf",
        "table_name": "papers",
    },
}

def store_pdf(table_name: str = "cv", pdf_path: str = "data/English_CV_2025.pdf"):
    if os.path.exists(pdf_path):
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
    pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

    data = supabase.table(table_name).insert({"filename": os.path.basename(pdf_path), "filedata": pdf_base64}).execute()

    return data

def load_pdf(table_name: str = "cv", filename: str = None):
    data = supabase.table(table_name).select("*").eq("filename", filename).execute()
    if len(data.data) == 0:
        return None
    record = data.data[0]
    record["filedata"] = base64.b64decode(record["filedata"].encode("utf-8"))
    return record

def is_pdf_already_stored(table_name: str = "cv", filename: str = None):
    data = supabase.table(table_name).select("*").eq("filename", filename).execute()
    return len(data.data) > 0


if __name__ == "__main__":
    pdf_path ="/home/clement/projects/side_project/data/English_CV_2025.pdf"
    if not is_cv_already_stored():
        print("Storing CV into Supabase...")
        store_cv(pdf_path)
    else:
        print("CV already exists in Supabase, skipping store.")

    cv = load_cv()
    with open("./test_cv.pdf", "wb") as f:
        f.write(cv["filedata"])
    print(f"Loaded CV: {cv["filename"]}")
