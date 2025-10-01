#!/bin/bash
echo "=== Acompanhando logs em tempo real ==="
echo "Pressione Ctrl+C para sair"
echo ""
tail -f ~/kami-automations/services/pricing-automation/logs/pricing-$(date +%Y%m%d).log

