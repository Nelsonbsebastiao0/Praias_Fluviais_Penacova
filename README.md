# Praias Fluviais - Sistema de Gestão de Ocorrências
Sistema web de gestão de ocorrências em praias fluviais, desenvolvido em Flask com suporte a SQLite (desenvolvimento) e MySQL/MariaDB (produção).

## 📋 Requisitos

- **Python 3.10+**
- **pip** (gerenciador de pacotes Python)
- **Git** (para controle de versão)
- **MySQL/MariaDB** (opcional, apenas para produção)

## 🚀 Setup Inicial (Desenvolvimento)

### 1. Clonar o repositório

```bash
git clone https://github.com/seu-usuario/praias_fluviais.git
cd praias_fluviais
```

### 2. Criar ambiente virtual

**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Linux/macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar dependências

```bash
pip install -r requirements.txt
```

### 4. Inicializar a base de dados

**Opção A: Criar e seeder dados de exemplo**
```bash
python seed.py
```

**Opção B: Criar manualmente**
```bash
python
>>> from app import app, db
>>> with app.app_context():
...     db.create_all()
>>> exit()
```

### 5. Executar a aplicação

**Windows:**
```powershell
python app.py
```

**Linux/macOS:**
```bash
bash run.sh
```

A aplicação estará disponível em `http://localhost:5000`

## 🔐 Contas de Teste

| Email | Senha | Função |
|-------|-------|--------|
| nadador@penacova.pt | password123 | Nadador |
| supervisor@penacova.pt | password123 | Supervisor |
| presidente@penacova.pt | password123 | Presidente (Admin) |

> **⚠️ Segurança:** Altere as senhas em produção e remova/desative estas contas!

## 📁 Estrutura do Projeto

```
praias_fluviais/
├── app.py                      # Aplicação Flask (31+ rotas)
├── config.py                   # Configuração (suporta env vars)
├── models.py                   # Modelos SQLAlchemy (7 tabelas)
├── forms.py                    # Formulários WTForms
├── requirements.txt            # Dependências Python
├── seed.py                     # Script para popular dados de exemplo
├── migrate_to_mysql.py         # Script de migração SQLite → MySQL
├── run.sh                      # Script para executar em Linux/macOS
├── instance/
│   └── praias.db               # Base de dados SQLite (desenvolvimento)
├── templates/
│   ├── base.html               # Template principal
│   ├── dashboard.html          # Dashboard com gráficos
│   ├── login.html              # Página de login
│   ├── ocorrencia_form.html    # Criar/editar ocorrência
│   ├── ocorrencias.html        # Listar ocorrências (com filtros/export)
│   ├── users.html              # Gestão de utilizadores (admin)
│   ├── activities.html         # Registo de atividades (auditoria)
│   ├── settings_time_limit.html # Configurações de tempo limite (admin)
│   ├── zones_manage.html       # Gestão de zonas (admin)
│   ├── types_manage.html       # Gestão de tipos de ocorrência (admin)
│   ├── zones_form.html         # Formulário para criar/editar zona
│   ├── types_form.html         # Formulário para criar/editar tipo
│   └── ... (outros templates)
├── static/
│   ├── css/
│   │   └── tweaks.css          # Estilos customizados
│   └── ... (imagens, ícones)
├── .gitignore                  # Ficheiros ignorados por Git
└── README.md                   # Este ficheiro
```

## 🗄️ Base de Dados

### Tabelas Principais (SQLAlchemy)

1. **User** - Utilizadores do sistema
	 - Campos: id, username, email, password_hash, role, is_active, created_at
	 - Papéis: `nadador`, `supervisor`, `presidente`
	 - Relações: ActivityLog, Occurrence, Notification, Zone, OccurrenceType

2. **UserPreferences** - Preferências do utilizador
	 - Campos: id, user_id, preferences (JSON)
	 - Armazena configurações personalizadas por utilizador

