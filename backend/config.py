from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://localhost:5432/elg_pos"

    # DIAN
    dian_test_url: str = "https://vpfe-hab.dian.gov.co/WcfDianCustomerServices.svc?wsdl"
    dian_prod_url: str = "https://vpfe.dian.gov.co/WcfDianCustomerServices.svc?wsdl"
    dian_environment: str = "test"

    # Digital Certificate
    certificate_path: str = ""
    certificate_password: str = ""

    # JWT
    jwt_secret: str = "change-this-to-a-random-secret-key"
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24

    # Emisor (POS owner)
    emisor_nit: str = ""
    emisor_razon_social: str = ""
    emisor_nombre_comercial: str = ""
    emisor_direccion: str = ""
    emisor_municipio: str = ""
    emisor_departamento: str = ""
    emisor_pais: str = "CO"
    emisor_telefono: str = ""
    emisor_email: str = ""
    regmen_fiscal: str = "48-20"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
BASE_DIR = Path(__file__).parent
