"""
Serviço de Envio de Emails
===========================

Módulo responsável pelo envio de emails transacionais do sistema,
incluindo confirmação de conta e redefinição de senha.

Tecnologias:
- smtplib: Envio de emails via SMTP
- email.mime: Formatação de emails HTML/Text
- os: Variáveis de ambiente para configuração

Configuração:
Defina as seguintes variáveis de ambiente:
- SMTP_SERVER: Servidor SMTP (ex: smtp.gmail.com)
- SMTP_PORT: Porta SMTP (587 para TLS, 465 para SSL)
- SMTP_EMAIL: Email remetente
- SMTP_PASSWORD: Senha ou app password
- APP_NAME: Nome da aplicação (ex: Praias Fluviais)
- APP_URL: URL base da aplicação
"""

import smtplib
import os
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

# Configurações do SMTP (via variáveis de ambiente)
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_EMAIL = os.getenv('SMTP_EMAIL', '')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
APP_NAME = os.getenv('APP_NAME', 'Praias Fluviais')
APP_URL = os.getenv('APP_URL', 'http://localhost:5000')
EMAIL_DEBUG = os.getenv('EMAIL_DEBUG') == '1'
USE_RESEND_API = os.getenv('USE_RESEND_API') == '1' or SMTP_EMAIL == 'resend'
# Lista de emails permitidos no Resend (separados por vírgula)
ALLOWED_EMAILS = [e.strip() for e in os.getenv('ALLOWED_EMAILS', 'nelsonalunogpsi@gmail.com').split(',') if e.strip()]


def _debug_log(msg: str) -> None:
    if EMAIL_DEBUG:
        print(f"[EMAIL_DEBUG] {msg}")


def _get_html_template(title: str, greeting: str, message: str, button_text: str, button_link: str, footer_note: str = "") -> str:
    """
    Template HTML base para emails (design responsivo e anti-spam)
    
    Args:
        title: Título do email
        greeting: Saudação inicial
        message: Corpo da mensagem
        button_text: Texto do botão CTA
        button_link: Link do botão
        footer_note: Nota adicional no rodapé
    
    Returns:
        String HTML formatada
    """
    return f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f7f9;">
    <table role="presentation" style="width: 100%; border-collapse: collapse; background-color: #f4f7f9;">
        <tr>
            <td align="center" style="padding: 40px 0;">
                <!-- Container Principal -->
                <table role="presentation" style="width: 600px; max-width: 100%; border-collapse: collapse; background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    
                    <!-- Header com Logo -->
                    <tr>
                        <td style="padding: 40px 40px 20px; text-align: center; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 8px 8px 0 0;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 600; letter-spacing: -0.5px;">
                                🌊 {APP_NAME}
                            </h1>
                            <p style="margin: 8px 0 0; color: #e0e7ff; font-size: 14px;">Sistema de Gestão de Ocorrências</p>
                        </td>
                    </tr>
                    
                    <!-- Corpo do Email -->
                    <tr>
                        <td style="padding: 40px;">
                            <!-- Título -->
                            <h2 style="margin: 0 0 16px; color: #1f2937; font-size: 24px; font-weight: 600;">
                                {title}
                            </h2>
                            
                            <!-- Saudação -->
                            <p style="margin: 0 0 24px; color: #4b5563; font-size: 16px; line-height: 1.6;">
                                {greeting}
                            </p>
                            
                            <!-- Mensagem Principal -->
                            <p style="margin: 0 0 32px; color: #4b5563; font-size: 16px; line-height: 1.6;">
                                {message}
                            </p>
                            
                            <!-- Botão CTA -->
                            <table role="presentation" style="width: 100%; border-collapse: collapse;">
                                <tr>
                                    <td align="center" style="padding: 0;">
                                        <a href="{button_link}" 
                                           style="display: inline-block; padding: 16px 48px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #ffffff; text-decoration: none; font-size: 16px; font-weight: 600; border-radius: 6px; box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4); transition: all 0.3s ease;">
                                            {button_text}
                                        </a>
                                    </td>
                                </tr>
                            </table>
                            
                            <!-- Link alternativo -->
                            <p style="margin: 24px 0 0; color: #6b7280; font-size: 14px; line-height: 1.6; text-align: center;">
                                Ou copie e cole este link no seu navegador:<br>
                                <a href="{button_link}" style="color: #667eea; text-decoration: none; word-break: break-all;">
                                    {button_link}
                                </a>
                            </p>
                            
                            <!-- Nota adicional -->
                            {f'<p style="margin: 24px 0 0; padding: 16px; background-color: #fef3c7; border-left: 4px solid #f59e0b; color: #92400e; font-size: 14px; line-height: 1.6; border-radius: 4px;">{footer_note}</p>' if footer_note else ''}
                        </td>
                    </tr>
                    
                    <!-- Rodapé -->
                    <tr>
                        <td style="padding: 32px 40px; background-color: #f9fafb; border-radius: 0 0 8px 8px; border-top: 1px solid #e5e7eb;">
                            <p style="margin: 0 0 8px; color: #6b7280; font-size: 14px; line-height: 1.6; text-align: center;">
                                Esta é uma mensagem automática do sistema {APP_NAME}.<br>
                                Por favor, não responda a este email.
                            </p>
                            <p style="margin: 8px 0 0; color: #9ca3af; font-size: 12px; text-align: center;">
                                Se você não solicitou esta ação, ignore este email.<br>
                                Sua conta permanecerá segura.
                            </p>
                            <p style="margin: 16px 0 0; color: #9ca3af; font-size: 12px; text-align: center;">
                                &copy; 2024 {APP_NAME}. Todos os direitos reservados.
                            </p>
                        </td>
                    </tr>
                    
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
    """.strip()


def _get_text_template(title: str, greeting: str, message: str, button_text: str, button_link: str, footer_note: str = "") -> str:
    """
    Template de texto simples para fallback (clientes sem suporte HTML)
    
    Args:
        title: Título do email
        greeting: Saudação inicial
        message: Corpo da mensagem
        button_text: Texto da ação
        button_link: Link
        footer_note: Nota adicional
    
    Returns:
        String de texto simples
    """
    text = f"""
{APP_NAME}
{'=' * 60}

