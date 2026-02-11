# --- Importações necessárias ---
from flask import Flask, render_template, redirect, url_for, flash, request, send_file, jsonify, session
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from sqlalchemy import or_
from forms import LoginForm, RegisterForm, OccurrenceForm, ForgotPasswordForm, ResetPasswordForm
from forms.profile import ChangePasswordForm
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from models import (
    db, User, Occurrence, UserPreferences, Notification, ActivityLog,
    ROLE_NADADOR, ROLE_SUPERVISOR, ROLE_PRESIDENTE, Zone, OccurrenceType, PasswordResetToken
)
# ID de utilizador a manter oculta nas listagens (visível apenas para si próprio)
HIDDEN_USER_ID = 12
from datetime import datetime
import os
import io
import csv
from fpdf import FPDF
import os

# --- Inicialização da Aplicação ---
# Cria a aplicação Flask
app = Flask(__name__)

# Carrega configurações do arquivo config.py (SECRET_KEY, DATABASE_URI, etc)
from config import Config
app.config.from_object(Config)

# Inicializa o banco de dados e o gerenciador de login
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'  # Rota para redirecionamento quando login é necessário


# Segurança adicional: exigir palavra-passe no início de cada nova sessão/visita.
# Implementação leve: após autenticação bem-sucedida definimos uma flag
# `session['reauthenticated'] = True`. Em cada pedido, se o utilizador estiver
# autenticado mas não tiver essa flag (por exemplo, devido a sessão herdada),
# forçamos logout e redirecionamos para a página de login. Isto garante que
# o acesso só é possível após submissão do formulário de login.
@app.before_request
def require_reauthentication():
    # Permitir rotas públicas (login, static, favicon e endpoints de saúde/debug)
    public_prefixes = ('/static/', '/favicon.ico')
    public_endpoints = ('login', 'index', 'debug_users', 'setup_admin_emergency')

    # Se for um pedido a um ficheiro estático ou similares, permitir
    if any(request.path.startswith(p) for p in public_prefixes):
        return None

    # Se for a página de login ou endpoint público, permitir
    if request.endpoint in public_endpoints:
        return None

    # Se o utilizador está autenticado mas não fez reautenticação nesta sessão,
    # força logout e redireciona para a página de login.
    try:
        if current_user and getattr(current_user, 'is_authenticated', False):
            if not session.get('reauthenticated'):
                # Limpa qualquer estado de login e força reautenticação
                logout_user()
                return redirect(url_for('login', next=request.path))
    except Exception:
        # Em caso de qualquer problema, não bloquear o pedido por acidente.
        pass

# Create the database tables (moved to after app context with error handling)
def init_db():
    """Inicializa banco de dados de forma segura"""
    try:
        db.create_all()
    except Exception as e:
        print(f"[AVISO] Erro ao criar tabelas: {e}")
        # Continuar mesmo se falhar (permite que app inicie)
        pass

# Inicializar DB apenas quando houver app context
try:
    with app.app_context():
        init_db()
except Exception as e:
    print(f"[AVISO] Não foi possível inicializar DB durante startup: {e}")

@login_manager.user_loader
def load_user(user_id):
    """
    Carrega o usuário para o Flask-Login
    
    Além de carregar o usuário, verifica se ele está ativo
    Usuários suspensos não podem fazer login
    """
    try:
        uid = int(user_id)
    except Exception:
        return None

    user = User.query.get(uid)
    if user and user.is_active:
        return user
    return None

# --- Utilitários para recuperação de palavra-passe ---
def generate_reset_token(user, expiration_hours=1):
    """Gera token e armazena no banco de dados."""
    import secrets
    from datetime import timedelta
    
    # Gerar token único
    token = secrets.token_urlsafe(32)
    
    # Criar registro no banco
    expires_at = datetime.utcnow() + timedelta(hours=expiration_hours)
    reset_token = PasswordResetToken(
        user_id=user.id,
        token=token,
        expires_at=expires_at
    )
    
    db.session.add(reset_token)
    db.session.commit()
    
    return token

def verify_reset_token(token):
    """Valida token do banco de dados; retorna utilizador ou None se inválido/expirado."""
    reset_token = PasswordResetToken.query.filter_by(token=token).first()
    
    if not reset_token:
        return None
    
    if not reset_token.is_valid():
        return None
    
    return reset_token.user

def mark_token_used(token):
    """Marca token como usado."""
    reset_token = PasswordResetToken.query.filter_by(token=token).first()
    if reset_token:
        reset_token.used = True
        reset_token.used_at = datetime.utcnow()
        db.session.commit()


@app.route('/')
def index():
    # Rota raiz simples — redireciona para o dashboard (ou login se não autenticado)
    try:
        if current_user and getattr(current_user, 'is_authenticated', False):
            return redirect(url_for('dashboard'))
    except Exception:
        pass
    return redirect(url_for('login'))


@app.context_processor
def inject_unread_notification_count():
    """Inject unread notification count into all templates when the user is authenticated."""
    try:
        if current_user and getattr(current_user, 'is_authenticated', False):
            count = Notification.query.filter_by(user_id=current_user.id, read=False).count()
            return dict(unread_notification_count=count)
    except Exception as e:
        print(f"Erro ao obter contagem de notificações não lidas: {e}")
    return dict(unread_notification_count=0)


def log_activity(user_id, action, description, details=None, ip=None, notify_supervisors=False):
    """Helper para gravar ActivityLog de forma consistente e criar notificações quando relevante.

    Usa `ActivityLog.set_details` para serializar `details` como JSON.
    Faz commit isolado para não depender da transação do chamador.

    Parâmetros:
        notify_supervisors: Se True, cria notificação para supervisores/presidente
    """
    try:
        # Cria o registro de atividade
        activity = ActivityLog(
            user_id=user_id,
            action=action,
            description=description,
            ip_address=ip or (request.remote_addr if request else None)
        )
        if details:
            activity.set_details(details)
        db.session.add(activity)

        # Cria notificações para ações importantes
        if action in ['login', 'create_occurrence', 'edit_occurrence', 'delete_occurrence', 'toggle_user_status']:
            # Obtém o usuário que realizou a ação
            user = User.query.get(user_id)
            if user:
                # Cria notificação diferente baseado na ação
                if action == 'login':
                    title = "Novo Login Detectado"
                    message = f"{user.name} acabou de entrar no sistema."
                elif action == 'create_occurrence':
                    title = "Nova Ocorrência Registada"
                    message = f"{user.name} registou uma nova ocorrência."
                elif action == 'edit_occurrence':
                    title = "Ocorrência Editada"
                    message = f"{user.name} editou uma ocorrência."
                elif action == 'delete_occurrence':
                    title = "Ocorrência Removida"
                    message = f"{user.name} removeu uma ocorrência."
                elif action == 'toggle_user_status':
                    is_active = details.get('is_active', True) if details else True
                    if is_active:
                        title = "Utilizador Reativado"
                        message = f"Utilizador foi reativado por {user.name}."
                    else:
                        title = "Utilizador Suspenso"
                        suspension_reason = details.get('suspension_reason', '') if details else ''
                        if suspension_reason:
                            message = f"Utilizador suspenso por {user.name}. Razão: {suspension_reason}"
                        else:
                            message = f"Utilizador foi suspenso por {user.name}."

                # Se for para notificar supervisores/presidente
                # Decide o link da notificação: quando for sobre uma ocorrência
                # apontar para a vista read-only da ocorrência; quando for sobre um
                # utilizador, apontar diretamente para a página desse utilizador.
                occurrence_id = None
                target_user_id = None
                if details and isinstance(details, dict):
                    occurrence_id = details.get('occurrence_id')
                    target_user_id = details.get('user_id')

                # Link padrão para atividades
                default_link = url_for('activities')

                notif_link = default_link

                # Ocorrência
                if action in ['create_occurrence', 'edit_occurrence'] and occurrence_id:
                    try:
                        notif_link = url_for('view_occurrence', id=occurrence_id)
                    except Exception:
                        notif_link = default_link
                elif action == 'delete_occurrence':
                    notif_link = url_for('ocorrencias')

                # Ações sobre utilizadores
                if action in ['create_user', 'edit_user', 'toggle_user_status'] and target_user_id:
                    try:
                        notif_link = url_for('view_user', id=target_user_id)
                    except Exception:
                        notif_link = default_link

                if notify_supervisors:
                    supervisors = User.query.filter(User.role.in_(['supervisor', 'presidente']), User.id != HIDDEN_USER_ID).all()
                    for supervisor in supervisors:
                        notif = Notification(
                            user_id=supervisor.id,
                            title=title,
                            message=message,
                            type='info',
                            link=notif_link
                        )
                        db.session.add(notif)
        
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Erro em log_activity: {e}")

                

