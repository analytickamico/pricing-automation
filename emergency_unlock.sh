#!/bin/bash
echo "=== EMERGENCY UNLOCK - PRICING AUTOMATION ==="
echo "Data/Hora: $(date)"
echo ""

LOCK_FILE="/tmp/pricing-automation.lock"

if [ -f "$LOCK_FILE" ]; then
    echo "🔒 Lock file encontrado - removendo..."
    rm "$LOCK_FILE"
    echo "✅ Lock file removido - sistema liberado para nova execução"
    echo ""
    echo "ℹ️  O sistema poderá executar normalmente na próxima janela de 10 minutos"
else
    echo "✅ Sistema já estava livre - nenhum lock file encontrado"
fi

echo ""
echo "=== STATUS ATUAL ==="
if [ -f "$LOCK_FILE" ]; then
    echo "🔒 Status: BLOQUEADO"
else
    echo "🟢 Status: LIVRE"
fi

echo ""
echo "=== ÚLTIMAS EXECUÇÕES ==="
grep "===== " ~/kami-automations/services/pricing-automation/logs/pricing-*.log | tail -3

echo ""
echo "=== PRÓXIMA EXECUÇÃO PREVISTA ==="
NEXT_MIN=$(( ($(date +%M) / 10 + 1) * 10 ))
if [ $NEXT_MIN -ge 60 ]; then
    NEXT_HOUR=$(( $(date +%H) + 1 ))
    NEXT_MIN=0
else
    NEXT_HOUR=$(date +%H)
fi
printf "⏰ Próxima execução: %02d:%02d\n" $NEXT_HOUR $NEXT_MIN
