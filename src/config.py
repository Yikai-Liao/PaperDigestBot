from pydantic import BaseModel, Field, model_validator
from pathlib import Path
from typing import Self

REPO_ROOT = Path(__file__).parent.parent.resolve()
CONFIG_PATH = REPO_ROOT / "config/config.toml"

class PATConfig(BaseModel):
    """
    Configuration for the PAT (Personal Access Token) used to authenticate with the GitHub API.
    """
    key: str = Field(..., description="The path to the key file used for encryption/decryption.")
    db_path: str = Field(..., description="The path to the SQLite database file.")
    
    @model_validator(mode='after')
    def resolve_paths(self) -> Self:
        """
        将相对路径转换为绝对路径
        """
        if not Path(self.key).is_absolute():
            self.key = str(REPO_ROOT / self.key)
            
        if not Path(self.db_path).is_absolute():
            self.db_path = str(REPO_ROOT / self.db_path)
            
        return self



class TelegramConfig(BaseModel):
    """
    Configuration for the Telegram bot.
    """
    token: str = Field(..., description="The token for the Telegram bot.")

class Config(BaseModel):
    """
    Main configuration class that aggregates all configurations.
    """
    pat: PATConfig = Field(..., description="Configuration for the Personal Access Token.")
    telegram: TelegramConfig = Field(..., description="Configuration for the Telegram bot.")

    @classmethod
    def from_toml(cls, file_path: str=CONFIG_PATH) -> "Config":
        """
        Load configuration from a TOML file.
        
        Args:
            file_path (str): The path to the TOML configuration file.
        
        Returns:
            Config: An instance of the Config class populated with the data from the TOML file.
        """
        import toml
        data = toml.load(file_path)
        return cls(**data)
    
    @classmethod
    def default(cls) -> "Config":
        """
        Load the default configuration.
        
        Returns:
            Config: An instance of the Config class populated with default values.
        """
        return cls.from_toml()