3. **Occurrence** - Ocorrências registadas
	 - Campos: id, user_id, zone_id, type_id, date, time, location, description, status, created_at
	 - Status: pending, approved, rejected
	 - Relações: User, Zone, OccurrenceType

4. **Zone** - Zonas de água (praias fluviais)
	 - Campos: id, name, location, user_id (criador), created_at
	 - Relações: User, Occurrence

5. **OccurrenceType** - Tipos de ocorrência
	 - Campos: id, name, description, user_id (criador), created_at
	 - Exemplos: resgate, afogamento, incidente
	 - Relações: User, Occurrence

6. **ActivityLog** - Registo de atividades (auditoria)
	 - Campos: id, user_id, action, details (JSON), timestamp
	 - Rastreia TODAS as ações dos utilizadores
	 - Relações: User

7. **Notification** - Notificações para utilizadores
	 - Campos: id, user_id, message, is_read, created_at
	 - Enviadas automaticamente em aprovações/rejeições
	 - Relações: User

### Diagrama de Relações

```
User (1) ──── (N) Occurrence
	│
	├─── (1) ──── (N) ActivityLog
	├─── (1) ──── (N) Notification
	├─── (1) ──── (N) Zone
	└─── (1) ──── (N) OccurrenceType

Zone (1) ──── (N) Occurrence
OccurrenceType (1) ──── (N) Occurrence
```

### Desenvolvimento: SQLite

Por padrão, a aplicação usa **SQLite** em `instance/praias.db`. Perfeito para desenvolvimento local:

```python
# config.py (padrão)
SQLALCHEMY_DATABASE_URI = 'sqlite:///praias.db'
```

**Vantagens:**
- ✅ Sem dependências externas
- ✅ Fácil de resetar (apenas eliminar ficheiro .db)
- ✅ Ideal para testes e desenvolvimento

**Limitações:**
- ❌ Sem suporte a concorrência
- ❌ Não adequado para produção com múltiplos utilizadores
- ❌ Backups manuais necessários

### Produção: MySQL/MariaDB

Para produção, configure a variável de ambiente `DATABASE_URL`:

```bash
# Variável de ambiente
export DATABASE_URL="mysql+pymysql://user:password@localhost:3306/praias_db"
python app.py
```

Ou no ficheiro `.env` (nunca commitar):
```
DATABASE_URL=mysql+pymysql://praias_user:senha_forte@localhost:3306/praias_db
SECRET_KEY=sua-chave-secreta-muito-longa-e-aleatoria
FLASK_ENV=production
```

**Vantagens:**
- ✅ Suporte a múltiplos utilizadores simultâneos
- ✅ Melhor desempenho
- ✅ Backups automatizados
- ✅ Replicação de dados

## 🛠️ Funcionalidades por Papel

### 👤 Nadador
- ✅ Registar novas ocorrências (com zona, tipo, descrição, localização, data/hora)
- ✅ Ver histórico das suas ocorrências
- ✅ Editar ocorrências (antes de aprovação)
- ✅ Eliminar ocorrências próprias
- ✅ Consultar dashboard com estatísticas pessoais
- ✅ Receber notificações de aprovação/rejeição
- ✅ Ver outras ocorrências (leitura)

### 👮 Supervisor
- ✅ **Todas as funcionalidades do nadador**
- ✅ Aprovar/rejeitar ocorrências de outros nadadores
- ✅ Ver todas as ocorrências do sistema
- ✅ Gerar relatórios (CSV, PDF)
- ✅ Filtrar ocorrências (por zona, tipo, data, status)
- ✅ Ver registo de atividades (auditoria)
- ✅ Dashboard com estatísticas globais

### 👨‍💼 Presidente (Admin)
- ✅ **Todas as funcionalidades de supervisor**
- ✅ Gestão completa de utilizadores (criar, editar, ativar/desativar)
- ✅ Gestão de zonas (CRUD completo)
- ✅ Gestão de tipos de ocorrência (CRUD completo)
- ✅ Configurações do sistema (tempo limite de aprovação, etc.)
- ✅ Visualização de registo de atividades detalhado
- ✅ Gestão de notificações

