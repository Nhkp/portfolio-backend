from sqlalchemy import Column, Integer, String, LargeBinary
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class CVFile(Base):
    __tablename__ = "cv_files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    filedata = Column(LargeBinary, nullable=False)
