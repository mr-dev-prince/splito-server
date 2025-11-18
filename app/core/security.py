from passlib.context import CryptContext
import hashlib
import bcrypt

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password:str) -> str:
    sha_digest = hashlib.sha256(password.encode("utf-8")).digest()
    hashed = bcrypt.hashpw(sha_digest, bcrypt.gensalt())
    return hashed.decode()

def verify_password(password:str, hashed_password:str) -> bool:
    sha_digest = hashlib.sha256(password.encode("utf-8")).digest()
    return bcrypt.checkpw(sha_digest, hashed_password.encode())