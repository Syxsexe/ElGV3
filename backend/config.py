from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://localhost:5432/elg_pos"

    # DIAN
    dian_test_url: str = "https://vpfe-hab.dian.gov.co/WcfDianCustomerServices.svc?wsdl"
    dian_prod_url: str = "https://vpfe.dian.gov.co/WcfDianCustomerServices.svc?wsdl"
    dian_environment: str = "test"
    dian_mock_url: str = "http://localhost:8081"

    # Habilitación DIAN: juego de pruebas y software autorizado.
    dian_test_set_id: str = ""   # TestSetId del juego de pruebas (habilitación)
    dian_software_id: str = ""   # SoftwareID asignado por la DIAN
    dian_software_pin: str = ""  # PIN del software (SoftwareSecurityCode)

    # Digital Certificate
    certificate_path: str = ""
    certificate_password: str = ""

    # JWT
    jwt_secret: str = "change-this-to-a-random-secret-key"
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24

    # Credenciales de los POS autorizados a usar este backend.
    # Formato: "client_id:client_secret,client_id2:client_secret2"
    pos_clients: str = ""

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

    @property
    def pos_clients_map(self) -> dict[str, str]:
        """Parsea POS_CLIENTS ('id:secret,id2:secret2') a {client_id: secret}."""
        mapa: dict[str, str] = {}
        for par in self.pos_clients.split(","):
            par = par.strip()
            if not par:
                continue
            client_id, sep, secret = par.partition(":")
            client_id, secret = client_id.strip(), secret.strip()
            if sep and client_id and secret:
                mapa[client_id] = secret
        return mapa


settings = Settings()
BASE_DIR = Path(__file__).parent
