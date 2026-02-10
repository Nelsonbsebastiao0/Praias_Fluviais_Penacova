"""
Script de inicialização do banco de dados

Este script recria o banco de dados e o popula com dados de exemplo,
incluindo usuários de diferentes roles e ocorrências de teste.

ATENÇÃO: Este script apaga o banco existente antes de criar um novo!

Dados criados:
1. Usuários:
   - presidente@penacova.pt (ROLE_PRESIDENTE)
   - supervisor@penacova.pt (ROLE_SUPERVISOR)
   - nadador@penacova.pt (ROLE_NADADOR)
   Todos com senha: password123

2. Ocorrências:
   - 5 ocorrências de exemplo para o usuário nadador
"""

import os
import sys
from werkzeug.security import generate_password_hash
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# Cria a aplicação Flask
app = Flask(__name__)

# Carrega configurações do config.py
from config import Config, DB_PATH
app.config.from_object(Config)

# Inicializa o banco de dados
from models import db
db.init_app(app)

# Importa modelos após inicialização do db para evitar imports circulares
from models import User, Occurrence, ROLE_NADADOR, ROLE_SUPERVISOR, ROLE_PRESIDENTE

def main():
    """
    Função principal de inicialização do banco de dados
    
    Esta função:
    1. Apaga o banco existente (se houver)
    2. Cria um novo banco com as tabelas
    3. Cria usuários de teste com diferentes roles
    4. Verifica se os usuários foram criados corretamente
    5. Cria ocorrências de exemplo
    
    Returns:
        None
        
    Side effects:
        - Apaga arquivo do banco se existir
        - Cria novo banco com estrutura
        - Insere dados de exemplo
        - Imprime status no console
    """
    print(f"Database path: {DB_PATH}")
    
    # Apaga banco existente para começar do zero
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Removed existing database: {DB_PATH}")
    
    # Cria as tabelas no novo banco
    with app.app_context():
        db.create_all()
        print("Created database tables")
        
        # Define dados dos usuários de teste
        users_data = [
            {
                'name': 'Presidente',
                'email': 'presidente@penacova.pt',
                'role': ROLE_PRESIDENTE
            },
            {
                'name': 'Supervisor',
                'email': 'supervisor@penacova.pt',
                'role': ROLE_SUPERVISOR
            },
            {
                'name': 'Nadador',
                'email': 'nadador@penacova.pt',
                'role': ROLE_NADADOR
            }
        ]
        
        # Cria os usuários de teste
        created_users = []
        for user_data in users_data:
            user = User(
                name=user_data['name'],
                email=user_data['email'],
                role=user_data['role']
            )
            user.set_password('password123')
            db.session.add(user)
            created_users.append(user)
            print(f"Created user: {user.email} with role: {user.role}")
        
        # Salva os usuários no banco
        db.session.commit()
        print("Users committed to database")
    
        # Verifica se os usuários foram criados corretamente
        users = User.query.all()
        print("\nVerifying created users:")
        for user in users:
            print(f"- {user.email} (role: {user.role}, has_password: {bool(user.password_hash)})")
            # Testa se a senha foi definida corretamente
            if user.check_password('password123'):
                print(f"  Password verification successful for {user.email}")
            else:
                print(f"  WARNING: Password verification failed for {user.email}")
        
        # Cria ocorrências de exemplo para o nadador
        nadador = User.query.filter_by(email='nadador@penacova.pt').first()
        if nadador:
            from datetime import datetime, timedelta
            # Cria 5 ocorrências nos últimos 5 dias
            for i in range(1, 6):
                ocorrencia = Occurrence(
                    date=datetime.utcnow() - timedelta(days=i),
                    zone=f'Zona {i}',
                    type='Pequena Lesão',
                    description=f'Exemplo de ocorrência {i}',
                    user_id=nadador.id
                )
                db.session.add(ocorrencia)
                print(f"Created occurrence {i} for user {nadador.email}")
            
            # Salva as ocorrências no banco
            db.session.commit()
            print("Sample occurrences created and committed")
        
        print("\nDatabase initialization complete!")

if __name__ == '__main__':
    main()
