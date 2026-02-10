from flask_wtf import FlaskForm
from wtforms import PasswordField, SubmitField
from wtforms.validators import InputRequired, Length, EqualTo

class ChangePasswordForm(FlaskForm):
    """
    Formulário para alteração da palavra-passe
    """
    current_password = PasswordField('Palavra-passe atual', validators=[
        InputRequired('A palavra-passe atual é obrigatória')
    ])
    
    new_password = PasswordField('Nova palavra-passe', validators=[
        InputRequired('A nova palavra-passe é obrigatória'),
        Length(min=6, message='A nova palavra-passe deve ter pelo menos 6 caracteres')
    ])
    
    confirm_password = PasswordField('Confirmar nova palavra-passe', validators=[
        InputRequired('A confirmação da palavra-passe é obrigatória'),
        EqualTo('new_password', message='As palavras-passe não coincidem')
    ])
    
    submit = SubmitField('Alterar Palavra-passe')