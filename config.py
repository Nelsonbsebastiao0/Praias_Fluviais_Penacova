"""
Configurações da aplicação Flask

Este módulo define as configurações básicas da aplicação, incluindo:
- Diretório base
- Localização e configuração do banco de dados SQLite
- Chaves secretas e outras configurações do Flask

As configurações podem ser substituídas por variáveis de ambiente.
"""

import os

# Diretório base da aplicação - usado como referência para outros paths
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Configuração do banco de dados SQLite
DB_PATH = os.path.join(BASE_DIR, 'instance', 'praias.db')
# Garante que o diretório instance existe
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

class Config:
    """
    Classe de configuração do Flask
    
    Define todas as configurações necessárias para a aplicação:
    - SECRET_KEY: Chave para sessões e tokens CSRF
    - SQLALCHEMY_DATABASE_URI: URL de conexão com o banco
    - SQLALCHEMY_TRACK_MODIFICATIONS: Desabilita tracking do SQLAlchemy
    
    As configurações podem ser sobrescritas por variáveis de ambiente.
    """
    
    # Chave secreta para sessões e CSRF
    # Pode ser definida pela variável de ambiente SECRET_KEY
    SECRET_KEY = os.environ.get('SECRET_KEY', 'troca_esta_chave')
    
    # URL de conexão com o banco de dados
    # Suporta:
    # - SQLite (padrão para dev): sqlite:///instance/praias.db
    # - MySQL/MariaDB (produção): mysql+pymysql://user:pass@host/db
    # Pode ser definida pela variável de ambiente DATABASE_URL
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if DATABASE_URL:
        SQLALCHEMY_DATABASE_URI = DATABASE_URL
    else:
        # Padrão: SQLite (desenvolvimento)
        SQLALCHEMY_DATABASE_URI = f'sqlite:///{DB_PATH}'
    
    # Desabilita o sistema de eventos do SQLAlchemy para melhor performance
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # (Nenhuma credencial admin embutida por defeito)