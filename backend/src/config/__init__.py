import os
import json
from pathlib import Path
from dotenv import load_dotenv

class Config:
    """Load and manage configuration from JSON and environment variables"""
    
    def __init__(self):
        # Load environment variables from secrets.env
        env_path = Path(__file__).parent.parent.parent / 'secrets.env'
        if env_path.exists():
            load_dotenv(env_path)
        
        # Load JSON config
        config_path = Path(__file__).parent.parent.parent / 'config' / 'config.json'
        if not config_path.exists():
            raise FileNotFoundError(f'Config file not found: {config_path}')
        
        with open(config_path) as f:
            self.data = json.load(f)
    
    def get(self, key_path: str, default=None):
        """
        Get nested config value using dot notation
        Example: 'trading.position_size.confidence_8_10'
        """
        keys = key_path.split('.')
        value = self.data
        
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return default
        
        return value if value is not None else default
    
    def get_secret(self, key: str):
        """Get environment variable (API keys, tokens)"""
        value = os.getenv(key)
        if value is None:
            raise ValueError(f'Environment variable {key} not set. Check secrets.env')
        return value
    
    def get_optional_secret(self, key: str, default=None):
        """Get optional secret from environment"""
        """Get optional environment variable"""
        return os.getenv(key, default)


    def get_optional_config(self, key: str, default=None):
        """Get config value with default fallback"""
        return self.data.get(key, default)

    def to_dict(self):
        """Return full configuration data as a dictionary"""
        return self.data
