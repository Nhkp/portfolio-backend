import base64
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()


url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)


# pdf_path = "data/English_CV_2025.pdf"

def store_cv(pdf_path: str = "data/English_CV_2025.pdf"):
    if os.path.exists(pdf_path):
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
    pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

    data = supabase.table("cv").insert({"id": 0, "filename": "English_CV_2025.pdf", "filedata": pdf_base64}).execute()

    return data
    # Assert we pulled real data.
    assert len(data.data) > 0

def load_cv():
    data = supabase.table("cv").select("*").eq("id", 0).execute()
    if len(data.data) == 0:
        return None
    record = data.data[0]
    print(type(record["filedata"]))
    record["filedata"] = base64.b64decode(record["filedata"].encode("utf-8"))
    return record

def is_cv_already_stored():
    data = supabase.table("cv").select("*").eq("id", 0).execute()
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
