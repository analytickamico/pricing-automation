#!/bin/bash
set -e

# Configurações
PROJECT_DIR="/home/ubuntu/kami-automations/services/pricing-automation"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/pricing-$(date +%Y%m%d).log"
LOCK_FILE="/tmp/pricing-automation.lock"

# Criar diretório de logs se não existir
mkdir -p "$LOG_DIR"

# Verificar se já está rodando
if [ -f "$LOCK_FILE" ]; then
    echo "$(date): Pricing automation já está rodando" >> "$LOG_FILE"
    exit 1
fi

# Criar lock file
touch "$LOCK_FILE"

# Cleanup function
cleanup() {
    rm -f "$LOCK_FILE"
}
trap cleanup EXIT

echo "$(date): ===== Iniciando pricing automation =====" >> "$LOG_FILE"

# Verificar espaço em disco antes da execução
DISK_USAGE=$(df /var/lib/docker --output=pcent | tail -n1 | tr -d ' %')
echo "$(date): Uso do disco antes: ${DISK_USAGE}%" >> "$LOG_FILE"

# Limpeza automática se uso > 80%
if [ "$DISK_USAGE" -gt 80 ]; then
    echo "$(date): Uso do disco alto (${DISK_USAGE}%), executando limpeza..." >> "$LOG_FILE"
    docker system prune -af --volumes >> "$LOG_FILE" 2>&1
    # Remover imagens não utilizadas há mais de 24h
    docker image prune -af --filter "until=24h" >> "$LOG_FILE" 2>&1
    echo "$(date): Limpeza concluída" >> "$LOG_FILE"
fi

cd "$PROJECT_DIR"

# Verificar se Django está rodando
if ! curl -s http://127.0.0.1:8000/health/ > /dev/null; then
    echo "$(date): ERRO - Django API não está acessível" >> "$LOG_FILE"
    exit 1
fi

# Executar container
docker compose run --rm pricing-automation >> "$LOG_FILE" 2>&1

if [ $? -eq 0 ]; then
    echo "$(date): ===== Pricing automation finalizado com sucesso =====" >> "$LOG_FILE"
    
    # Limpeza leve após execução bem-sucedida
    echo "$(date): Executando limpeza pós-execução..." >> "$LOG_FILE"
    docker system prune -f >> "$LOG_FILE" 2>&1
else
    echo "$(date): ===== ERRO na execução do pricing automation =====" >> "$LOG_FILE"
fi

# Verificar espaço em disco após execução
DISK_USAGE_AFTER=$(df /var/lib/docker --output=pcent | tail -n1 | tr -d ' %')
echo "$(date): Uso do disco após: ${DISK_USAGE_AFTER}%" >> "$LOG_FILE"