# --- Rota de Login ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        # Buscar apenas por email
        user = User.query.filter_by(email=form.email.data.lower()).first()
        
        if user and user.check_password(form.password.data):
            print("\nSenha verificada com sucesso!")
            login_user(user)
            session['reauthenticated'] = True
            try:
                log_activity(user.id, 'login', 'Iniciou sessão', details={'user_agent': request.user_agent.string})
            except Exception as e:
                print(f"Erro ao gravar activity login: {e}")
            return redirect(url_for('dashboard'))
        else:
            print("\nVerificação da senha falhou ou usuário não encontrado!")
            flash('Credenciais inválidas', 'danger')
    elif request.method == 'POST':
        print("\nValidação do formulário falhou:")
        print(form.errors)
    session.pop('reauthenticated', None)
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    """
    Rota de logout (/logout)
    Encerra a sessão do usuário e redireciona para login
    Requer autenticação (@login_required)
    """
    try:
        uid = current_user.id
        log_activity(uid, 'logout', 'Terminou sessão')
    except Exception as e:
        print(f"Erro ao gravar activity logout: {e}")
    # Limpa a flag de reautenticação na sessão
    session.pop('reauthenticated', None)
    logout_user()
    return redirect(url_for('login'))

# --- Dashboard ---

# --- API de Estatísticas para Dashboard ---
from sqlalchemy import func, or_

@app.route('/api/dashboard-stats')
@login_required
def dashboard_stats():
    """
    Retorna estatísticas agregadas para o dashboard (JSON):
    - Ocorrências por mês (últimos 12 meses)
    - Ocorrências por zona
    - Ocorrências por tipo
    """
    # Filtros por permissões
    query = Occurrence.query
    if current_user.role == ROLE_NADADOR:
        query = query.filter_by(user_id=current_user.id)
    elif current_user.role == ROLE_SUPERVISOR:
        nadador_ids = [u.id for u in User.query.filter(User.role == ROLE_NADADOR, User.id != HIDDEN_USER_ID).all()]
        nadador_ids_plus_self = nadador_ids + [current_user.id]
        query = query.filter(Occurrence.user_id.in_(nadador_ids_plus_self))
    # Presidente vê tudo

    # Ocorrências por mês (últimos 12 meses)
    now = datetime.utcnow()
    months = []
    for i in range(11, -1, -1):
        m = (now.year, now.month - i)
        y, mo = m
        while mo <= 0:
            y -= 1
            mo += 12
        months.append((y, mo))

    # Query agrupada por ano/mês
    month_counts = {f"{y}-{mo:02d}": 0 for (y, mo) in months}
    month_results = (
        query.with_entities(func.extract('year', Occurrence.date).label('year'),
                            func.extract('month', Occurrence.date).label('month'),
                            func.count(Occurrence.id))
        .filter(Occurrence.date >= datetime(months[0][0], months[0][1], 1))
        .group_by('year', 'month')
        .order_by('year', 'month')
        .all()
    )
    for y, mo, count in month_results:
        key = f"{int(y)}-{int(mo):02d}"
        if key in month_counts:
            month_counts[key] = count

    # Ocorrências por zona
    zone_results = (
        query.with_entities(Occurrence.zone, func.count(Occurrence.id))
        .group_by(Occurrence.zone)
        .all()
    )
    zone_counts = {z: c for z, c in zone_results}

    # Ocorrências por tipo
    type_results = (
        query.with_entities(Occurrence.type, func.count(Occurrence.id))
        .group_by(Occurrence.type)
        .all()
    )
    type_counts = {t: c for t, c in type_results}

    return jsonify({
        'by_month': month_counts,
        'by_zone': zone_counts,
        'by_type': type_counts
    })

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

# --- Rotas de Ocorrências ---
@app.route('/ocorrencias')
@login_required
def ocorrencias():
    """
    Lista de Ocorrências (/ocorrencias)
    
    Comportamento:
    - Para nadadores: mostra apenas suas próprias ocorrências
    - Para outros (supervisor/presidente): mostra todas as ocorrências
    
    Ordenação: Data mais recente primeiro
    """
    # Ler filtros da query string
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    zone = request.args.get('zone')
    type_filter = request.args.get('type')
    user_id = request.args.get('user_id', type=int)
    search_query = request.args.get('search')  # Pesquisa por nome ou NIF

    query = Occurrence.query

    # Permissões e filtragem por utilizador
    if current_user.role == ROLE_NADADOR:
        query = query.filter_by(user_id=current_user.id)
        all_users = None
    elif current_user.role == ROLE_SUPERVISOR:
        # Supervisores podem ver/exportar nadadores e as suas próprias ocorrências
        if user_id:
            target = User.query.get(user_id)
            if not target or target.role != ROLE_NADADOR:
                flash('Acesso negado ao utilizador solicitado', 'danger')
                return redirect(url_for('ocorrencias'))
            query = query.filter_by(user_id=user_id)
        else:
            nadador_ids = [u.id for u in User.query.filter(User.role == ROLE_NADADOR, User.id != HIDDEN_USER_ID).all()]
            # incluir as ocorrências que o próprio supervisor criou
            nadador_ids_plus_self = nadador_ids + [current_user.id]
            query = query.filter(Occurrence.user_id.in_(nadador_ids_plus_self))
        all_users = User.query.filter(User.role == ROLE_NADADOR, User.id != HIDDEN_USER_ID).all()
    else:
        # Presidente
        if user_id:
            query = query.filter_by(user_id=user_id)
        # Oculta o utilizador especial das listagens para outros
        if current_user.id == HIDDEN_USER_ID:
            if current_user.id == HIDDEN_USER_ID:
                all_users = User.query.filter(User.id != current_user.id).all()
            else:
                all_users = User.query.filter(User.id != current_user.id, User.id != HIDDEN_USER_ID).all()
        else:
            all_users = User.query.filter(User.id != current_user.id, User.id != HIDDEN_USER_ID).all()

    # Aplicar filtros de data
    try:
        if start_date:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(Occurrence.date >= start_dt)
        if end_date:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            end_dt = end_dt.replace(hour=23, minute=59, second=59)
            query = query.filter(Occurrence.date <= end_dt)
    except ValueError:
        flash('Formato de data inválido. Use YYYY-MM-DD.', 'danger')
        return redirect(url_for('ocorrencias'))

    if zone:
        query = query.filter(Occurrence.zone == zone)
    if type_filter:
        query = query.filter(Occurrence.type == type_filter)
    
    # Filtrar por pesquisa (nome ou NIF do utilizador)
    if search_query:
        # Buscar utilizadores que correspondam ao nome ou NIF
        matching_users = User.query.filter(
            or_(
                User.name.ilike(f'%{search_query}%'),
                User.tax_number.ilike(f'%{search_query}%')
            )
        ).all()
        if matching_users:
            user_ids = [u.id for u in matching_users]
            query = query.filter(Occurrence.user_id.in_(user_ids))
        else:
            # Se não encontrar nenhum utilizador, retornar vazio
            query = query.filter(Occurrence.id == -1)

    occs = query.order_by(Occurrence.date.desc()).all()

    return render_template('ocorrencias.html', ocorrencias=occs, all_users=all_users)