## 🗺️ Rotas Principais

### Autenticação & Navegação
- `GET /` - Página inicial (redireciona para dashboard ou login)
- `GET /login` - Página de login
- `POST /login` - Processar login
- `GET /logout` - Logout
- `POST /register` - Registar novo utilizador
- `GET /dashboard` - Dashboard principal com gráficos

### Ocorrências (CRUD)
- `GET /ocorrencias` - Listar ocorrências com filtros
- `POST /ocorrencias` - Criar nova ocorrência
- `GET /ocorrencia/<id>` - Ver detalhes de ocorrência
- `POST /ocorrencia/<id>` - Editar ocorrência
- `POST /ocorrencia/<id>/delete` - Eliminar ocorrência
- `POST /ocorrencia/<id>/approve` - Aprovar (supervisor+)
- `POST /ocorrencia/<id>/reject` - Rejeitar (supervisor+)

### Exportação
- `GET /ocorrencia/export/csv` - Exportar como CSV
- `GET /ocorrencia/export/pdf` - Exportar como PDF
- Modal de export (download tudo ou adicionar filtros)

### Utilizadores (Admin)
- `GET /users` - Listar utilizadores
- `POST /user/create` - Criar novo utilizador
- `POST /user/<id>/edit` - Editar utilizador
- `POST /user/<id>/delete` - Eliminar utilizador
- `GET /user/<id>` - Ver perfil de utilizador

### Gestão de Zonas (Admin)
- `GET /admin/zones` - Listar zonas
- `GET /admin/zone/form` - Formulário de criar zona
- `POST /admin/zone/create` - Criar zona
- `POST /admin/zone/<id>/edit` - Editar zona
- `POST /admin/zone/<id>/delete` - Eliminar zona

### Gestão de Tipos (Admin)
- `GET /admin/types` - Listar tipos
- `GET /admin/type/form` - Formulário de criar tipo
- `POST /admin/type/create` - Criar tipo
- `POST /admin/type/<id>/edit` - Editar tipo
- `POST /admin/type/<id>/delete` - Eliminar tipo

### Configurações (Admin)
- `GET /settings/time_limit` - Configurar tempo limite de aprovação
- `POST /settings/time_limit` - Guardar configurações

### Auditoria & Notificações
- `GET /activities` - Registo de atividades (ActivityLog)
- `GET /notifications` - Centro de notificações
- `POST /notification/<id>/read` - Marcar notificação como lida

## 🔄 Migração de SQLite para MySQL

Quando estiver pronto para migrar para produção:

### 1. Preparar servidor MySQL

```bash
mysql -u root -p
```

```sql
-- Criar base de dados
CREATE DATABASE praias_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Criar utilizador dedicado
CREATE USER 'praias_user'@'localhost' IDENTIFIED BY 'senha_forte_aqui';

-- Conceder permissões
GRANT ALL PRIVILEGES ON praias_db.* TO 'praias_user'@'localhost';
FLUSH PRIVILEGES;

-- Sair
EXIT;
```

### 2. Instalar dependência MySQL

```bash
pip install pymysql
```

### 3. Executar script de migração

```bash
python migrate_to_mysql.py
```

O script automaticamente:
- ✅ Lê todos os dados do SQLite
- ✅ Cria schema completo no MySQL
- ✅ Insere todos os registos preservando integridade de chaves estrangeiras
- ✅ Valida contagem de registos
- ✅ Apresenta relatório final

### 4. Configurar variável de ambiente

```bash
export DATABASE_URL="mysql+pymysql://praias_user:senha_forte_aqui@localhost:3306/praias_db"
python app.py
```

### 5. Eliminar ou fazer backup do SQLite (opcional)

