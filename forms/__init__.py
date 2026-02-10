from wtforms.validators import ValidationError
from .profile import ChangePasswordForm
from .occurrence import OccurrenceForm

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField
from wtforms.validators import InputRequired, Email, Length, EqualTo, Optional, Regexp
from models import ROLE_NADADOR, ROLE_SUPERVISOR, ROLE_PRESIDENTE

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[InputRequired()])
    password = PasswordField('Palavra-passe', validators=[InputRequired()])
    submit = SubmitField('Entrar')

class RegisterForm(FlaskForm):
    name = StringField('Nome', validators=[
        InputRequired(), 
        Length(min=2, message='Nome deve ter pelo menos 2 caracteres')
    ])
    
    email = StringField('Email', validators=[
        InputRequired(), 
        Email(message='Formato de email inválido')
    ])
    
    tax_number = StringField('Número de Contribuinte (NIF)', validators=[
        Optional(),
        Length(min=9, max=9, message='NIF deve ter exatamente 9 dígitos'),
        Regexp(r'^\d{9}$', message='NIF deve conter apenas números')
    ])
    
    password = PasswordField('Palavra-passe', validators=[
        Length(min=6, message='A palavra-passe deve ter pelo menos 6 caracteres')
    ])
    
    password_confirm = PasswordField('Confirmar palavra-passe', validators=[
        Length(min=6, message='A palavra-passe deve ter pelo menos 6 caracteres')
    ])
    
    role = SelectField('Função', choices=[
        (ROLE_NADADOR, 'Nadador-Salvador'),
        (ROLE_SUPERVISOR, 'Supervisor'),
        (ROLE_PRESIDENTE, 'Presidente')
    ])
    
    submit = SubmitField('Criar')

    def __init__(self, *args, **kwargs):
        """
        Inicializa o formulário
        
        Se não houver objeto (novo registro):
            Adiciona validação de campo obrigatório para senhas
        Se houver objeto (edição):
            Senha é opcional
        """
        super(RegisterForm, self).__init__(*args, **kwargs)
        if 'obj' not in kwargs:  # Se é um novo registro
            self.password.validators.insert(0, InputRequired())
            self.password_confirm.validators.insert(0, InputRequired())

    def validate_password_confirm(self, field):
        """
        Validação customizada: confirma se as senhas coincidem
        Executada automaticamente durante form.validate()
        """
        if self.password.data and self.password_confirm.data:
            if self.password.data != self.password_confirm.data:
                raise ValidationError('As palavras-passe não coincidem')

class ForgotPasswordForm(FlaskForm):
    email = StringField('Email', validators=[InputRequired(), Email(message='Formato de email inválido')])
    submit = SubmitField('Enviar link de recuperação')

class ResetPasswordForm(FlaskForm):
    password = PasswordField('Nova palavra-passe', validators=[InputRequired(), Length(min=6, message='A palavra-passe deve ter pelo menos 6 caracteres')])
    password_confirm = PasswordField('Confirmar nova palavra-passe', validators=[InputRequired(), EqualTo('password', message='As palavras-passe não coincidem')])
    submit = SubmitField('Redefinir palavra-passe')