{title}

{greeting}

{message}

{button_text}: {button_link}
"""
    
    if footer_note:
        text += f"\n⚠️ IMPORTANTE: {footer_note}\n"
    
    text += f"""
{'=' * 60}

Esta é uma mensagem automática do sistema {APP_NAME}.
Por favor, não responda a este email.

Se você não solicitou esta ação, ignore este email.
Sua conta permanecerá segura.

© 2024 {APP_NAME}. Todos os direitos reservados.
    """.strip()
    
    return text


def _send_email(to_email: str, subject: str, html_content: str, text_content: str) -> bool:
    """
    Envia email via SMTP ou Resend API
    
    Args:
        to_email: Email do destinatário
        subject: Assunto do email
        html_content: Conteúdo HTML
        text_content: Conteúdo texto simples (fallback)
    
    Returns:
        True se enviado com sucesso, False caso contrário
    """
    # Validação de configuração
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        print("❌ Erro: SMTP_EMAIL e SMTP_PASSWORD não configurados nas variáveis de ambiente")
        return False
    
    # Se Resend, usar API HTTP (não SMTP)
    if USE_RESEND_API:
        return _send_via_resend_api(to_email, subject, html_content, text_content)
    
    # Caso contrário, usar SMTP tradicional
    return _send_via_smtp(to_email, subject, html_content, text_content)


def _send_via_resend_api(to_email: str, subject: str, html_content: str, text_content: str) -> bool:
    """Envia email via API HTTP do Resend (evita bloqueio de portas SMTP)"""
    try:
        # Verificar se email está na lista permitida
        if to_email not in ALLOWED_EMAILS:
            print(f"⚠️ Email {to_email} não está na lista ALLOWED_EMAILS")
            print(f"   Emails permitidos: {', '.join(ALLOWED_EMAILS)}")
            print(f"   Adicione ao Render: ALLOWED_EMAILS={to_email},{','.join(ALLOWED_EMAILS)}")
            return False
        
        print(f"[EMAIL_SERVICE] Enviando via Resend API para {to_email}")
        print(f"[EMAIL_SERVICE] API Key: {SMTP_PASSWORD[:10]}...")
        
        url = "https://api.resend.com/emails"
        headers = {
            "Authorization": f"Bearer {SMTP_PASSWORD}",
            "Content-Type": "application/json"
        }
        data = {
            "from": f"{APP_NAME} <onboarding@resend.dev>",
            "to": [to_email],
            "subject": subject,
            "html": html_content,
            "text": text_content
        }
        
        print(f"[EMAIL_SERVICE] Enviando POST para {url}")
        response = requests.post(url, json=data, headers=headers, timeout=10)
        
        print(f"[EMAIL_SERVICE] Status: {response.status_code}")
        print(f"[EMAIL_SERVICE] Response: {response.text}")
        
        if response.status_code == 200:
            print(f"✅ Email enviado com sucesso via Resend API para {to_email}")
            return True
        else:
            print(f"❌ Erro Resend API: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Erro ao enviar via Resend API: {e}")
        import traceback
        traceback.print_exc()
        return False


def _send_via_smtp(to_email: str, subject: str, html_content: str, text_content: str) -> bool:
    """Envia email via SMTP tradicional"""
    try:
        print(f"[EMAIL_SERVICE] Iniciando envio para {to_email}")
        print(f"[EMAIL_SERVICE] SMTP_SERVER={SMTP_SERVER}, SMTP_PORT={SMTP_PORT}")
        print(f"[EMAIL_SERVICE] SMTP_EMAIL={SMTP_EMAIL}")
        print(f"[EMAIL_SERVICE] Subject={subject}")
        _debug_log(f"SMTP_SERVER={SMTP_SERVER}, SMTP_PORT={SMTP_PORT}, SMTP_EMAIL={'definido' if SMTP_EMAIL else 'vazio'}")
        # Criar mensagem multipart (HTML + Text)
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        # Para serviços como Resend, usar email válido no From
        from_email = SMTP_EMAIL if '@' in SMTP_EMAIL else 'noreply@resend.dev'
        msg['From'] = f'{APP_NAME} <{from_email}>'  # Nome de exibição amigável
        msg['To'] = to_email
        print(f"[EMAIL_SERVICE] From={msg['From']}, To={msg['To']}")
        
        # Adicionar versão texto simples (fallback)
        part1 = MIMEText(text_content, 'plain', 'utf-8')
        msg.attach(part1)
        
        # Adicionar versão HTML (preferencial)
        part2 = MIMEText(html_content, 'html', 'utf-8')
        msg.attach(part2)
        
        # Conectar ao servidor SMTP (SSL para 465, STARTTLS para 587)
        if SMTP_PORT == 465:
            print("[EMAIL_SERVICE] Usando porta 465 (SSL)")
            _debug_log("Conectando via SMTP_SSL (porta 465)")
            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
                _debug_log("Ligado ao servidor (SSL). Tentando autenticar...")
                print("[EMAIL_SERVICE] Conectado via SSL. Autenticando...")
                server.login(SMTP_EMAIL, SMTP_PASSWORD)
                _debug_log("Autenticado com sucesso (SSL)")
                print("[EMAIL_SERVICE] Autenticado com sucesso!")
                server.send_message(msg)
                _debug_log("Mensagem enviada (SSL)")
                print("[EMAIL_SERVICE] Mensagem enviada!")
        else:
            print("[EMAIL_SERVICE] Usando porta 587 (STARTTLS)")
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
                _debug_log("Conectado via SMTP. EHLO inicial...")
                print("[EMAIL_SERVICE] Conectado. Iniciando STARTTLS...")
                try:
                    server.ehlo()
                except Exception as e:
                    _debug_log(f"EHLO falhou: {e}")
                try:
                    _debug_log("Tentando STARTTLS...")
                    server.starttls()
                    print("[EMAIL_SERVICE] STARTTLS ativado")
                    try:
                        server.ehlo()
                    except Exception:
                        pass
                    _debug_log("STARTTLS ok")
                except smtplib.SMTPException as e:
                    print(f"⚠️ STARTTLS indisponível ou falhou: {e}. Continuando sem TLS.")
                _debug_log("Tentando autenticar (LOGIN)...")
                print(f"[EMAIL_SERVICE] Autenticando como {SMTP_EMAIL}...")
                server.login(SMTP_EMAIL, SMTP_PASSWORD)
                _debug_log("Autenticado com sucesso. Enviando mensagem...")
                print("[EMAIL_SERVICE] Autenticado! Enviando mensagem...")
                server.send_message(msg)
                _debug_log("Mensagem enviada")
                print("[EMAIL_SERVICE] Mensagem enviada com sucesso!")
        
        print(f"✅ Email enviado com sucesso para {to_email}")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ Erro de autenticação SMTP: {e}")
        print(f"   SMTP_SERVER={SMTP_SERVER}, SMTP_PORT={SMTP_PORT}")
        print(f"   SMTP_EMAIL={'definido' if SMTP_EMAIL else 'vazio'}")
        print("   Verifique SMTP_EMAIL e SMTP_PASSWORD")
        import traceback
        traceback.print_exc()
        return False
    except smtplib.SMTPException as e:
        print(f"❌ Erro SMTP: {e}")
        print(f"   Tipo: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"❌ Erro ao enviar email: {e}")
        print(f"   Tipo: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False


def send_confirmation_email(user_email: str, token: str) -> bool:
    """
    Envia email de confirmação de conta
    
    Args:
        user_email: Email do novo usuário
        token: Token de confirmação único
    
    Returns:
        True se enviado com sucesso, False caso contrário
    
    Exemplo:
        >>> send_confirmation_email('usuario@exemplo.com', 'abc123xyz789')
        ✅ Email enviado com sucesso para usuario@exemplo.com
        True
    """
    # Construir link de confirmação
    confirmation_link = f"{APP_URL}/confirmar-email?token={token}"
    
    # Assunto (claro, sem spam triggers)
    subject = f"Confirme sua conta no {APP_NAME}"
    
    # Conteúdo
    title = f"Bem-vindo(a) ao {APP_NAME}!"
    greeting = "Olá! Ficamos muito felizes em tê-lo(a) conosco."
    message = (
        "Você está a um passo de começar a usar nossa plataforma de gestão de ocorrências. "
        "Para ativar sua conta e garantir a segurança dos seus dados, precisamos confirmar seu endereço de email."
    )
    button_text = "Confirmar Minha Conta"
    footer_note = "Este link de confirmação expira em 24 horas por motivos de segurança."
    
    # Gerar HTML e texto
    html_content = _get_html_template(title, greeting, message, button_text, confirmation_link, footer_note)
    text_content = _get_text_template(title, greeting, message, button_text, confirmation_link, footer_note)
    
    # Enviar
    return _send_email(user_email, subject, html_content, text_content)


def send_reset_password_email(user_email: str, token: str) -> bool:
    """
    Envia email de redefinição de senha
    
    Args:
        user_email: Email do usuário
        token: Token de redefinição único
    
    Returns:
        True se enviado com sucesso, False caso contrário
    
    Exemplo:
        >>> send_reset_password_email('usuario@exemplo.com', 'xyz789abc123')
        ✅ Email enviado com sucesso para usuario@exemplo.com
        True
    """
    # Construir link de redefinição (rota real da aplicação)
    reset_link = f"{APP_URL}/reset-password/{token}"
    
    # Assunto (claro, sem spam triggers)
    subject = f"Redefinição de senha - {APP_NAME}"
    
    # Conteúdo
    title = "Solicitação de Redefinição de Senha"
    greeting = "Olá! Recebemos uma solicitação para redefinir a senha da sua conta."
    message = (
        "Se você solicitou esta redefinição, clique no botão abaixo para criar uma nova senha. "
        "Se você não fez esta solicitação, pode ignorar este email com segurança — sua senha atual permanecerá inalterada."
    )
    button_text = "Redefinir Minha Senha"
    footer_note = "⚠️ IMPORTANTE: Por motivos de segurança, este link expira em 1 hora. Após esse período, será necessário solicitar uma nova redefinição."
    
    # Gerar HTML e texto
    html_content = _get_html_template(title, greeting, message, button_text, reset_link, footer_note)
    text_content = _get_text_template(title, greeting, message, button_text, reset_link, footer_note)
    
    # Enviar
    return _send_email(user_email, subject, html_content, text_content)


# Exemplo de uso (apenas para testes)
if __name__ == '__main__':
    print("=" * 70)
    print("📧 Teste do Serviço de Envio de Emails")
    print("=" * 70)
    print()
    
    # Verificar configuração
    print("Configuração atual:")
    print(f"  SMTP_SERVER: {SMTP_SERVER}")
    print(f"  SMTP_PORT: {SMTP_PORT}")
    print(f"  SMTP_EMAIL: {SMTP_EMAIL or '❌ NÃO CONFIGURADO'}")
    print(f"  SMTP_PASSWORD: {'✅ Configurado' if SMTP_PASSWORD else '❌ NÃO CONFIGURADO'}")
    print(f"  APP_NAME: {APP_NAME}")
    print(f"  APP_URL: {APP_URL}")
    print()
    
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        print("⚠️  Configure as variáveis de ambiente antes de testar:")
        print("   - SMTP_EMAIL")
        print("   - SMTP_PASSWORD")
        print("   - SMTP_SERVER (opcional, padrão: smtp.gmail.com)")
        print("   - SMTP_PORT (opcional, padrão: 587)")
        print("   - APP_NAME (opcional)")
        print("   - APP_URL (opcional)")
        print()
        print("Exemplo para Gmail:")
        print("  export SMTP_EMAIL='seu-email@gmail.com'")
        print("  export SMTP_PASSWORD='sua-senha-de-app'")
        print()
    else:
        # Teste de confirmação
        print("📧 Testando envio de confirmação de email...")
        test_email = input("Digite um email para teste (Enter para pular): ").strip()
        if test_email:
            success = send_confirmation_email(test_email, "TOKEN_TESTE_123")
            print(f"   {'✅ Sucesso!' if success else '❌ Falha'}")
            print()
        
        # Teste de redefinição
        print("📧 Testando envio de redefinição de senha...")
        test_email = input("Digite um email para teste (Enter para pular): ").strip()
        if test_email:
            success = send_reset_password_email(test_email, "TOKEN_RESET_456")
            print(f"   {'✅ Sucesso!' if success else '❌ Falha'}")
            print()
    
    print("=" * 70)
