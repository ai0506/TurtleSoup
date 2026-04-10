import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'turtle-soup-secret-key-2024'
    DATABASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'turtlesoup.db')

    # 保证永远不为 None，有环境变量用环境变量，没有用占位符（不发送、不泄露）
    DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY') or 'sk-placeholder'
    OPENAI_API_KEY = DEEPSEEK_API_KEY

    DEEPSEEK_BASE_URL = 'https://api.deepseek.com'
    DEEPSEEK_MODEL = 'deepseek-chat'
    DEEPSEEK_TEMPERATURE = 0.05