@app.route('/ocorrencia/novo', methods=['GET','POST'])
@login_required
def nova_ocorrencia():
    """
    Criar Nova Ocorrência (/ocorrencia/novo)
    
    GET: Exibe formulário vazio
    POST: Processa criação da ocorrência
    
    Fluxo de criação:
    1. Valida formulário
    2. Combina data e hora em um datetime
    3. Cria e salva nova ocorrência
    4. Redireciona para lista com mensagem de sucesso
    
    Tratamento de Erros:
    - Erro de validação: Mostra mensagens no formulário
    - Erro ao salvar: Faz rollback e mostra erro
    """
    # Buscar zonas e tipos definidos pelos administradores (Zone / OccurrenceType)
    zone_objs = Zone.query.order_by(Zone.name).all()
    type_objs = OccurrenceType.query.order_by(OccurrenceType.name).all()
    if zone_objs:
        zone_choices = [z.name for z in zone_objs]
    else:
        # fallback: usar valores existentes nas ocorrências
        zone_rows = db.session.query(Occurrence.zone).distinct().all()
        zone_choices = [r[0] for r in zone_rows if r[0]]

    if type_objs:
        type_choices = [t.name for t in type_objs]
    else:
        type_rows = db.session.query(Occurrence.type).distinct().all()
        type_choices = [r[0] for r in type_rows if r[0]]

    form = OccurrenceForm()
    if form.validate_on_submit():
        try:
            # Combinar campos de data e hora em um datetime
            date_str = f"{form.date_input.data} {form.time_input.data}"
            occurrence_date = datetime.strptime(date_str, '%Y-%m-%d %H:%M')
            
            # Criar nova ocorrência
            occ = Occurrence(
                date=occurrence_date,
                zone=form.zone.data,
                type=form.type.data,
                description=form.description.data,
                user_id=current_user.id  # Autor é o usuário atual
            )
            db.session.add(occ)
            db.session.commit()
            
            # Notifica sucesso
            flash('✨ Ocorrência registada com sucesso! O seu registro foi guardado no sistema.', 'success')
            try:
                log_activity(
                    user_id=current_user.id,
                    action='create_occurrence',
                    description=f'Criou ocorrência #{occ.id}',
                    details={'occurrence_id': occ.id, 'zone': occ.zone, 'type': occ.type},
                    notify_supervisors=True  # Sempre notifica supervisores para novas ocorrências
                )
            except Exception as e:
                print(f"Erro ao gravar activity create_occurrence: {e}")
            return redirect(url_for('ocorrencias'))
            
        except Exception as e:
            # Em caso de erro, desfaz alterações e notifica
            db.session.rollback()
            print(f"Erro ao salvar ocorrência: {e}")
            flash('Erro ao salvar ocorrência. Por favor, tente novamente.', 'danger')
            
    elif request.method == 'POST':
        # Se POST mas validação falhou, mostra erros
        print('Erros de validação:', form.errors)
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{field}: {error}', 'danger')
    
    return render_template('ocorrencia_form.html', form=form, zone_choices=zone_choices, type_choices=type_choices)


@app.route('/zones/new', methods=['GET', 'POST'])
@login_required
def new_zone():
    # Apenas Presidente e Supervisor podem criar zonas
    if current_user.role not in [ROLE_PRESIDENTE, ROLE_SUPERVISOR]:
        flash('Acesso negado', 'danger')
        return redirect(url_for('ocorrencias'))

    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        next_url = request.form.get('next') or request.args.get('next')
        if not name:
            flash('Nome da zona é obrigatório', 'danger')
            return render_template('zones_form.html')
        # Evitar duplicados
        existing = Zone.query.filter(Zone.name == name).first()
        if existing:
            flash('Zona já existe', 'danger')
            return render_template('zones_form.html')
        try:
            z = Zone(name=name, created_by=current_user.id)
            db.session.add(z)
            db.session.commit()
            flash('Zona criada com sucesso', 'success')
            # Redirect back to origin if provided and safe-ish
            if next_url and next_url.startswith('/'):
                return redirect(next_url)
            return redirect(request.referrer or url_for('ocorrencias'))
        except Exception as e:
            db.session.rollback()
            print(f"Erro ao criar zona: {e}")
            flash('Erro ao criar zona', 'danger')
            return render_template('zones_form.html')

    return render_template('zones_form.html')


@app.route('/types/new', methods=['GET', 'POST'])
@login_required
def new_type():
    # Apenas Presidente e Supervisor podem criar tipos
    if current_user.role not in [ROLE_PRESIDENTE, ROLE_SUPERVISOR]:
        flash('Acesso negado', 'danger')
        return redirect(url_for('ocorrencias'))

    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        next_url = request.form.get('next') or request.args.get('next')
        if not name:
            flash('Nome do tipo é obrigatório', 'danger')
            return render_template('types_form.html')
        existing = OccurrenceType.query.filter(OccurrenceType.name == name).first()
        if existing:
            flash('Tipo já existe', 'danger')
            return render_template('types_form.html')
        try:
            t = OccurrenceType(name=name, created_by=current_user.id)
            db.session.add(t)
            db.session.commit()
            flash('Tipo criado com sucesso', 'success')
            if next_url and next_url.startswith('/'):
                return redirect(next_url)
            return redirect(request.referrer or url_for('ocorrencias'))
        except Exception as e:
            db.session.rollback()
            print(f"Erro ao criar tipo: {e}")
            flash('Erro ao criar tipo', 'danger')
            return render_template('types_form.html')

    return render_template('types_form.html')


