from langchain_openai.llms import AzureOpenAI
import os
from dotenv import load_dotenv
from backend.configs.logger import logger


load_dotenv()

def load_config() -> AzureOpenAI:
    """Load configuration from environment variables."""
 
    config = {
        'azure_endpoint': os.getenv('AZURE_OPENAI_ENDPOINT'),
        'azure_api_key': os.getenv('AZURE_OPENAI_API_KEY'),
        'api_version': os.getenv('AZURE_OPENAI_API_VERSION', '2024-02-01'),
        'model':os.getenv('AZURE_OPENAI_DEPLOYMENT')
    }

    if not config['azure_api_key']:
        logger.error("Missing AZURE_OPENAI_API_KEY")
        raise ValueError("AZURE_OPENAI_API_KEY not found in environment variables")
    if not config['azure_endpoint']:
        logger.error("Missing AZURE_OPENAI_ENDPOINT")
        raise ValueError("AZURE_OPENAI_ENDPOINT not found in environment variables")
    if not config['api_version']:
        raise ValueError('AZURE_API_VERSION not found in environment variables')
    if not config['model']:
        raise ValueError('AZURE_MODEL not found in env variables')
    
    llm = AzureOpenAI(
        api_key=config.get('azure_api_key'),
        api_version=config.get('api_version'),
        model=config.get('azure_deployment'),
        azure_endpoint=config.get('azure_endpoint'),
        azure_deployment=config.get('azure_deployment')
    )
    return llm
