from redis.asyncio import Redis
from kupala.cache import Cache
from kupala.passwords import Passwords
from kupala.encryptors import Encryptor
from kupala.signers import Signer
from kupala.contrib.sqlalchemy import DatabaseManager
from kupala.mail import Mail, css_inliner, remove_html_comments
from kupala.files import Files, MemoryConfig, LocalConfig, S3Config
from kupala.sessions import RedisStore
from kupala.templating import Templates, app_processor, flash_processor, auth_processor

from demo.settings import settings

# Templates rendering.
templates = Templates(
    template_packages=["demo"],
    debug=settings.debug,
    globals={
        "settings": settings,
    },
    context_processors=[
        app_processor,
        flash_processor,
        auth_processor,
    ],
)

# Password hashing and verification.
passwords = Passwords(
    default="pbkdf2_sha256",
    schemes=["pbkdf2_sha256"],
)

# SQLAlchemy manager.
database = DatabaseManager(
    url=settings.database_url,
    pool_size=15,
    pool_recycle=1000,
    pool_timeout=10,
    max_overflow=2,
)

# Redis.
redis = Redis.from_url(settings.redis_url)

# Cache.
cache = Cache.from_url(settings.cache_url, namespace=f"demo:{settings.app_env}_")

# Data encryption.
encryptor = Encryptor(settings.encryption_key)

# Data signing.
signer = Signer(settings.secret_key)

# Email sending.
mail = Mail(
    dsn=settings.email_url,
    from_name=settings.email_from_name,
    from_address=settings.email_from_address,
    templates=templates,
    template_context={
        "settings": settings,
        "app_name": settings.app_name,
        "app_url": settings.app_url,
    },
    preprocessors=[css_inliner, remove_html_comments],
)

# File uploads.
files = Files.from_choices(
    settings.file_storage,
    memory=MemoryConfig(),
    local=LocalConfig(
        url_prefix="/media",
        directory=settings.file_local_upload_dir,
    ),
    s3=S3Config(
        bucket=settings.file_s3_bucket,
        access_key=settings.file_s3_access_key,
        secret_key=settings.file_s3_secret_key,
        region=settings.file_s3_region,
    ),
)

session_store = RedisStore(connection=redis, prefix=f"demo:{settings.app_env}_")
