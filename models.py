"""
Módulo de modelos do banco de dados.

Define os modelos SQLAlchemy para usuários e ocorrências,
estabelecendo o esquema do banco de dados e as relações entre tabelas.

Classes:
    User: Modelo para usuários do sistema
    Occurrence: Modelo para registro de ocorrências
"""

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from datetime import datetime
import json

# Instância global do SQLAlchemy
db = SQLAlchemy()

# Constantes para roles de usuário
ROLE_NADADOR = 'nadador'      # Usuário básico
ROLE_SUPERVISOR = 'supervisor' # Supervisor com permissões extras
ROLE_PRESIDENTE = 'presidente' # Administrador com todas as permissões

class User(db.Model, UserMixin):
    """
    Modelo de Usuário
    
    Representa um usuário no sistema com autenticação e permissões.
    Herda de UserMixin para integração com Flask-Login.
    
    Atributos:
        id (int): Identificador único do usuário
        name (str): Nome completo do usuário
        email (str): Email único do usuário (usado para login)
        password_hash (str): Hash da senha (nunca armazena senha em texto)
        role (str): Papel do usuário (nadador/supervisor/presidente)
        occurrences (relationship): Relação com ocorrências criadas
        preferences (relationship): Preferências do usuário
        notifications (relationship): Notificações do usuário
        activities (relationship): Histórico de atividades
    """
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    tax_number = db.Column(db.String(20), unique=True, nullable=True, index=True)  # NIF/Contribuinte
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(50), nullable=False, default=ROLE_NADADOR)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    occurrences = db.relationship('Occurrence', backref='user', lazy=True)
    preferences = db.relationship('UserPreferences', backref='user', lazy=True, uselist=False)
    notifications = db.relationship('Notification', backref='user', lazy=True)
    activities = db.relationship('ActivityLog', backref='user', lazy=True)

    def set_password(self, password):
        """
        Define a senha do usuário
        
        Gera um hash seguro da senha fornecida usando werkzeug.security
        
        Args:
            password (str): Senha em texto plano a ser hasheada
        """
        if password:
            self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """
        Verifica se a senha fornecida está correta
        
        Args:
            password (str): Senha em texto plano a ser verificada
            
        Returns:
            bool: True se a senha está correta, False caso contrário
        """
        if not password or not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        """Representação string do usuário para debug"""
        return f'<User {self.email}>'

class UserPreferences(db.Model):
    """
    Preferências do usuário para personalização da interface
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    theme = db.Column(db.String(20), default='light')  # light/dark
    notifications_enabled = db.Column(db.Boolean, default=True)
    email_notifications = db.Column(db.Boolean, default=True)
    display_settings = db.Column(db.Text)  # JSON com configurações de exibição

    def get_display_settings(self):
        """Retorna as configurações de exibição como dicionário"""
        if self.display_settings:
            return json.loads(self.display_settings)
        return {}

    def set_display_settings(self, settings):
        """Salva as configurações de exibição como JSON"""
        self.display_settings = json.dumps(settings)

class Notification(db.Model):
    """
    Notificações do sistema para usuários
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(20), nullable=False)  # info, warning, success, error
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    read = db.Column(db.Boolean, default=False)
    link = db.Column(db.String(200))  # Link opcional para mais detalhes

class PasswordResetToken(db.Model):
    """Tokens de recuperação de palavra-passe"""
    __tablename__ = 'password_reset_tokens'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    token = db.Column(db.String(200), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False, nullable=False)
    used_at = db.Column(db.DateTime)
    
    user = db.relationship('User', backref='reset_tokens')
    
    def is_valid(self):
        """Verifica se token ainda é válido"""
        return not self.used and datetime.utcnow() < self.expires_at

class ActivityLog(db.Model):
    """
    Registro de atividades dos usuários no sistema
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action = db.Column(db.String(50), nullable=False)  # login, create_occurrence, etc
    description = db.Column(db.Text, nullable=False)
    ip_address = db.Column(db.String(45))  # IPv4 ou IPv6
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    details = db.Column(db.Text)  # JSON com detalhes adicionais

    def set_details(self, details_dict):
        """Salva detalhes adicionais como JSON"""
        self.details = json.dumps(details_dict)

    def get_details(self):
        """Retorna os detalhes como dicionário"""
        if self.details:
            return json.loads(self.details)
        return {}

class Occurrence(db.Model):
    """
    Modelo de Ocorrência
    
    Representa um registro de ocorrência/incidente no sistema.
    Cada ocorrência está vinculada a um usuário que a registrou.
    
    Atributos:
        id (int): Identificador único da ocorrência
        date (datetime): Data e hora da ocorrência (UTC)
        zone (str): Zona/local onde ocorreu o incidente
        type (str): Tipo/categoria da ocorrência
        description (str): Descrição detalhada (opcional)
        user_id (int): ID do usuário que registrou (chave estrangeira)
        user (User): Relacionamento com o usuário que criou
    """
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    zone = db.Column(db.String(120), nullable=False)
    type = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


class Zone(db.Model):
    """
    Lookup table for Zones created by Presidente/Supervisor.
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class OccurrenceType(db.Model):
    """
    Lookup table for Occurrence types/categories created by Presidente/Supervisor.
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
