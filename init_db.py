"""
Script de inicialização do banco de dados
Cria usuários padrão se não existirem
"""
from app import app, db, User, ROLE_PRESIDENTE, ROLE_SUPERVISOR, ROLE_NADADOR
from werkzeug.security import generate_password_hash

def init_database():
    """Inicializa banco com usuários padrão"""
    with app.app_context():
        # Criar tabelas se não existirem
        db.create_all()
        
        # Verificar se já existem usuários
        if User.query.count() > 0:
            print("✅ Banco já tem usuários. Nada a fazer.")
            return
        
        print("🔧 Criando usuários padrão...")
        
        # Presidente
        presidente = User(
            username='presidente',
            email='presidente@praias.pt',
            password_hash=generate_password_hash('Presidente123'),
            role=ROLE_PRESIDENTE,
            active=True,
            name='Presidente Silva'
        )
        
        # Supervisor
        supervisor = User(
            username='supervisor',
            email='supervisor@praias.pt',
            password_hash=generate_password_hash('Supervisor123'),
            role=ROLE_SUPERVISOR,
            active=True,
            name='Supervisor Costa'
        )
        
        # Nadador 1
        nadador1 = User(
            username='nadador1',
            email='nadador1@praias.pt',
            password_hash=generate_password_hash('Nadador123'),
            role=ROLE_NADADOR,
            active=True,
            name='Nadador Salvador João'
        )
        
        # Nadador 2
        nadador2 = User(
            username='nadador2',
            email='nadador2@praias.pt',
            password_hash=generate_password_hash('Nadador123'),
            role=ROLE_NADADOR,
            active=True,
            name='Nadador Salvador Maria'
        )
        
        # Admin (para você)
        admin = User(
            username='admin',
            email='nelsonalunogpsi@gmail.com',
            password_hash=generate_password_hash('Admin123'),
            role=ROLE_PRESIDENTE,
            active=True,
            name='Administrador Nelson'
        )
        
        db.session.add_all([presidente, supervisor, nadador1, nadador2, admin])
        db.session.commit()
        
        print("✅ Usuários criados com sucesso!")
        print("\n" + "="*60)
        print("CREDENCIAIS DE ACESSO:")
        print("="*60)
        print("\n👑 PRESIDENTE:")
        print("   Username: presidente")
        print("   Password: Presidente123")
        print("   Email: presidente@praias.pt")
        print("\n👤 SUPERVISOR:")
        print("   Username: supervisor")
        print("   Password: Supervisor123")
        print("   Email: supervisor@praias.pt")
        print("\n🏊 NADADOR 1:")
        print("   Username: nadador1")
        print("   Password: Nadador123")
        print("   Email: nadador1@praias.pt")
        print("\n🏊 NADADOR 2:")
        print("   Username: nadador2")
        print("   Password: Nadador123")
        print("   Email: nadador2@praias.pt")
        print("\n🔧 ADMIN (SEU):")
        print("   Username: admin")
        print("   Password: Admin123")
        print("   Email: nelsonalunogpsi@gmail.com")
        print("\n" + "="*60)

if __name__ == '__main__':
    init_database()
