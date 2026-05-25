from streamer.__main__ import main


def hashpw():
    import getpass

    import bcrypt

    password = getpass.getpass("Enter password: ")
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    print(f"\nAdd this to your .env:\nAUTH_PASSWORD_HASH={hashed.decode('utf-8')}")
