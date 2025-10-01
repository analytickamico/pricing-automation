#!/bin/bash
LOG_DIR="/home/ubuntu/kami-automations/services/pricing-automation/logs"
HEALTH_LOG="$LOG_DIR/health-check.log"

# Verificar se houve execução nos últimos 15 minutos
RECENT_LOG=$(find "$LOG_DIR" -name "pricing-*.log" -mmin -15 -exec grep -l "Iniciando pricing automation" {} \; 2>/dev/null)

if [ -z "$RECENT_LOG" ]; then
    echo "$(date): ALERTA - Pricing automation não executou nos últimos 15 minutos" >> "$HEALTH_LOG"
fi

# Verificar erros recentes
ERROR_COUNT=$(find "$LOG_DIR" -name "pricing-*.log" -mmin -60 -exec grep -c "ERRO\|ERROR\|Exception" {} \; 2>/dev/null | paste -sd+ | bc 2>/dev/null || echo 0)

if [ "$ERROR_COUNT" -gt 0 ]; then
    echo "$(date): ALERTA - $ERROR_COUNT erros encontrados na última hora" >> "$HEALTH_LOG"
fi

# Verificar se Django está acessível
if ! curl -s http://127.0.0.1:8000/health/ > /dev/null; then
    echo "$(date): ALERTA - Django API não está acessível" >> "$HEALTH_LOG"
fi