```bash
# Backup
cp instance/praias.db instance/praias.db.backup

# Ou eliminar se tiver a certeza
rm instance/praias.db
```

## 🚢 Deployment em Produção

### Opção 1: Servidor Linux com Gunicorn

```bash
# Instalar Gunicorn
pip install gunicorn

# Executar (4 workers)
gunicorn -w 4 -b 0.0.0.0:5000 app:app

# Com ficheiro de configuração
gunicorn --config gunicorn_config.py app:app
```

### Opção 2: Docker

**Dockerfile:**
```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y gcc

# Copiar requirements e instalar
COPY requirements.txt .
RUN pip install -r requirements.txt gunicorn pymysql

# Copiar código
COPY . .

# Variáveis de ambiente
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

# Exposar porta
EXPOSE 5000

# Executar
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
```

**docker-compose.yml:**
```yaml
version: '3.8'

services:
	db:
		image: mariadb:latest
		environment:
			MYSQL_ROOT_PASSWORD: root_password
			MYSQL_DATABASE: praias_db
			MYSQL_USER: praias_user
			MYSQL_PASSWORD: user_password
		volumes:
			- db_data:/var/lib/mysql
		ports:
			- "3306:3306"

	web:
		build: .
		environment:
			DATABASE_URL: mysql+pymysql://praias_user:user_password@db:3306/praias_db
			SECRET_KEY: sua-chave-secreta-aqui
			FLASK_ENV: production
		ports:
			- "5000:5000"
		depends_on:
			- db

volumes:
	db_data:
```

### Variáveis de Ambiente Obrigatórias

```bash
# Chave secreta para Flask (gerar com: python -c "import secrets; print(secrets.token_hex(32))")
SECRET_KEY=seu-token-aleatorio-muito-longo-aqui

# Conexão à base de dados (MySQL em produção)
DATABASE_URL=mysql+pymysql://praias_user:senha_forte@host:3306/praias_db

# Modo Flask
FLASK_ENV=production
```

### Checklist de Deployment

- [ ] Alterar `SECRET_KEY` para valor aleatório único
- [ ] Migrar de SQLite para MySQL (usar `migrate_to_mysql.py`)
- [ ] Testar migração em ambiente de staging
- [ ] Configurar backups automáticos da base de dados
- [ ] Verificar HTTPS (usar reverse proxy com Nginx/Apache)
- [ ] Configurar rate limiting (Flask-Limiter)
- [ ] Configurar logging centralizado
- [ ] Testar com múltiplos utilizadores simultâneos
- [ ] Monitorar performance e uptime
- [ ] Ter plano de rollback em caso de falha

## 🔒 Segurança

### Implementado
- ✅ **Hashing de senhas:** Werkzeug `generate_password_hash()` e `check_password_hash()`
- ✅ **Proteção CSRF:** Flask-WTF em todos os formulários
- ✅ **Reauthentication:** Função `reauthenticate_if_needed()` para ações sensíveis
- ✅ **Controlo de acesso:** Decoradores `@login_required` e `@admin_required`
- ✅ **Auditoria:** ActivityLog rastreia TODAS as ações
- ✅ **Segurança de sessão:** Flask-Login com timeout seguro

### Boas Práticas
- ❌ Nunca armazene `SECRET_KEY` no código
- ❌ Nunca commite ficheiros `.env`
- ✅ Use HTTPS em produção
- ✅ Implemente rate limiting
- ✅ Faça backups regulares
- ✅ Mantenha dependências atualizadas

## 📝 RGPD / Privacidade

Este sistema foi desenvolvido com conformidade RGPD em mente:

### Dados Recolhidos
- Nome de utilizador
- Email
- Função/papel no sistema
- Ocorrências registadas (com localização e descrição)
- Registo de atividades (auditoria)

### Dados NÃO Recolhidos
- ❌ Imagens ou vídeos
- ❌ Dados de localização em tempo real
- ❌ Informações de saúde sensíveis

