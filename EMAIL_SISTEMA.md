# 📧 Sistema de Email com Resend (Plano Gratuito)

## Como Funciona:

O Resend no plano gratuito só permite enviar para emails verificados manualmente.

### ✅ Solução Implementada:

- Lista de emails permitidos via variável `ALLOWED_EMAILS`
- Se email estiver na lista → envia via Resend API
- Se NÃO estiver na lista → mostra link na tela (como localhost)

---

## 🔧 Configuração no Render:

### Variáveis de Ambiente:

```
SMTP_SERVER = smtp.resend.com
SMTP_PORT = 587
SMTP_EMAIL = resend
SMTP_PASSWORD = re_xxxxxxx (API key do Resend)
APP_NAME = Praias Fluviais
APP_URL = https://praias-fluviais.onrender.com
ALLOWED_EMAILS = nelsonalunogpsi@gmail.com,nelsonbsebastiao0@gmail.com,outro@email.com
```

### Formato da ALLOWED_EMAILS:

```
email1@exemplo.com,email2@exemplo.com,email3@exemplo.com
```

**Separados por vírgula, SEM espaços.**

---

## 📝 Adicionar Novos Emails:

### Método 1: Atualizar ALLOWED_EMAILS (Recomendado)

1. Render Dashboard → Environment
2. Edite `ALLOWED_EMAILS`
3. Adicione o novo email separado por vírgula:
   ```
   nelsonalunogpsi@gmail.com,novo@email.com
   ```
4. Save Changes

### Método 2: Verificar no Resend (Melhor para poucos emails)

1. Resend Dashboard → Settings → Email Addresses
2. Add Email Address
3. Confirme no email recebido
4. Adicione também à `ALLOWED_EMAILS`

---

## 🎯 Comportamento:

### Email na lista (permitido):
```
User: novo@email.com
✅ Email enviado via Resend API
📧 Recebe email de recuperação
```

### Email NÃO na lista:
```
User: desconhecido@email.com
⚠️ Email não está em ALLOWED_EMAILS
📋 Mostra link de recuperação na tela
```

---

## 🚀 Para Produção (Futuro):

Quando quiser enviar para **qualquer email**:

1. Compre domínio: `praias-fluviais.pt` (€10/ano)
2. Resend → Domains → Add Domain
3. Configure DNS (SPF, DKIM)
4. Emails funcionam para todos automaticamente
5. Nunca mais caem em spam

---

## ✅ Vantagens desta Solução:

- ✅ Funciona no Render gratuito
- ✅ Sem bloqueio de portas SMTP
- ✅ Fácil adicionar novos emails
- ✅ Fallback para mostrar link na tela
- ✅ Emails reais recebem via Resend
- ✅ Outros veem link na tela (útil para testes)

---

## 📊 Resumo:

| Email | Comportamento |
|-------|--------------|
| `nelsonalunogpsi@gmail.com` | ✅ Envia via Resend |
| `nelsonbsebastiao0@gmail.com` | ✅ Envia via Resend (se adicionar) |
| `presidente@praias.pt` | 📋 Mostra link na tela |
| Qualquer outro | 📋 Mostra link na tela |

**Perfeito para desenvolvimento e testes!**
