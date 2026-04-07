import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'turtle-soup-secret-key-2024'
    DATABASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'turtlesoup.db')
    DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY') or 'sk-fe2782b6a90a4b188b50c656a53672ad'
    DEEPSEEK_BASE_URL = 'https://api.deepseek.com'
    DEEPSEEK_MODEL = 'deepseek-chat'
    DEEPSEEK_TEMPERATURE = 0.05