### Direitos do Utilizador
- ✅ Direito ao esquecimento (eliminação de conta)
- ✅ Portabilidade de dados (exportar como CSV)
- ✅ Acesso aos seus dados pessoais
- ✅ Controlo de notificações

### Responsável de Dados
Para questões de privacidade, contacte: **[seu-email@dominio.pt]**

### Termos de Serviço
[A agregar texto dos termos de serviço específicos da sua organização]

## 🐛 Troubleshooting

### "ModuleNotFoundError: No module named 'flask'"

```bash
pip install -r requirements.txt
```

### "sqlite3.OperationalError: no such table: user"

Base de dados vazia. Executar:

```bash
python seed.py
# ou
python
>>> from app import app, db
>>> with app.app_context():
...     db.create_all()
>>> exit()
```

### "ModuleNotFoundError: No module named 'pymysql'"

Instalar para migração MySQL:
```bash
pip install pymysql
```

### "ConnectionError: Unable to connect to database"

Verificar:
- ✅ MySQL/MariaDB está a correr?
- ✅ Credenciais em `DATABASE_URL` corretas?
- ✅ Base de dados `praias_db` existe?
- ✅ Firewall permite conexão na porta 3306?

```bash
# Testar conexão
mysql -u praias_user -p -h localhost praias_db
```

### Porta 5000 já em uso

**Windows:**
```powershell
netstat -ano | findstr :5000
taskkill /PID <PID> /F
```

**Linux/macOS:**
```bash
lsof -i :5000
kill -9 <PID>
```

Ou usar porta diferente:
```bash
python app.py --port 5001
```

### Ficheiros estáticos não carregam (CSS, JavaScript)

Limpar cache e reconstruir:
```bash
# Eliminar cache
rm -rf __pycache__ static/.webassets-cache

# Aceder com refresh forçado (Ctrl+Shift+R ou Cmd+Shift+R)
```

### Erros de timeout no export de PDF

Aumentar timeout em `app.py`:
```python
PDF_TIMEOUT = 30  # segundos
```

---

## 📧 Recuperação de Palavra-passe (Email)

### Desenvolvimento (Localhost)

O sistema funciona **sem configuração de email**:
- Link de recuperação aparece diretamente na tela
- Perfeito para testes locais
- Não precisa configurar SMTP

### Produção (Render/Servidor)

Para enviar emails automaticamente, configure variáveis de ambiente:

```bash
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_EMAIL=seu-email@gmail.com
SMTP_PASSWORD=sua-senha-de-app
APP_NAME=Praias Fluviais
APP_URL=https://seu-app.onrender.com
```

**Guias Detalhados:**
- 📘 `CONFIGURAR_EMAIL_RENDER.md` - Como configurar email no Render
- 📘 `EMAIL_SERVICE_README.md` - Documentação completa do módulo
- 📘 `RECUPERACAO_RESOLVIDA.md` - Guia de teste do sistema

**Provedores Recomendados:**
- **Gmail** (teste): Senha de app grátis
- **SendGrid** (produção): 100 emails/dia grátis
- **Mailgun** (alternativa): 5000 emails/mês

### Testar Localmente

```powershell
# Configurar SMTP (opcional)
.\configure_smtp.ps1

# Testar envio
python test_email_quick.py

# Iniciar app
python app.py
```

---

## 📧 Contacto & Suporte

Para reportar bugs ou sugerir melhorias, crie uma issue no GitHub:

```
https://github.com/seu-usuario/praias_fluviais/issues
```

Ou contacte: **[seu-email@dominio.pt]**

## 📄 Licença

Propriedade privada. Todos os direitos reservados.

---

**Versão:** 1.2.0  
**Data de Atualização:** Dezembro de 2025  
**Desenvolvedor:** [Seu Nome]  
**Compatibilidade:** Python 3.10+, Flask 2.0+, SQLite/MySQL

