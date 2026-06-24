from passlib.context import CryptContext

pwd_context = CryptContext(
    schemes=["bcrypt"],
    bcrypt__rounds=14,
    deprecated="auto"
)

def hash_password(password: str) -> str:
    """
    hash a text password using the configured password context.
    Takes plain-text password to hash as an argument and returns resulting hashed password.
    """

    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain-text password against its hashed version.

    This func compares a plain-text password with
     a hashed one and return True if they match.
    """
    return pwd_context.verify(plain_password, hashed_password)
