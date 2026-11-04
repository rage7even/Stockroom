import hashlib
import hmac


def hash_password(password):
    from django.contrib.auth.hashers import make_password
    return make_password(password)


def verify_password(password, stored):
    from django.contrib.auth.hashers import check_password
    if '$' in stored:
        return check_password(password, stored)
    # Existing databases used salt:hex before the Django migration.
    try:
        salt, expected = stored.split(':')
        value = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()
        return hmac.compare_digest(value, expected)
    except (ValueError, TypeError):
        return False


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()
