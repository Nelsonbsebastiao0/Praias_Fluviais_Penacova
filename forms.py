# --- Importações ---
from flask_wtf import FlaskForm  # Base para formulários com CSRF protection
from wtforms import (
    StringField,     # Campo de texto
    PasswordField,   # Campo de senha (mascara entrada)
    SubmitField,     # Botão submit
    TextAreaField,   # Área de texto grande
    DateTimeField,   # Campo datetime (não usado atualmente)
    SelectField      # Campo select/dropdown
)
from wtforms.validators import (
    InputRequired,   # Validador de campo obrigatório
    Email,          # Validador de formato de email
    Length,         # Validador de comprimento mínimo/máximo
    Optional,       # Validador para campos opcionais
    Regexp          # Validador de expressão regular
)
from models import ROLE_NADADOR, ROLE_SUPERVISOR, ROLE_PRESIDENTE  # Constantes de roles

# --- Formulário de Login ---
class LoginForm(FlaskForm):
    """
    Formulário de Login
    
    Campos:
    - email: Endereço de email (obrigatório, deve ser válido)
    - password: Senha (obrigatória)
    - submit: Botão de envio
    """
    email = StringField('Email', validators=[InputRequired(), Email()])
    password = PasswordField('Password', validators=[InputRequired()])
    submit = SubmitField('Entrar')

from wtforms.validators import ValidationError  # Para validações customizadas

class RegisterForm(FlaskForm):
    """
    Formulário de Registro de Usuário
    
    Campos:
    - name: Nome do usuário (mín. 2 caracteres)
    - email: Email para login (deve ser único e válido)
    - password: Senha (mín. 6 caracteres)
    - password_confirm: Confirmação de senha (deve coincidir)
    - role: Função/papel do usuário (Nadador, Supervisor, Presidente)
    
    Comportamento:
    - Em novo registro: senha é obrigatória
    - Em edição: senha é opcional (mantém existente se vazia)
    """
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
    
    password = PasswordField('Password', validators=[
        Length(min=6, message='Senha deve ter pelo menos 6 caracteres')
    ])
    
    password_confirm = PasswordField('Confirmar Password', validators=[
        Length(min=6, message='Senha deve ter pelo menos 6 caracteres')
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
                raise ValidationError('As senhas não coincidem')

from datetime import datetime

from datetime import datetime

class OccurrenceForm(FlaskForm):
    """
    Formulário de Ocorrência
    
    Utilizado para criar e editar ocorrências. Separa o campo datetime
    em dois inputs HTML5 nativos (date e time) para melhor UX.
    """
    
    # Campo de data - usa input type="date" do HTML5
    date_input = StringField('Data',
        validators=[InputRequired(message='Data é obrigatória')],
        render_kw={"type": "date", "required": True})
    
    # Campo de hora - usa input type="time" do HTML5
    time_input = StringField('Hora',
        validators=[InputRequired(message='Hora é obrigatória')],
        render_kw={"type": "time", "required": True})
    
    # Zona onde ocorreu o incidente
    zone = SelectField('Zona',
        choices=[
            ('zona_norte', 'Zona Norte'),
            ('zona_central', 'Zona Central'),
            ('zona_sul', 'Zona Sul'),
        ],
        validators=[InputRequired(message='Zona é obrigatória')],
        render_kw={"class": "form-select", "required": True})
    
    # Tipo/categoria do incidente
    type = SelectField('Tipo',
        choices=[
            ('sujidade', 'Sujidade'),
            ('briga', 'Briga'),
            ('acidente', 'Acidente'),
            ('outro', 'Outro'),
        ],
        validators=[InputRequired(message='Tipo é obrigatório')],
        render_kw={"class": "form-select", "required": True})
    
    # Descrição detalhada (opcional)
    description = TextAreaField('Descrição',
        render_kw={"rows": 4})
    
    # Botão de submit
    submit = SubmitField('Guardar')

    def __init__(self, *args, **kwargs):
        """Inicializa o formulário e preenche campos de data/hora"""
        obj = kwargs.get('obj', None)
        super(OccurrenceForm, self).__init__(*args, **kwargs)
        
        if obj and getattr(obj, 'date', None):
            try:
                # Converte datetime para string nos formatos corretos
                self.date_input.data = obj.date.strftime('%Y-%m-%d')
                self.time_input.data = obj.date.strftime('%H:%M')
                print(f"Data preenchida: {self.date_input.data}")
                print(f"Hora preenchida: {self.time_input.data}")
            except Exception as e:
                print(f"Erro ao preencher data/hora: {e}")

    def validate(self, extra_validators=None):
        """
        Validação customizada do formulário
        
        Args:
            extra_validators: Validadores adicionais passados pelo Flask-WTF
        """
        # Chama validação da classe pai com os validadores extras
        if not super().validate(extra_validators=extra_validators):
            return False
            
        try:
            # Verifica se os campos têm dados
            if not self.date_input.data or not self.time_input.data:
                self.date_input.errors.append('Data e hora são obrigatórios')
                return False
                
            # Tenta criar um datetime válido
            date_str = f"{self.date_input.data} {self.time_input.data}"
            print(f"Tentando validar: {date_str}")
            
            datetime_obj = datetime.strptime(date_str, '%Y-%m-%d %H:%M')
            print(f"DateTime válido: {datetime_obj}")
            
            # Guarda o datetime validado para uso posterior
            self.validated_datetime = datetime_obj
            return True
            
        except ValueError as e:
            print(f"Erro na validação da data/hora: {e}")
            self.date_input.errors.append('Data ou hora em formato inválido')
            return False
        except Exception as e:
            print(f"Erro inesperado na validação: {e}")
            self.date_input.errors.append('Erro ao validar data e hora')
            return False
