import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'turtle-soup-secret-key-2024'
    DATABASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'turtlesoup.db')
    DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')
    OPENAI_API_KEY = DEEPSEEK_API_KEY
    DEEPSEEK_BASE_URL = 'https://api.deepseek.com'
    DEEPSEEK_MODEL = 'deepseek-chat'
    DEEPSEEK_TEMPERATURE = 0.05
