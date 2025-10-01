#!/bin/bash
echo "============================================"
echo "     STATUS PRICING AUTOMATION"
echo "============================================"
echo "Data/Hora: $(date)"
echo ""

echo "=== ÚLTIMA EXECUÇÃO ==="
LAST_LOG=$(find ~/kami-automations/services/pricing-automation/logs -name "pricing-*.log" -exec ls -lt {} \; | head -1)
echo "$LAST_LOG"

echo ""
echo "=== CRONTAB ATIVO ==="
crontab -l | grep pricing

echo ""
echo "=== STATUS DJANGO API ==="
if curl -s http://127.0.0.1:8000/health/ > /dev/null; then
    echo "✅ Django API está respondendo"
else
    echo "❌ Django API não está acessível"
fi

echo ""
echo "=== LOCK FILE ==="
if [ -f "/tmp/pricing-automation.lock" ]; then
    echo "🟡 Sistema está executando agora"
else
    echo "🟢 Sistema está livre para execução"
fi

echo ""
echo "=== ÚLTIMAS 5 EXECUÇÕES ==="
grep "===== " ~/kami-automations/services/pricing-automation/logs/pricing-*.log | tail -5

echo ""
echo "=== ESPAÇO EM DISCO ==="
df -h /home/ubuntu/kami-automations/services/pricing-automation/logs

echo ""
echo "=== ESTATÍSTICAS DOS LOGS ==="
find ~/kami-automations/services/pricing-automation/logs -name "pricing-*.log" -exec wc -l {} \; | awk '{sum+=$1} END {print "Total de linhas nos logs: " sum}'

echo "============================================"
