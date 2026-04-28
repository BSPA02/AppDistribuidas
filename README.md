# AppDistribuidas

## Variables de entorno

Para el envío de correos con Resend:

- `RESEND_API_KEY`
- `RESEND_FROM` (por ejemplo, `onboarding@resend.dev` o un remitente verificado en Resend)

La API `POST /enviar-alerta` espera un JSON con:

- `to`
- `subject`
- `message`