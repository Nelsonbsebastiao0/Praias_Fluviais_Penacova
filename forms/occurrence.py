from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, SubmitField
from wtforms.validators import InputRequired
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
    
    # Zona onde ocorreu o incidente (campo livre)
    zone = StringField('Zona',
        validators=[InputRequired(message='Zona é obrigatória')],
        render_kw={
            "class": "shadow-sm focus:ring-primary-500 focus:border-primary-500 block w-full sm:text-sm border-gray-300 rounded-md",
            "placeholder": "Ex: Margem direita, Zona das árvores, etc",
            "required": True
        })
    
    # Tipo/categoria do incidente (campo livre)
    type = StringField('Tipo',
        validators=[InputRequired(message='Tipo é obrigatório')],
        render_kw={
            "class": "shadow-sm focus:ring-primary-500 focus:border-primary-500 block w-full sm:text-sm border-gray-300 rounded-md",
            "placeholder": "Ex: Queda, Afogamento, Sujidade, etc",
            "required": True
        })
    
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
            # Do not allow future datetimes
            now = datetime.utcnow()
            if datetime_obj > now:
                self.date_input.errors.append('Data e hora não podem ser no futuro')
                return False
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