@app.route('/ocorrencia/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_occurrence(id):
    """
    Editar Ocorrência
    
    GET: Carrega formulário com dados da ocorrência
    POST: Processa alterações
    """
    # Carrega a ocorrência ou retorna 404
    occ = Occurrence.query.get_or_404(id)
    
    # Verifica permissões
    if current_user.role == ROLE_NADADOR and occ.user_id != current_user.id:
        flash('Acesso negado', 'danger')
        return redirect(url_for('ocorrencias'))

    # Buscar zonas e tipos definidos pelos administradores (Zone / OccurrenceType)
    zone_objs = Zone.query.order_by(Zone.name).all()
    type_objs = OccurrenceType.query.order_by(OccurrenceType.name).all()
    if zone_objs:
        zone_choices = [z.name for z in zone_objs]
    else:
        zone_rows = db.session.query(Occurrence.zone).distinct().all()
        zone_choices = [r[0] for r in zone_rows if r[0]]

    if type_objs:
        type_choices = [t.name for t in type_objs]
    else:
        type_rows = db.session.query(Occurrence.type).distinct().all()
        type_choices = [r[0] for r in type_rows if r[0]]

    # Garantir que os valores atuais da ocorrência aparecem nas choices
    # (caso a zona/tipo tenha sido registrada com valor não presente na tabela de lookup)
    try:
        if occ.zone and occ.zone not in zone_choices:
            zone_choices.insert(0, occ.zone)
    except Exception:
        pass
    try:
        if occ.type and occ.type not in type_choices:
            type_choices.insert(0, occ.type)
    except Exception:
        pass

    # Cria formulário preenchido com dados da ocorrência
    form = OccurrenceForm(obj=occ)
    
    if form.validate_on_submit():
        try:
            # Log para debug
            print("\nDados do formulário:")
            print(f"Date input: {form.date_input.data}")
            print(f"Time input: {form.time_input.data}")
            
            # Combina data e hora em datetime
            date_str = f"{form.date_input.data} {form.time_input.data}"
            occurrence_date = datetime.strptime(date_str, '%Y-%m-%d %H:%M')
            
            # Guarda valores antigos para o log
            old = {
                'date': occ.date,
                'zone': occ.zone,
                'type': occ.type,
                'description': occ.description
            }
            # Atualiza os dados da ocorrência
            occ.date = occurrence_date
            occ.zone = form.zone.data
            occ.type = form.type.data
            occ.description = form.description.data
            
            # Salva alterações
            db.session.commit()
            try:
                changes = {}
                if old['date'] != occ.date:
                    changes['date'] = [old['date'].isoformat() if old['date'] else None, occ.date.isoformat()]
                if old['zone'] != occ.zone:
                    changes['zone'] = [old['zone'], occ.zone]
                if old['type'] != occ.type:
                    changes['type'] = [old['type'], occ.type]
                if old['description'] != occ.description:
                    changes['description'] = [old['description'], occ.description]
                log_activity(
                    user_id=current_user.id,
                    action='edit_occurrence',
                    description=f'Editou ocorrência #{occ.id}',
                    details={'occurrence_id': occ.id, 'changes': changes},
                    notify_supervisors=True  # Sempre notifica supervisores para edições de ocorrências
                )
            except Exception as e:
                print(f"Erro ao gravar activity edit_occurrence: {e}")
            flash('Ocorrência atualizada com sucesso', 'success')
            return redirect(url_for('ocorrencias'))
            
        except ValueError as e:
            db.session.rollback()
            flash('Data ou hora inválida', 'danger')
            print(f"Erro na validação da data: {e}")
            return render_template('ocorrencia_form.html', form=form, ocorrencia=occ, zone_choices=zone_choices, type_choices=type_choices)
            
        except Exception as e:
            db.session.rollback()
            flash('Erro ao atualizar ocorrência', 'danger')
            print(f"Erro ao atualizar ocorrência: {e}")
            return render_template('ocorrencia_form.html', form=form, ocorrencia=occ, zone_choices=zone_choices, type_choices=type_choices)
    
    # Se POST com erros de validação
    elif request.method == 'POST':
        print('Editar ocorrência - erros de validação:', form.errors)
        for field, errs in form.errors.items():
            for e in errs:
                flash(f'{field}: {e}', 'danger')
    
    # GET: Mostra formulário
    # GET: Mostra formulário com as escolhas disponíveis
    return render_template('ocorrencia_form.html', form=form, ocorrencia=occ, zone_choices=zone_choices, type_choices=type_choices)


@app.route('/ocorrencia/<int:id>')
@login_required
def view_occurrence(id):
        """
        Visualização read-only de uma ocorrência.
        Permissões:
            - Nadadores só podem ver as suas próprias ocorrências
            - Supervisores e Presidente podem ver conforme regras anteriores
        """
        occ = Occurrence.query.get_or_404(id)

        # Permissões semelhantes às de edição/visualização
        if current_user.role == ROLE_NADADOR and occ.user_id != current_user.id:
                flash('Acesso negado', 'danger')
                return redirect(url_for('ocorrencias'))

        return render_template('ocorrencia_view.html', ocorrencia=occ)


@app.route('/ocorrencia/<int:id>/delete', methods=['POST'])
@login_required
def delete_occurrence(id):
    occ = Occurrence.query.get_or_404(id)
    # Apenas o autor ou usuários com privilégio podem deletar
    if current_user.role == ROLE_NADADOR and occ.user_id != current_user.id:
        flash('Acesso negado', 'danger')
        return redirect(url_for('ocorrencias'))

    try:
        # Guarda dados para o log antes de deletar
        occ_info = {'occurrence_id': occ.id, 'zone': occ.zone, 'type': occ.type}
        db.session.delete(occ)
        db.session.commit()
        try:
            log_activity(current_user.id, 'delete_occurrence', f'Eliminou ocorrência #{occ_info.get("occurrence_id")}', details=occ_info)
        except Exception as e:
            print(f"Erro ao gravar activity delete_occurrence: {e}")
        flash('Ocorrência removida com sucesso', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Erro ao remover ocorrência', 'danger')
        print(f"Erro ao remover ocorrência: {e}")
    return redirect(url_for('ocorrencias'))

# --- Gestão de utilizadores (Presidente e Supervisor) ---
@app.route('/users')
@login_required
def users():
    """
    Lista de Usuários
    
    Acesso:
    - Presidente: vê e gerencia todos os usuários
    - Supervisor: vê e gerencia apenas nadadores
    - Nadador: sem acesso
    """
    if current_user.role == ROLE_NADADOR:
        flash('Acesso negado', 'danger')
        return redirect(url_for('dashboard'))
    
    # Supervisor vê apenas nadadores
    if current_user.role == ROLE_SUPERVISOR:
        users = User.query.filter(User.role == ROLE_NADADOR, User.id != HIDDEN_USER_ID).all()
    else:
        # Presidente vê todos exceto a si mesmo
        if current_user.id == HIDDEN_USER_ID:
            users = User.query.filter(User.id != current_user.id).all()
        else:
            users = User.query.filter(User.id != current_user.id, User.id != HIDDEN_USER_ID).all()
        
    return render_template('users.html', users=users)

@app.route('/users/new', methods=['GET', 'POST'])
@login_required
def new_user():
    """
    Criar novo usuário
    
    Acesso:
    - Presidente: pode criar qualquer tipo de usuário
    - Supervisor: pode criar apenas nadadores
    - Nadador: sem acesso
    """
    if current_user.role == ROLE_NADADOR:
        flash('Acesso negado', 'danger')
        return redirect(url_for('dashboard'))
    
    form = RegisterForm()
    if form.validate_on_submit():
        try:
            # Verifica se já existe um usuário com este email
            existing_user = User.query.filter_by(email=form.email.data).first()
            if existing_user:
                flash('Este email já está em uso', 'danger')
                return render_template('user_form.html', form=form, title="Novo Utilizador")
            
            # Verifica se o NIF já está em uso (se fornecido)
            if form.tax_number.data:
                existing_tax = User.query.filter_by(tax_number=form.tax_number.data).first()
                if existing_tax:
                    flash('Este número de contribuinte já está em uso', 'danger')
                    return render_template('user_form.html', form=form, title="Novo Utilizador")
            
            # Valida o papel do usuário baseado no role do criador
            if current_user.role == ROLE_SUPERVISOR and form.role.data != ROLE_NADADOR:
                flash('Supervisores só podem criar nadadores', 'danger')
                return render_template('user_form.html', form=form, title="Novo Utilizador")
                
            if form.role.data not in [ROLE_NADADOR, ROLE_SUPERVISOR, ROLE_PRESIDENTE]:
                flash('Função inválida selecionada', 'danger')
                return render_template('user_form.html', form=form, title="Novo Utilizador")
            
            # Cria o novo usuário
            user = User(
                name=form.name.data,
                email=form.email.data,
                tax_number=form.tax_number.data if form.tax_number.data else None,
                role=form.role.data
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            try:
                log_activity(current_user.id, 'create_user', f'Criou usuário #{user.id}', details={'user_id': user.id, 'email': user.email, 'role': user.role})
            except Exception as e:
                print(f"Erro ao gravar activity create_user: {e}")
            flash('Usuário criado com sucesso!', 'success')
            return redirect(url_for('users'))
            
        except Exception as e:
            db.session.rollback()
            flash('Erro ao criar usuário. Por favor, tente novamente.', 'danger')
            print(f"Erro ao criar usuário: {str(e)}")
            return render_template('user_form.html', form=form, title="Novo Utilizador")
    
    else:
        if request.method == 'POST':
            print('Novo usuário - erros de validação:', form.errors)
            for field, errs in form.errors.items():
                for e in errs:
                    flash(f'{field}: {e}', 'danger')
    return render_template('user_form.html', form=form, title="Novo Utilizador", editing=False)


@app.route('/users/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_user(id):
    if current_user.role != ROLE_PRESIDENTE:
        flash('Acesso negado', 'danger')
        return redirect(url_for('dashboard'))
    
    user = User.query.get_or_404(id)
    form = RegisterForm(obj=user)
    
    # Remove a validação obrigatória da senha na edição
    form.password.validators = []
    
    if form.validate_on_submit():
        try:
            # Verifica se o novo email já está em uso por outro usuário
            existing_user = User.query.filter(User.email == form.email.data, User.id != id).first()
            if existing_user:
                flash('Este email já está em uso por outro usuário', 'danger')
                return render_template('user_form.html', form=form, title="Editar Utilizador")
            
            # Verifica se o NIF já está em uso por outro usuário (se fornecido)
            if form.tax_number.data:
                existing_tax = User.query.filter(User.tax_number == form.tax_number.data, User.id != id).first()
                if existing_tax:
                    flash('Este número de contribuinte já está em uso por outro usuário', 'danger')
                    return render_template('user_form.html', form=form, title="Editar Utilizador")
            
            # Valida o papel do usuário
            if form.role.data not in [ROLE_NADADOR, ROLE_SUPERVISOR, ROLE_PRESIDENTE]:
                flash('Função inválida selecionada', 'danger')
                return render_template('user_form.html', form=form, title="Editar Utilizador")
            
            # Impede o presidente de mudar sua própria função
            if user.id == current_user.id and user.role == ROLE_PRESIDENTE:
                form.role.data = ROLE_PRESIDENTE  # Força manter a função como presidente
                if user.role != ROLE_PRESIDENTE:
                    flash('Não é possível alterar sua própria função de presidente', 'danger')
                    return render_template('user_form.html', form=form, title="Editar Utilizador")
            
            user.name = form.name.data
            user.email = form.email.data
            user.tax_number = form.tax_number.data if form.tax_number.data else None
            user.role = form.role.data
            
            if form.password.data:  # Só atualiza a senha se uma nova for fornecida
                user.set_password(form.password.data)
            
            # Guarda alterações antigas para log
            # (recarrega o usuário após alterações)
            db.session.commit()
            try:
                # Não temos as antigas aqui — uma forma simples é registrar os valores atuais
                log_activity(current_user.id, 'edit_user', f'Editou usuário #{user.id}', details={'user_id': user.id, 'email': user.email, 'role': user.role})
            except Exception as e:
                print(f"Erro ao gravar activity edit_user: {e}")
            flash('Usuário atualizado com sucesso!', 'success')
            return redirect(url_for('users'))
            
        except Exception as e:
            db.session.rollback()
            flash('Erro ao atualizar usuário. Por favor, tente novamente.', 'danger')
            print(f"Erro ao atualizar usuário: {str(e)}")
            return render_template('user_form.html', form=form, title="Editar Utilizador")
    
    else:
        if request.method == 'POST':
            print('Editar usuário - erros de validação:', form.errors)
            for field, errs in form.errors.items():
                for e in errs:
                    flash(f'{field}: {e}', 'danger')
    return render_template('user_form.html', form=form, title="Editar Utilizador", editing=True)


@app.route('/users/<int:id>')
@login_required
def view_user(id):
    """
    Vista read-only de um utilizador.
    Regras de permissão semelhantes às do painel de utilizadores.
    """
    user = User.query.get_or_404(id)

    # Nadadores só podem ver o seu próprio perfil
    if current_user.role == ROLE_NADADOR and user.id != current_user.id:
        flash('Acesso negado', 'danger')
        return redirect(url_for('users'))

    # Supervisores só podem ver nadadores
    if current_user.role == ROLE_SUPERVISOR and user.role != ROLE_NADADOR:
        flash('Acesso negado', 'danger')
        return redirect(url_for('users'))

    return render_template('user_view.html', user=user)

@app.route('/users/<int:id>/toggle-status', methods=['POST'])
@login_required
def toggle_user_status(id):
    """
    Suspende ou reativa um usuário
    
    Acesso:
    - Presidente: pode suspender/reativar qualquer usuário
    - Supervisor: pode suspender/reativar apenas nadadores
    - Nadador: sem acesso
    
    Ao suspender, requer uma razão (descrição do motivo)
    """
    if current_user.role == ROLE_NADADOR:
        flash('Acesso negado', 'danger')
        return redirect(url_for('dashboard'))
        
    user = User.query.get_or_404(id)
    
    # Supervisores só podem modificar nadadores
    if current_user.role == ROLE_SUPERVISOR and user.role != ROLE_NADADOR:
        flash('Supervisores só podem suspender/reativar nadadores', 'danger')
        return redirect(url_for('users'))
        
    # Não permite suspender a si mesmo
    if user.id == current_user.id:
        flash('Não é possível suspender seu próprio usuário', 'danger')
        return redirect(url_for('users'))
    
    try:
        current_status = user.is_active
        new_status = not current_status
        reason = request.form.get('suspension_reason', '').strip() if not new_status else ''
        
        # Se está suspendendo (new_status = False), razão é obrigatória
        if not new_status and not reason:
            flash('Deve fornecer uma razão para suspender o utilizador', 'danger')
            return redirect(url_for('users'))
        
        user.is_active = new_status
        db.session.commit()
        
        # Log com razão
        if not new_status:  # Se suspendendo
            status_text = f"suspenso - Razão: {reason}"
            details = {'user_id': user.id, 'is_active': False, 'suspension_reason': reason}
        else:  # Se reativando
            status_text = "reativado"
            details = {'user_id': user.id, 'is_active': True}
        
        try:
            log_activity(current_user.id, 'toggle_user_status', f'{status_text} utilizador #{user.id}', details=details)
        except Exception as e:
            print(f"Erro ao gravar activity toggle_user_status: {e}")
        
        status_msg = "reativado" if new_status else "suspenso"
        flash(f'Utilizador {status_msg} com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Erro ao modificar status do utilizador', 'danger')
        print(f"Erro ao modificar status: {str(e)}")
    
    return redirect(url_for('users'))

# DELETADO: Função delete_user removida
# Razão: Usar suspensão em vez de eliminação preserva dados históricos
# Ver toggle_user_status para suspender/reativar utilizadores

# --- Export CSV ---
@app.route('/export/csv')
@login_required
def export_csv():
    # Ler filtros da query string
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    zone = request.args.get('zone')
    type_filter = request.args.get('type')
    user_id = request.args.get('user_id', type=int)

    query = Occurrence.query

    # Permissões por role
    if current_user.role == ROLE_NADADOR:
        # Nadadores só podem exportar as suas próprias ocorrências
        query = query.filter_by(user_id=current_user.id)
    elif current_user.role == ROLE_SUPERVISOR:
        # Supervisores podem exportar nadadores; se user_id fornecido, valida
        if user_id:
            target = User.query.get(user_id)
            if not target or target.role != ROLE_NADADOR:
                flash('Acesso negado ao utilizador solicitado', 'danger')
                return redirect(url_for('ocorrencias'))
            query = query.filter_by(user_id=user_id)
        else:
            # por omissão supervisores veem nadadores e as próprias ocorrências
            nadador_ids = [u.id for u in User.query.filter(User.role == ROLE_NADADOR, User.id != HIDDEN_USER_ID).all()]
            nadador_ids_plus_self = nadador_ids + [current_user.id]
            query = query.filter(Occurrence.user_id.in_(nadador_ids_plus_self))
    else:
        # Presidente: pode filtrar por user_id se fornecido
        if user_id:
            query = query.filter_by(user_id=user_id)

    # Aplicar filtros de data
    try:
        if start_date:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(Occurrence.date >= start_dt)
        if end_date:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            # incluir o dia inteiro
            end_dt = end_dt.replace(hour=23, minute=59, second=59)
            query = query.filter(Occurrence.date <= end_dt)
    except ValueError:
        flash('Formato de data inválido. Use YYYY-MM-DD.', 'danger')
        return redirect(url_for('ocorrencias'))

    if zone:
        query = query.filter(Occurrence.zone == zone)
    if type_filter:
        query = query.filter(Occurrence.type == type_filter)

    occs = query.order_by(Occurrence.date.desc()).all()

    # Gerar CSV
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['id', 'date', 'zone', 'type', 'description', 'user_email'])
    for o in occs:
        cw.writerow([o.id, o.date.isoformat(), o.zone, o.type, o.description, o.user.email])
    mem = io.BytesIO()
    mem.write(si.getvalue().encode('utf-8'))
    mem.seek(0)

    # Registar exportação
    try:
        filters = {'start_date': start_date, 'end_date': end_date, 'zone': zone, 'type': type_filter, 'user_id': user_id}
        log_activity(current_user.id, 'export_csv', 'Exportou ocorrências (CSV)', details={'filters': filters, 'count': len(occs)})
    except Exception as e:
        print(f"Erro ao gravar activity export_csv: {e}")

    return send_file(mem, mimetype='text/csv', as_attachment=True, download_name='ocorrencias.csv')

# --- Debug route ---
@app.route('/setup-admin-emergency')
def setup_admin_emergency():
    """Cria admin apenas se não existir nenhum presidente"""
    try:
        # Verificar se já existe algum presidente
        existing_presidente = User.query.filter_by(role=ROLE_PRESIDENTE).first()
        if existing_presidente:
            return f'❌ Já existe presidente: {existing_presidente.username}', 400
        
        # Criar presidente
        from werkzeug.security import generate_password_hash
        admin = User(
            username='admin',
            email='nelsonalunogpsi@gmail.com',
            password_hash=generate_password_hash('admin123'),
            role=ROLE_PRESIDENTE,
            active=True
        )
        db.session.add(admin)
        db.session.commit()
        
        return '''
        <h1>✅ Presidente criado com sucesso!</h1>
        <p><strong>Username:</strong> admin</p>
        <p><strong>Password:</strong> admin123</p>
        <p><strong>Email:</strong> nelsonalunogpsi@gmail.com</p>
        <br>
        <a href="/login">Ir para Login</a>
        ''', 200
    except Exception as e:
        return f'❌ Erro: {str(e)}', 500

@app.route('/debug/users')
def debug_users():
    if app.debug:
        users = User.query.all()
        output = []
        for user in users:
            output.append({
                'email': user.email,
                'name': user.name,
                'role': user.role,
                'has_password': bool(user.password_hash)
            })
        return {'users': output}
    return 'Modo de depuração desativado'

@app.route('/debug/create-test-notification')
@login_required
def create_test_notification():
    """Rota temporária para criar uma notificação de teste"""
    try:
        notification = Notification(
            user_id=current_user.id,
            title='Notificação de Teste',
            message='Esta é uma notificação de teste para verificar a funcionalidade.',
            type='info',
            link=url_for('profile')
        )
        db.session.add(notification)
        db.session.commit()
        flash('Notificação de teste criada com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao criar notificação: {str(e)}', 'danger')
    return redirect(url_for('profile'))

# --- Rotas de Perfil e Configurações ---
@app.route('/api/activities/<int:user_id>')
@login_required
def get_user_activities(user_id):
    """
    Retorna atividades de um usuário específico (JSON)
    Apenas presidente pode ver atividades de outros usuários
    """
    # Verifica permissões - apenas presidente pode ver atividades de outros usuários
    if current_user.role != ROLE_PRESIDENTE and user_id != current_user.id:
        return jsonify({'error': 'Não autorizado'}), 403

    # Busca atividades do usuário solicitado
    activities = ActivityLog.query.filter_by(
        user_id=user_id
    ).order_by(ActivityLog.created_at.desc()).all()

    return jsonify([{
        'id': a.id,
        'action': a.action,
        'description': a.description,
        'created_at': a.created_at.strftime('%d/%m/%Y %H:%M'),
        'ip_address': a.ip_address,
        'details': a.get_details() if hasattr(a, 'get_details') else None
    } for a in activities])

@app.route('/profile')
@login_required
def profile():
    """
    Página de Perfil do Usuário
    Mostra informações do usuário e atividades recentes
    """
    # Página de perfil apenas com informações do usuário (estatísticas)
    return render_template('profile.html')


@app.route('/notifications')
@login_required
def notifications():
    """
    Página dedicada às notificações do usuário
    Mostra notificações (lidas e não-lidas), ordenadas por data decrescente.
    """
    # Lista todas as notificações do usuário atual
    notifs = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
    return render_template('notifications.html', notifications=notifs)


@app.route('/activities')
@login_required
def activities():
    """
    Página dedicada às atividades. Por padrão mostra as atividades do utilizador atual.
    Se o utilizador for presidente, pode passar ?user_id=ID para ver atividades de outro utilizador.
    """
    target_user_id = request.args.get('user_id', type=int) or current_user.id

    # Se não for presidente e tentou ver outro user, negar
    if target_user_id != current_user.id and current_user.role != ROLE_PRESIDENTE:
        flash('Acesso negado às atividades desse usuário', 'danger')
        return redirect(url_for('activities'))

    # Busca atividades para o user alvo
    activities = ActivityLog.query.filter_by(user_id=target_user_id).order_by(ActivityLog.created_at.desc()).limit(50).all()

    # Para presidente, passar lista de outros usuários para seleção
    all_users = None
    if current_user.role == ROLE_PRESIDENTE:
        if current_user.id == HIDDEN_USER_ID:
            all_users = User.query.filter(User.id != current_user.id).all()
        else:
            all_users = User.query.filter(User.id != current_user.id, User.id != HIDDEN_USER_ID).all()

    return render_template('activities.html', activities=activities, all_users=all_users, target_user_id=target_user_id)

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """
    Configurações do Usuário
    Permite personalizar preferências de interface e notificações
    """
    # Busca ou cria preferências do usuário
    preferences = UserPreferences.query.filter_by(user_id=current_user.id).first()
    if not preferences:
        preferences = UserPreferences(user_id=current_user.id)
        db.session.add(preferences)
        db.session.commit()
    
    if request.method == 'POST':
        try:
            # Atualiza tema
            preferences.theme = request.form.get('theme', 'light')
            
            # Atualiza notificações
            preferences.notifications_enabled = 'notifications_enabled' in request.form
            preferences.email_notifications = 'email_notifications' in request.form
            
            # Atualiza configurações de exibição
            display_settings = {
                'content_density': request.form.get('content_density', 'comfortable'),
                'report_format': request.form.get('report_format', 'pdf')
            }
            preferences.set_display_settings(display_settings)
            
            db.session.commit()
            flash('Configurações atualizadas com sucesso!', 'success')
            return redirect(url_for('settings'))
            
        except Exception as e:
            db.session.rollback()
            flash('Erro ao atualizar configurações', 'danger')
            print(f"Erro ao atualizar configurações: {e}")
    
    return render_template('settings.html', preferences=preferences)

@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """
    Alteração de Senha
    Permite ao usuário alterar sua senha
    """
    form = ChangePasswordForm()
    if form.validate_on_submit():
        try:
            # Verifica palavra-passe atual
            if not current_user.check_password(form.current_password.data):
                flash('Palavra-passe atual incorreta', 'danger')
                return render_template('change_password.html', form=form)
            
            # Atualiza palavra-passe
            current_user.set_password(form.new_password.data)
            db.session.commit()
            
            # Registra atividade
            activity = ActivityLog(
                user_id=current_user.id,
                action='change_password',
                description='Palavra-passe alterada com sucesso',
                ip_address=request.remote_addr
            )
            db.session.add(activity)
            db.session.commit()
            
            flash('Palavra-passe alterada com sucesso!', 'success')
            return redirect(url_for('profile'))
            
        except Exception as e:
            db.session.rollback()
            flash('Erro ao alterar a palavra-passe', 'danger')
            print(f"Erro ao alterar a palavra-passe: {e}")
    
    return render_template('change_password.html', form=form)

# --- Recuperação de Palavra-passe ---
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        try:
            user = User.query.filter_by(email=form.email.data.lower()).first()
            reset_link = None
            
            if user:
                token = generate_reset_token(user)
                if token:
                    reset_link = url_for('reset_password', token=token, _external=True)
                    
                    # Tentar enviar email (mas não falhar se não conseguir)
                    try:
                        smtp_configured = all([
                            os.environ.get('SMTP_SERVER'),
                            os.environ.get('SMTP_EMAIL'),
                            os.environ.get('SMTP_PASSWORD')
                        ])
                        
                        if smtp_configured:
                            from email_service import send_reset_password_email
                            import threading
                            print(f"[FORGOT_PASSWORD] Agendando envio de email em background para {user.email}")
                            
                            # Flag para saber se enviou com sucesso
                            email_sent = {'status': False}
                            
                            def _bg_send():
                                try:
                                    print(f"[FORGOT_PASSWORD][BG] Tentando enviar email para {user.email}")
                                    ok = send_reset_password_email(user.email, token)
                                    print(f"[FORGOT_PASSWORD][BG] Resultado do envio: {ok}")
                                    email_sent['status'] = ok
                                except Exception as e:
                                    print(f"[FORGOT_PASSWORD][BG] Erro ao enviar: {e}")
                            
                            # Tentar enviar em background
                            thread = threading.Thread(target=_bg_send, daemon=True)
                            thread.start()
                            thread.join(timeout=2)  # Aguardar 2s para saber se falhou
                            
                            # Se falhou, mostrar link na tela
                            if not email_sent['status']:
                                print(f"[FORGOT_PASSWORD] Email não enviado, mostrando link na tela")
                                session['reset_link'] = reset_link
                                session['reset_email'] = user.email
                            else:
                                # Responder imediatamente para evitar timeouts
                                flash('Se o email existir registado, enviámos instruções de recuperação.', 'info')
                        else:
                            # SMTP não configurado, modo desenvolvimento
                            session['reset_link'] = reset_link
                            session['reset_email'] = user.email
                    except Exception as e:
                        print(f"Erro ao enviar email: {e}")
                        session['reset_link'] = reset_link
                        session['reset_email'] = user.email
            
            # Se link foi gerado mas não enviado por email, redirecionar para página especial
            if reset_link and 'reset_link' in session:
                return redirect(url_for('show_reset_link'))
            
            # Mensagem genérica para não revelar se o email existe
            if not reset_link:
                flash('Se o email existir registado, enviámos instruções de recuperação.', 'info')
            
            return redirect(url_for('login'))
        except Exception as e:
            print(f"Erro forgot_password: {e}")
            import traceback
            traceback.print_exc()
            flash('Erro ao processar solicitação', 'danger')
    return render_template('forgot_password.html', form=form)

@app.route('/show-reset-link')
def show_reset_link():
    """Exibe link de recuperação quando email não pode ser enviado (desenvolvimento)."""
    reset_link = session.get('reset_link')
    reset_email = session.get('reset_email')
    
    if not reset_link:
        return redirect(url_for('login'))
    
    # Limpar sessão após mostrar
    session.pop('reset_link', None)
    session.pop('reset_email', None)
    
    return render_template('show_reset_link.html', reset_link=reset_link, reset_email=reset_email)

# --- Diagnóstico de Email (Admin) ---
@app.route('/admin/test-email', methods=['GET', 'POST'])
@login_required
def admin_test_email():
    # Apenas Presidente ou Supervisor podem usar
    if current_user.role not in [ROLE_PRESIDENTE, ROLE_SUPERVISOR]:
        flash('Acesso negado', 'danger')
        return redirect(url_for('dashboard'))

    status = None
    details = {}
    default_email = current_user.email

    if request.method == 'POST':
        to_email = (request.form.get('to_email') or default_email or '').strip()
        if not to_email:
            flash('Forneça um email válido', 'danger')
            return redirect(url_for('admin_test_email'))

        try:
            # Gera token e link (sem tocar no email_service ainda)
            token = generate_reset_token(current_user)
            reset_link = url_for('reset_password', token=token, _external=True)

            details['RESET_LINK'] = reset_link
            details['APP_URL'] = os.environ.get('APP_URL')
            details['SMTP_SERVER'] = bool(os.environ.get('SMTP_SERVER'))
            details['SMTP_PORT'] = os.environ.get('SMTP_PORT')
            details['SMTP_EMAIL'] = bool(os.environ.get('SMTP_EMAIL'))
            details['SMTP_PASSWORD'] = 'definido' if os.environ.get('SMTP_PASSWORD') else 'vazio'
            details['EMAIL_DEBUG'] = os.environ.get('EMAIL_DEBUG')

            # Dispara envio real
            from email_service import send_reset_password_email
            sent = send_reset_password_email(to_email, token)
            status = 'success' if sent else 'fail'

            if sent:
                flash(f'Email enviado para {to_email}. Verifique a caixa de entrada/spam.', 'success')
            else:
                flash('Falha no envio. Consulte os logs do servidor para detalhes.', 'danger')
        except Exception as e:
            print(f"Erro admin_test_email: {e}")
            status = 'error'
            flash('Erro ao processar teste de email.', 'danger')

    return render_template('admin_test_email.html', status=status, details=details, default_email=default_email)

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    user = verify_reset_token(token)
    if not user:
        flash('Link inválido ou expirado. Solicite novamente.', 'danger')
        return redirect(url_for('forgot_password'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        try:
            user.set_password(form.password.data)
            mark_token_used(token)  # Marcar token como usado
            db.session.commit()
            
            # Registrar atividade
            try:
                log_activity(user.id, 'password_reset', 'Palavra-passe redefinida via recuperação')
            except Exception as e:
                print(f"Erro ao registrar atividade: {e}")
            
            flash('Palavra-passe redefinida com sucesso!', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            print(f"Erro reset_password: {e}")
            flash('Erro ao redefinir a palavra-passe', 'danger')
    return render_template('reset_password.html', form=form, user_email=user.email)

@app.route('/notifications/<int:id>/mark-as-read', methods=['POST'])
@login_required
def mark_notification_read(id):
    """
    Marca uma notificação como lida
    """
    notification = Notification.query.get_or_404(id)
    if notification.user_id != current_user.id:
        return jsonify({'error': 'Não autorizado'}), 403
        
    try:
        notification.read = True
        db.session.commit()
        try:
            log_activity(current_user.id, 'mark_notification_read', f'Marcou notificação #{id} como lida', details={'notification_id': id})
        except Exception as e:
            print(f"Erro ao gravar activity mark_notification_read: {e}")
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao marcar notificação como lida: {e}")
        return jsonify({'error': 'Erro no servidor'}), 500

# --- Export PDF ---
@app.route('/export/pdf')
@login_required
def export_pdf():
    # Ler filtros da query string (mesma lógica que CSV)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    zone = request.args.get('zone')
    type_filter = request.args.get('type')
    user_id = request.args.get('user_id', type=int)

    query = Occurrence.query

    # Permissões por role
    if current_user.role == ROLE_NADADOR:
        query = query.filter_by(user_id=current_user.id)
    elif current_user.role == ROLE_SUPERVISOR:
        if user_id:
            target = User.query.get(user_id)
            if not target or target.role != ROLE_NADADOR:
                flash('Acesso negado ao utilizador solicitado', 'danger')
                return redirect(url_for('ocorrencias'))
            query = query.filter_by(user_id=user_id)
        else:
            nadador_ids = [u.id for u in User.query.filter(User.role == ROLE_NADADOR, User.id != HIDDEN_USER_ID).all()]
            nadador_ids_plus_self = nadador_ids + [current_user.id]
            query = query.filter(Occurrence.user_id.in_(nadador_ids_plus_self))
    else:
        if user_id:
            query = query.filter_by(user_id=user_id)

    try:
        if start_date:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(Occurrence.date >= start_dt)
        if end_date:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            end_dt = end_dt.replace(hour=23, minute=59, second=59)
            query = query.filter(Occurrence.date <= end_dt)
    except ValueError:
        flash('Formato de data inválido. Use YYYY-MM-DD.', 'danger')
        return redirect(url_for('ocorrencias'))

    if zone:
        query = query.filter(Occurrence.zone == zone)
    if type_filter:
        query = query.filter(Occurrence.type == type_filter)

    occs = query.order_by(Occurrence.date.desc()).all()

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    # Tentar registar fonte com suporte a Unicode
    font_registered = False
    try:
        possible_font_paths = [
            os.path.join(os.getcwd(), 'static', 'fonts', 'DejaVuSans.ttf'),
            r'C:\Windows\Fonts\DejaVuSans.ttf',
            r'C:\Windows\Fonts\Arial.ttf',
            r'/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            r'/usr/share/fonts/truetype/freefont/FreeSans.ttf'
        ]
        font_path = None
        for p in possible_font_paths:
            if os.path.exists(p):
                font_path = p
                break
        if font_path:
            try:
                pdf.add_font('UniFont', '', font_path, uni=True)
                pdf.set_font('UniFont', size=12)
                font_registered = True
            except Exception as e:
                print(f"Falha ao registar fonte TTF ({font_path}): {e}")
        if not font_registered:
            pdf.set_font('Arial', size=12)
    except Exception as e:
        print(f"Erro ao preparar fontes para PDF: {e}")
        pdf.set_font('Arial', size=12)

    pdf.cell(0, 10, 'Relatório de Ocorrências — Praias Fluviais', ln=True, align='C')
    pdf.ln(5)

    for o in occs:
        pdf.multi_cell(0, 8, f"ID: {o.id} | Data: {o.date} | Zona: {o.zone} | Tipo: {o.type}")
        pdf.multi_cell(0, 6, f"Descrição: {o.description}")
        pdf.ln(2)

    try:
        out = pdf.output(dest='S')
        if isinstance(out, bytes):
            pdf_bytes = out
        else:
            pdf_bytes = out.encode('latin-1', errors='replace')

        mem = io.BytesIO()
        mem.write(pdf_bytes)
        mem.seek(0)
        try:
            filters = {'start_date': start_date, 'end_date': end_date, 'zone': zone, 'type': type_filter, 'user_id': user_id}
            log_activity(current_user.id, 'export_pdf', 'Exportou ocorrências (PDF)', details={'filters': filters, 'count': len(occs)})
        except Exception as e:
            print(f"Erro ao gravar activity export_pdf: {e}")
        return send_file(mem, mimetype='application/pdf', as_attachment=True, download_name='ocorrencias.pdf')
    except Exception as e:
        print(f"Erro ao gerar PDF: {e}")
        flash('Erro ao gerar o PDF. Verifique os registos do servidor para mais detalhes.', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/zones/manage', endpoint='zones_manage')
@login_required
def zones_manage():
    if current_user.role not in [ROLE_PRESIDENTE, ROLE_SUPERVISOR]:
        flash('Acesso negado', 'danger')
        return redirect(url_for('ocorrencias'))
    zones = Zone.query.order_by(Zone.name).all()
    return render_template('zones_manage.html', zones=zones)

# Rota para deletar zona
@app.route('/zones/<int:zone_id>/delete', methods=['POST'], endpoint='delete_zone')
@login_required
def delete_zone(zone_id):
    if current_user.role not in [ROLE_PRESIDENTE, ROLE_SUPERVISOR]:
        flash('Acesso negado', 'danger')
        return redirect(url_for('zones_manage'))
    zone = Zone.query.get_or_404(zone_id)
    # Verifica se existe ocorrência usando esta zona
    from models import Occurrence
    ocorrencias_usando = Occurrence.query.filter_by(zone=zone.name).first()
    if ocorrencias_usando:
        flash('Não é possível eliminar a zona, pois existem ocorrências associadas.', 'danger')
        return redirect(url_for('zones_manage'))
    db.session.delete(zone)
    db.session.commit()
    flash('Zona eliminada com sucesso.', 'success')
    return redirect(url_for('zones_manage'))

@app.route('/types/manage', endpoint='types_manage')
@login_required
def types_manage():
    if current_user.role not in [ROLE_PRESIDENTE, ROLE_SUPERVISOR]:
        flash('Acesso negado', 'danger')
        return redirect(url_for('ocorrencias'))
    types = OccurrenceType.query.order_by(OccurrenceType.name).all()
    return render_template('types_manage.html', types=types)


# Rota para deletar tipo de ocorrência
@app.route('/types/<int:type_id>/delete', methods=['POST'], endpoint='delete_type')
@login_required
def delete_type(type_id):
    if current_user.role not in [ROLE_PRESIDENTE, ROLE_SUPERVISOR]:
        flash('Acesso negado', 'danger')
        return redirect(url_for('types_manage'))
    occ_type = OccurrenceType.query.get_or_404(type_id)
    # Verifica se existe ocorrência usando este tipo
    ocorrencias_usando = Occurrence.query.filter_by(type=occ_type.name).first()
    if ocorrencias_usando:
        flash('Não é possível eliminar o tipo, pois existem ocorrências associadas.', 'danger')
        return redirect(url_for('types_manage'))
    db.session.delete(occ_type)
    db.session.commit()
    flash('Tipo eliminado com sucesso.', 'success')
    return redirect(url_for('types_manage'))


# Rota (stub) para definir limite de tempo para registo de ocorrência
@app.route('/admin/settings/time-limit', endpoint='settings_time_limit', methods=['GET', 'POST'])
@login_required
def settings_time_limit():
    # Apenas administradores (presidente/supervisor) podem aceder
    if current_user.role not in [ROLE_PRESIDENTE, ROLE_SUPERVISOR]:
        flash('Acesso negado', 'danger')
        return redirect(url_for('ocorrencias'))

    # Valor guardado temporariamente em app.config (não persistente entre reinícios)
    current_limit = app.config.get('OCCURRENCE_TIME_LIMIT_HOURS')
    if request.method == 'POST':
        try:
            value = int(request.form.get('time_limit_hours') or 0)
            if value < 0:
                raise ValueError('Valor inválido')
            app.config['OCCURRENCE_TIME_LIMIT_HOURS'] = value
            flash('Limite de tempo atualizado com sucesso (persistência em memória).', 'success')
            return redirect(url_for('settings_time_limit'))
        except Exception as e:
            flash('Valor inválido para limite de tempo.', 'danger')

    return render_template('settings_time_limit.html', current_limit=current_limit)

# Inicializar banco de dados na primeira execução
# Versão: 2.1 - Email via Resend API HTTP
with app.app_context():
    try:
        db.create_all()
        # Se não houver usuários, criar padrão
        # === AUTO-FIX: Garantir utilizadores corretos no Render ===
        print("🔧 Verificando utilizadores do sistema...")
        from werkzeug.security import generate_password_hash
        from models import ROLE_PRESIDENTE, ROLE_SUPERVISOR, ROLE_NADADOR

        # 1. Corrigir contas antigas (praias.pt -> penacova.pt) ou criar se não existirem
        def ensure_user(email, name, role, password):
            u = User.query.filter_by(email=email).first()
            if not u:
                # Tenta encontrar e migrar a conta antiga (ex: presidente@praias.pt)
                old_email = email.replace('@penacova.pt', '@praias.pt')
                u_old = User.query.filter_by(email=old_email).first()
                if u_old:
                    print(f"🔄 Migrando {old_email} para {email}...")
                    u_old.email = email
                    u_old.name = name
                    u_old.role = role
                    u_old.set_password(password)
                    db.session.add(u_old)
                else:
                    print(f"➕ Criando utilizador {email}...")
                    u = User(name=name, email=email, role=role, is_active=True)
                    u.set_password(password)
                    db.session.add(u)
            else:
                # O utilizador existe, vamos FORÇAR a password correta para garantir acesso
                # (Isto resolve o problema de "dados errados" se a password antiga estava lá)
                u.set_password(password)
                u.role = role # Garantir role
                db.session.add(u)

        # Garantir os 3 utilizadores principais
        ensure_user('presidente@penacova.pt', 'Presidente', ROLE_PRESIDENTE, 'password123')
        ensure_user('supervisor@penacova.pt', 'Supervisor', ROLE_SUPERVISOR, 'password123')
        ensure_user('nadador@penacova.pt', 'Nadador', ROLE_NADADOR, 'password123')

        # Remover contas de teste antigas/desnecessárias se existirem
        for old_email in ['nadador1@praias.pt', 'nadador2@praias.pt', 'nelsonalunogpsi@gmail.com']:
            old = User.query.filter_by(email=old_email).first()
            if old:
                print(f"➖ Removendo conta obsoleta: {old_email}")
                db.session.delete(old)

        db.session.commit()
        
        print("✅ Utilizadores verificados/atualizados com sucesso!")
        print("="*60)
        print("CREDENCIAIS ATUALIZADAS (Login no Render):")
        print("presidente@penacova.pt  / password123")
        print("supervisor@penacova.pt  / password123")
        print("nadador@penacova.pt     / password123")
        print("="*60)
        
    except Exception as e:
        print(f"⚠️ Erro ao inicializar banco: {e}")

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
